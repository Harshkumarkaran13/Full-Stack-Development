"""Document conversion, PDF processing, scanning and encryption services."""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import PurePosixPath

import fitz
from PIL import Image
from pypdf import PdfReader, PdfWriter
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAX_SIZE = 25 * 1024 * 1024
MAX_ENCRYPTED_SIZE = 40 * 1024 * 1024
MAX_FOLDER_FILES = 500
TEXT_HEADER = b"PDFMASTER-TEXT-ENCRYPTED-V1"
FILE_HEADER = b"PDFMASTER-FILE-ENCRYPTED-V1"
FOLDER_HEADER = b"PDFMASTER-FOLDER-ENCRYPTED-V1"


def _read_upload(upload, *, max_size: int = MAX_SIZE) -> bytes:
    if upload is None:
        raise ValueError("Choose a file first.")
    if upload.size > max_size:
        raise ValueError(f"File must be {max_size // (1024 * 1024)} MB or smaller.")
    data = upload.read()
    upload.seek(0)
    return data


def read_pdf(upload) -> bytes:
    data = _read_upload(upload)
    if not upload.name.lower().endswith(".pdf"):
        raise ValueError("Upload a PDF file.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if not reader.is_encrypted:
            _ = len(reader.pages)
    except Exception as exc:
        raise ValueError("This PDF is invalid or unreadable.") from exc
    return data


def parse_pages(spec: str, total: int) -> list[int]:
    result: set[int] = set()
    try:
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start, end = [int(value.strip()) for value in part.split("-", 1)]
                if start < 1 or end < start or end > total:
                    raise ValueError
                result.update(range(start, end + 1))
            else:
                page_number = int(part)
                if page_number < 1 or page_number > total:
                    raise ValueError
                result.add(page_number)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid page range. This PDF has {total} pages.") from exc
    if not result:
        raise ValueError("Enter pages, for example 1-3,5.")
    return sorted(result)


def _safe_filename(name: str, fallback: str = "download.bin") -> str:
    name = (name or "").replace("\\", "/").split("/")[-1].strip()
    if name in {"", ".", ".."}:
        return fallback
    # Prevent control characters and path separators from reaching download headers.
    return "".join(ch for ch in name if ch.isprintable() and ch not in '\\/:*?"<>|') or fallback


def _text_key(password: str, salt: bytes) -> bytes:
    if not password or len(password) < 8:
        raise ValueError("Use a password with at least 8 characters.")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _make_envelope(header: bytes, payload: bytes, password: str, metadata: dict | None = None) -> bytes:
    salt = os.urandom(16)
    if metadata is not None:
        payload = json.dumps(metadata, ensure_ascii=False).encode("utf-8") + b"\n" + payload
    token = Fernet(_text_key(password, salt)).encrypt(payload)
    return header + b"\n" + base64.b64encode(salt) + b"\n" + token


def _open_envelope(raw: bytes, expected_header: bytes, password: str) -> bytes:
    """Open current envelopes and the earlier v3 literal-backslash-n format."""
    for separator in (b"\n", b"\\n"):
        try:
            header, salt_line, token = raw.split(separator, 2)
            if header != expected_header:
                continue
            salt = base64.b64decode(salt_line, validate=True)
            if len(salt) != 16:
                raise ValueError
            return Fernet(_text_key(password, salt)).decrypt(token)
        except InvalidToken as exc:
            raise ValueError("Incorrect password or the protected file has been damaged.") from exc
        except ValueError:
            # Try the legacy separator before returning a format error.
            continue
        except Exception:
            continue
    raise ValueError("This is not a valid PDF Master encrypted file.")


def encrypt_text_file(upload, password: str):
    if upload is None:
        raise ValueError("Choose a text file.")
    if not upload.name.lower().endswith(".txt"):
        raise ValueError("Upload a .txt file.")
    raw = _read_upload(upload)
    try:
        raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Text file must be UTF-8 encoded.") from exc
    return _make_envelope(TEXT_HEADER, raw, password), "encrypted-text.pmx"


def decrypt_text_file(upload, password: str):
    if upload is None:
        raise ValueError("Choose an encrypted .pmx file.")
    raw = _read_upload(upload, max_size=MAX_ENCRYPTED_SIZE)
    plain = _open_envelope(raw, TEXT_HEADER, password)
    return plain, "decrypted-text.txt"


def encrypt_message(message: str, password: str):
    if not message or not message.strip():
        raise ValueError("Enter a text message to encrypt.")
    raw = message.encode("utf-8")
    if len(raw) > MAX_SIZE:
        raise ValueError("Message is too large.")
    return _make_envelope(TEXT_HEADER, raw, password), "encrypted-message.pmx"


def encrypt_any_file(upload, password: str):
    if upload is None:
        raise ValueError("Choose a file to protect.")
    raw = _read_upload(upload)
    original_name = _safe_filename(upload.name)
    container = _make_envelope(
        FILE_HEADER,
        raw,
        password,
        metadata={"filename": original_name, "kind": "file"},
    )
    return container, "protected-file.pme"


def decrypt_any_file(upload, password: str):
    if upload is None:
        raise ValueError("Choose a .pme protected file.")
    raw = _read_upload(upload, max_size=MAX_ENCRYPTED_SIZE)
    payload = _open_envelope(raw, FILE_HEADER, password)
    try:
        separator = b"\n" if b"\n" in payload else b"\\n"
        metadata_line, content = payload.split(separator, 1)
        metadata = json.loads(metadata_line.decode("utf-8"))
        filename = _safe_filename(metadata.get("filename", "decrypted-file.bin"))
        return content, filename
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError("The protected file metadata is invalid.") from exc


def _safe_archive_path(path_text: str) -> str:
    normalized = (path_text or "").replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("The selected folder contains an invalid file path.")
    if any(":" in part for part in path.parts):
        raise ValueError("The selected folder contains an invalid file path.")
    cleaned = ["".join(ch for ch in part if ch.isprintable() and ch not in '\\:*?"<>|') for part in path.parts]
    if any(not part for part in cleaned):
        raise ValueError("The selected folder contains an invalid file name.")
    return "/".join(cleaned)


def encrypt_folder(files, manifest_json: str, password: str):
    if not files:
        raise ValueError("Choose a folder containing at least one file.")
    if len(files) > MAX_FOLDER_FILES:
        raise ValueError(f"A folder can contain up to {MAX_FOLDER_FILES} files per operation.")
    try:
        manifest = json.loads(manifest_json or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("The folder selection could not be read. Select the folder again.") from exc
    paths = []
    if isinstance(manifest, list) and len(manifest) == len(files):
        for item in manifest:
            paths.append(_safe_archive_path(str(item.get("path", "")) if isinstance(item, dict) else ""))
    else:
        # Fallback for browsers that do not expose webkitRelativePath.
        paths = [_safe_archive_path(getattr(file_obj, "name", "")) for file_obj in files]
    if len(set(paths)) != len(paths):
        raise ValueError("The selected folder has duplicate file paths. Rename duplicates and try again.")

    total_size = sum(file_obj.size for file_obj in files)
    if total_size > MAX_SIZE:
        raise ValueError("The selected folder must be 25 MB or smaller in total.")

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_obj, relative_path in zip(files, paths):
            archive.writestr(relative_path, _read_upload(file_obj))

    root_name = paths[0].split("/", 1)[0] if "/" in paths[0] else "protected-folder"
    zip_name = _safe_filename(root_name, "protected-folder") + ".zip"
    container = _make_envelope(
        FOLDER_HEADER,
        archive_buffer.getvalue(),
        password,
        metadata={"filename": zip_name, "kind": "folder"},
    )
    return container, "protected-folder.pmf"


def decrypt_folder(upload, password: str):
    if upload is None:
        raise ValueError("Choose a .pmf protected folder file.")
    raw = _read_upload(upload, max_size=MAX_ENCRYPTED_SIZE)
    payload = _open_envelope(raw, FOLDER_HEADER, password)
    try:
        metadata_line, archive_data = payload.split(b"\n", 1)
        metadata = json.loads(metadata_line.decode("utf-8"))
        if metadata.get("kind") != "folder" or not zipfile.is_zipfile(io.BytesIO(archive_data)):
            raise ValueError
    except Exception as exc:
        raise ValueError("The folder container is invalid or damaged.") from exc
    return archive_data, _safe_filename(metadata.get("filename", "decrypted-folder.zip"), "decrypted-folder.zip")


def pdf_to_word(upload):
    """Convert a text-based PDF to an editable DOCX document."""
    data = read_pdf(upload)
    try:
        from pdf2docx import Converter
    except ImportError as exc:
        raise ValueError("PDF-to-Word is unavailable. Install the pdf2docx dependency from requirements.txt.") from exc
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "source.pdf")
        docx_path = os.path.join(tmp, "converted.docx")
        with open(pdf_path, "wb") as handle:
            handle.write(data)
        converter = Converter(pdf_path)
        try:
            converter.convert(docx_path, start=0, end=None)
        finally:
            converter.close()
        if not os.path.exists(docx_path) or os.path.getsize(docx_path) == 0:
            raise ValueError("Could not convert this PDF. It may be scanned or image-only.")
        with open(docx_path, "rb") as handle:
            return handle.read(), "converted.docx"


def _libreoffice_executable() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def _convert_with_libreoffice(upload, allowed_extensions: tuple[str, ...], output_ext: str, tool_label: str):
    if upload is None:
        raise ValueError("Choose a file first.")
    if upload.size > MAX_SIZE:
        raise ValueError("File must be 25 MB or smaller.")
    if not upload.name.lower().endswith(allowed_extensions):
        raise ValueError("Unsupported file type for this conversion.")
    executable = _libreoffice_executable()
    if not executable:
        raise ValueError(f"{tool_label} requires LibreOffice installed and available on PATH.")
    with tempfile.TemporaryDirectory() as tmp:
        safe_name = _safe_filename(upload.name)
        source_path = os.path.join(tmp, safe_name)
        with open(source_path, "wb") as handle:
            for chunk in upload.chunks():
                handle.write(chunk)
        profile_path = os.path.join(tmp, "lo-profile")
        command = [
            executable,
            "-env:UserInstallation=" + PathToFileURL(profile_path),
            "--headless",
            "--convert-to", output_ext,
            "--outdir", tmp,
            source_path,
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"{tool_label} timed out. Try a smaller document.") from exc
        output_path = os.path.splitext(source_path)[0] + "." + output_ext
        if result.returncode != 0 or not os.path.exists(output_path):
            detail = (result.stderr or result.stdout or "").strip()
            raise ValueError(f"LibreOffice could not complete {tool_label.lower()}. {detail[:220]}")
        with open(output_path, "rb") as handle:
            return handle.read()


def PathToFileURL(path: str) -> str:
    # LibreOffice expects a file URL for its isolated user profile.
    from pathlib import Path
    return Path(path).resolve().as_uri()


def word_to_pdf(upload):
    data = _convert_with_libreoffice(
        upload,
        (".docx", ".doc"),
        "pdf",
        "Word-to-PDF conversion",
    )
    return data, "converted.pdf"


def text_to_word(upload):
    if upload is None:
        raise ValueError("Choose a TXT file.")
    if not upload.name.lower().endswith(".txt"):
        raise ValueError("Upload a .txt file.")
    raw = _read_upload(upload)
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Text file must be UTF-8 encoded.") from exc
    from docx import Document
    from docx.shared import Pt

    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    for line in content.splitlines():
        document.add_paragraph(line)
    if not content:
        document.add_paragraph("")
    output = io.BytesIO()
    document.save(output)
    return output.getvalue(), "text-to-word.docx"


def word_to_text(upload):
    if upload is None:
        raise ValueError("Choose a Word document.")
    if not upload.name.lower().endswith(".docx"):
        raise ValueError("Upload a .docx Word document. Legacy .doc files are not supported by this tool.")
    raw = _read_upload(upload)
    from docx import Document
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    try:
        document = Document(io.BytesIO(raw))
    except Exception as exc:
        raise ValueError("This Word document is invalid or unreadable.") from exc
    parts: list[str] = []
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, document)
            parts.append(paragraph.text)
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            for row in table.rows:
                parts.append("\t".join(cell.text.replace("\n", " / ") for cell in row.cells))
    return "\n".join(parts).encode("utf-8"), "word-to-text.txt"


def text_to_pdf(upload):
    if upload is None:
        raise ValueError("Choose a TXT file.")
    if not upload.name.lower().endswith(".txt"):
        raise ValueError("Upload a .txt file.")
    try:
        content = _read_upload(upload).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Text file must be UTF-8 encoded.") from exc
    doc = fitz.open()
    page = doc.new_page()
    margin = 48
    x = margin
    y = margin
    line_height = 14
    max_chars = 95
    for line in content.splitlines() or [""]:
        chunks = [line[i:i + max_chars] for i in range(0, max(len(line), 1), max_chars)]
        for segment in chunks:
            if y > page.rect.height - margin:
                page = doc.new_page()
                y = margin
            page.insert_text((x, y), segment, fontsize=10)
            y += line_height
    output = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return output, "text-to-pdf.pdf"


def pdf_to_html(upload):
    doc = fitz.open(stream=read_pdf(upload), filetype="pdf")
    sections = ['<section class="pdf-page">' + page.get_text("html") + "</section>" for page in doc]
    doc.close()
    html = (
        '<!doctype html><html><head><meta charset="utf-8"><title>Converted PDF</title>'
        '<style>body{font-family:Arial,sans-serif;background:#eee}'
        '.pdf-page{background:white;margin:24px auto;padding:30px;max-width:900px;'
        'min-height:700px;box-shadow:0 1px 8px #bbb;overflow:hidden}</style>'
        '</head><body>' + "".join(sections) + "</body></html>"
    )
    return html.encode("utf-8"), "converted.html"


def html_to_pdf(upload):
    if upload is None:
        raise ValueError("Choose an HTML file.")
    data = _convert_with_libreoffice(upload, (".html", ".htm"), "pdf", "HTML-to-PDF conversion")
    return data, "html-to-pdf.pdf"


def remove_pages(upload, spec: str):
    reader = PdfReader(io.BytesIO(read_pdf(upload)), strict=False)
    remove = set(parse_pages(spec, len(reader.pages)))
    writer = PdfWriter()
    for index, page in enumerate(reader.pages, start=1):
        if index not in remove:
            writer.add_page(page)
    if not writer.pages:
        raise ValueError("You cannot remove every page.")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), "pages-removed.pdf"


def add_page_numbers(upload, position: str = "bottom"):
    doc = fitz.open(stream=read_pdf(upload), filetype="pdf")
    total = len(doc)
    for index, page in enumerate(doc, start=1):
        rect = page.rect
        y = rect.height - 24 if position == "bottom" else 24
        page.insert_text((rect.width / 2 - 12, y), f"{index} / {total}", fontsize=9, color=(.35, .35, .35))
    result = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return result, "numbered.pdf"


def repair_pdf(upload):
    data = read_pdf(upload)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        result = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()
        PdfReader(io.BytesIO(result), strict=False)
    except Exception as exc:
        raise ValueError("This PDF could not be repaired with the available tools.") from exc
    return result, "repaired.pdf"


def pdf_scanner(upload, password: str = ""):
    """Create a heuristic PDF structure report; this is not antivirus detection."""
    data = _read_upload(upload)
    if not upload.name.lower().endswith(".pdf"):
        raise ValueError("Upload a PDF file.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
    except Exception as exc:
        raise ValueError("This file could not be parsed as a PDF.") from exc

    lines = ["PDF MASTER — PDF SCAN REPORT", "=" * 34]
    lines.append(f"File name: {_safe_filename(upload.name)}")
    lines.append(f"File size: {len(data):,} bytes")
    lines.append(f"PDF encrypted: {'Yes' if reader.is_encrypted else 'No'}")
    if reader.is_encrypted and (not password or not reader.decrypt(password)):
        lines.extend([
            "Content inspection: Not performed because the PDF is encrypted and no valid password was supplied.",
            "Result: Password-protected file detected; this is not a malware verdict.",
            "",
            "IMPORTANT: This scanner checks document structure and selected active-content indicators only. It is not antivirus software and cannot certify a PDF as safe.",
        ])
        return "\n".join(lines).encode("utf-8"), "pdf-scan-report.txt"

    try:
        page_count = len(reader.pages)
    except Exception:
        page_count = 0
    lines.append(f"Pages: {page_count}")
    metadata = reader.metadata
    if metadata:
        for key, label in (("/Title", "Title"), ("/Author", "Author"), ("/Creator", "Creator"), ("/Producer", "Producer"), ("/CreationDate", "Creation date")):
            value = metadata.get(key)
            if value:
                lines.append(f"{label}: {str(value)[:180]}")

    root = reader.trailer.get("/Root")
    if hasattr(root, "get_object"):
        root = root.get_object()
    findings: list[str] = []
    if root and (root.get("/OpenAction") or root.get("/AA")):
        findings.append("The document catalog contains an OpenAction or additional-actions entry.")
    names = root.get("/Names") if root else None
    if hasattr(names, "get_object"):
        names = names.get_object()
    embedded_count = 0
    if names:
        embedded = names.get("/EmbeddedFiles")
        if hasattr(embedded, "get_object"):
            embedded = embedded.get_object()
        if embedded:
            name_array = embedded.get("/Names", [])
            embedded_count = len(name_array) // 2 if name_array else 0
        javascript = names.get("/JavaScript")
        if javascript:
            findings.append("A JavaScript name tree is present.")
    if embedded_count:
        findings.append(f"Embedded file entries detected: {embedded_count}.")

    action_counts: dict[str, int] = {}
    external_links = 0
    risky_schemes = 0
    try:
        for page in reader.pages:
            annotations = page.get("/Annots") or []
            for annotation_ref in annotations:
                annotation = annotation_ref.get_object() if hasattr(annotation_ref, "get_object") else annotation_ref
                action = annotation.get("/A") if annotation else None
                if hasattr(action, "get_object"):
                    action = action.get_object()
                if action:
                    action_type = str(action.get("/S", "Unknown"))
                    action_counts[action_type] = action_counts.get(action_type, 0) + 1
                    uri = str(action.get("/URI", ""))
                    if action_type == "/URI":
                        external_links += 1
                        if uri.lower().startswith(("javascript:", "file:", "data:")):
                            risky_schemes += 1
                    if action_type in {"/Launch", "/JavaScript", "/SubmitForm", "/ImportData"}:
                        findings.append(f"Potentially sensitive PDF action found: {action_type}.")
    except Exception:
        findings.append("Some page annotations could not be fully inspected.")

    lines.append(f"External URI links: {external_links}")
    lines.append(f"Unusual URI schemes: {risky_schemes}")
    if action_counts:
        lines.append("Annotation actions: " + ", ".join(f"{key}={value}" for key, value in sorted(action_counts.items())))
    if findings:
        lines.append("\nItems requiring manual review:")
        lines.extend(f"- {item}" for item in dict.fromkeys(findings))
    else:
        lines.append("No selected active-content indicators were found by these checks.")

    try:
        document = fitz.open(stream=data, filetype="pdf")
        if document.is_encrypted and password:
            document.authenticate(password)
        text_pages = sum(1 for page in document if page.get_text().strip())
        lines.append(f"Pages containing selectable text: {text_pages} / {len(document)}")
        document.close()
    except Exception:
        lines.append("Text-layer inspection: Unavailable.")
    lines.extend([
        "",
        "Interpretation: These are structural and heuristic checks only, not antivirus software or a malware scan. A clean report does not guarantee safety. Open files only from trusted sources and use endpoint security software for malware detection.",
    ])
    return "\n".join(lines).encode("utf-8"), "pdf-scan-report.txt"


def _lock_pdf(upload, password: str):
    data = read_pdf(upload)
    if len(password) < 8:
        raise ValueError("Use a PDF password with at least 8 characters.")
    reader = PdfReader(io.BytesIO(data), strict=False)
    if reader.is_encrypted:
        raise ValueError("This PDF is already password-protected. Unlock it before applying a new password.")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    try:
        writer.encrypt(user_password=password, algorithm="AES-256")
    except TypeError:
        writer.encrypt(user_password=password, use_128bit=True)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), "locked.pdf"


def _unlock_pdf(upload, password: str):
    data = read_pdf(upload)
    reader = PdfReader(io.BytesIO(data), strict=False)
    if reader.is_encrypted and not reader.decrypt(password):
        raise ValueError("Incorrect PDF password.")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), "unlocked.pdf"


def _convert_pdf_to_images(data: bytes):
    doc = fitz.open(stream=data, filetype="pdf")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, page in enumerate(doc):
            archive.writestr(
                f"page-{index + 1}.png",
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png"),
            )
    doc.close()
    return output.getvalue(), "pdf-pages-png.zip"


def _images_to_pdf(files):
    if not files:
        raise ValueError("Choose one or more images.")
    images = []
    try:
        for file_obj in files:
            if file_obj.size > MAX_SIZE:
                raise ValueError("Each image must be 25 MB or smaller.")
            try:
                image_data = _read_upload(file_obj)
                with Image.open(io.BytesIO(image_data)) as image:
                    image.verify()
                with Image.open(io.BytesIO(image_data)) as image:
                    images.append(image.convert("RGB"))
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("Use valid JPG, PNG or WebP images.") from exc
        if not images:
            raise ValueError("Choose at least one image.")
        output = io.BytesIO()
        images[0].save(output, format="PDF", save_all=True, append_images=images[1:])
        return output.getvalue(), "images-to-pdf.pdf"
    finally:
        for image in images:
            image.close()


def run_tool(tool: str, files, post):
    first = files[0] if files else None
    password = post.get("password", "")

    if tool == "encrypt-message":
        return encrypt_message(post.get("message", ""), password)
    if tool in {"lock-file"}:
        return encrypt_any_file(first, password)
    if tool == "unlock-file":
        return decrypt_any_file(first, password)
    if tool in {"encrypt-text", "text-locker"}:
        return encrypt_text_file(first, password)
    if tool in {"decrypt-text", "text-unlocker"}:
        return decrypt_text_file(first, password)
    if tool == "folder-locker":
        raise ValueError("Use the Windows Desktop Locker for click-to-open folder protection. A browser cannot replace a local Windows folder with a password shortcut.")
    if tool == "folder-unlocker":
        return decrypt_folder(first, password)
    if tool in {"protect", "pdf-locker"}:
        return _lock_pdf(first, password)
    if tool in {"unlock", "pdf-unlocker"}:
        return _unlock_pdf(first, password)
    if tool == "pdf-scanner":
        return pdf_scanner(first, password)
    if tool == "text-to-word":
        return text_to_word(first)
    if tool == "word-to-text":
        return word_to_text(first)
    if tool == "pdf-to-word":
        return pdf_to_word(first)
    if tool == "word-to-pdf":
        return word_to_pdf(first)
    if tool == "txt-to-pdf":
        return text_to_pdf(first)
    if tool == "html-to-pdf":
        return html_to_pdf(first)

    if tool == "merge":
        if len(files) < 2:
            raise ValueError("Select at least two PDF files.")
        writer = PdfWriter()
        for file_obj in files:
            for page in PdfReader(io.BytesIO(read_pdf(file_obj)), strict=False).pages:
                writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue(), "merged.pdf"
    if tool == "jpg-to-pdf":
        return _images_to_pdf(files)
    if tool in {"pdf-to-jpg", "extract-text", "pdf-to-html", "remove-pages", "page-numbers", "repair", "split", "compress", "rotate", "watermark"}:
        data = read_pdf(first)
        if tool == "pdf-to-jpg":
            return _convert_pdf_to_images(data)
        if tool == "extract-text":
            doc = fitz.open(stream=data, filetype="pdf")
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            return text.encode("utf-8"), "extracted-text.txt"
        if tool == "pdf-to-html":
            return pdf_to_html(first)
        if tool == "remove-pages":
            return remove_pages(first, post.get("pages", ""))
        if tool == "page-numbers":
            return add_page_numbers(first, post.get("position", "bottom"))
        if tool == "repair":
            return repair_pdf(first)
        if tool == "split":
            reader = PdfReader(io.BytesIO(data), strict=False)
            writer = PdfWriter()
            for page_number in parse_pages(post.get("pages", ""), len(reader.pages)):
                writer.add_page(reader.pages[page_number - 1])
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue(), "split-pages.pdf"
        if tool == "compress":
            doc = fitz.open(stream=data, filetype="pdf")
            result = doc.tobytes(garbage=4, deflate=True, clean=True)
            doc.close()
            return result, "compressed.pdf"
        if tool == "rotate":
            try:
                degrees = int(post.get("degrees", "90"))
            except ValueError as exc:
                raise ValueError("Choose 90, 180 or 270 degrees.") from exc
            if degrees not in (90, 180, 270):
                raise ValueError("Choose 90, 180 or 270 degrees.")
            doc = fitz.open(stream=data, filetype="pdf")
            for page in doc:
                page.set_rotation((page.rotation + degrees) % 360)
            result = doc.tobytes(garbage=4, deflate=True)
            doc.close()
            return result, "rotated.pdf"
        if tool == "watermark":
            label = post.get("watermark", "").strip()
            if not label:
                raise ValueError("Enter watermark text.")
            doc = fitz.open(stream=data, filetype="pdf")
            for page in doc:
                rect = page.rect
                page.insert_textbox(
                    fitz.Rect(rect.width * .1, rect.height * .43, rect.width * .9, rect.height * .57),
                    label[:100], fontsize=min(32, rect.width / 14), color=(.65, .65, .65), align=1,
                )
            result = doc.tobytes(garbage=4, deflate=True)
            doc.close()
            return result, "watermarked.pdf"
    raise ValueError("Unknown tool.")
