from django.core.files.base import ContentFile
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import ProcessedFile
from .services import run_tool

TOOLS = {
    "merge": ("Merge PDF", "Combine multiple PDF documents into one file.", "multiple"),
    "split": ("Split PDF", "Extract selected pages, such as 1-3,5.", "single"),
    "compress": ("Compress PDF", "Optimize the PDF structure. File-size reduction depends on the source PDF.", "single"),
    "rotate": ("Rotate PDF", "Rotate pages by 90, 180 or 270 degrees.", "single"),
    "watermark": ("Add Watermark", "Stamp custom text onto every page.", "single"),
    "page-numbers": ("Add Page Numbers", "Add sequential page numbers to the top or bottom of each page.", "single"),
    "remove-pages": ("Remove PDF Pages", "Remove selected pages from a PDF document.", "single"),
    "repair": ("Repair PDF", "Rewrite and validate the PDF structure where possible.", "single"),
    "pdf-locker": ("PDF Locker", "Encrypt a PDF with a password using PDF document encryption.", "single"),
    "pdf-unlocker": ("PDF Unlocker", "Remove PDF password protection when you know the password.", "single"),
    "pdf-scanner": ("PDF Scanner", "Inspect PDF metadata, page text and selected active-content indicators. This is not antivirus software.", "single"),
    "pdf-to-jpg": ("PDF to Images", "Convert PDF pages into PNG images in a ZIP archive.", "single"),
    "jpg-to-pdf": ("Images to PDF", "Combine JPG, PNG or WebP images into one PDF.", "multiple"),
    "extract-text": ("PDF to Text", "Extract selectable text from a PDF into a TXT file.", "single"),
    "pdf-to-word": ("PDF to Word", "Convert a text-based PDF into an editable Word document (.docx).", "single"),
    "word-to-pdf": ("Word to PDF", "Convert a Word document (.docx or .doc) into a PDF.", "single"),
    "text-to-word": ("Text to Word", "Convert a UTF-8 TXT file into an editable Word document (.docx).", "single"),
    "word-to-text": ("Word to Text", "Extract paragraphs and tables from a .docx file into TXT.", "single"),
    "txt-to-pdf": ("Text to PDF", "Turn a UTF-8 text file into a PDF document.", "single"),
    "pdf-to-html": ("PDF to HTML", "Export PDF page content into an HTML document.", "single"),
    "html-to-pdf": ("HTML to PDF", "Convert an HTML document into a PDF using LibreOffice.", "single"),
    "text-locker": ("Text Locker", "Encrypt a UTF-8 text file into a password-protected .pmx file.", "single"),
    "text-unlocker": ("Text Unlocker", "Decrypt a PDF Master .pmx text container with its password.", "single"),
    "folder-locker": ("Folder Locker", "Use the Windows desktop companion to create a folder-shaped shortcut that prompts for a password when double-clicked.", "desktop"),
    "folder-unlocker": ("Folder Unlocker", "Restore a protected folder as a ZIP archive that you can extract locally.", "single"),
    "lock-file": ("Protect Any File", "Password-encrypt images, videos, audio, documents and other files.", "single"),
    "unlock-file": ("Unlock Any File", "Restore a PDF Master protected file using its password.", "single"),
    "encrypt-message": ("Encrypt a Message", "Type a private message and encrypt it into a downloadable .pmx file.", "message"),
    # Backward-compatible routes retained for existing users and bookmarks.
    "protect": ("Protect PDF", "Encrypt a PDF with a password.", "single"),
    "unlock": ("Unlock PDF", "Remove password protection when you know the password.", "single"),
    "encrypt-text": ("Encrypt Text File", "Lock a text file with password-based authenticated encryption.", "single"),
    "decrypt-text": ("Decrypt Text File", "Unlock a PDF Master encrypted text file.", "single"),
}


def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


@ensure_csrf_cookie
def home(request):
    _ensure_session(request)
    return render(request, "spa.html")


@ensure_csrf_cookie
def tool_page(request, tool):
    if tool not in TOOLS:
        return render(request, "404.html", status=404)
    _ensure_session(request)
    return render(request, "spa.html")


@ensure_csrf_cookie
def history(request):
    _ensure_session(request)
    return render(request, "spa.html")


@require_GET
@ensure_csrf_cookie
def api_bootstrap(request):
    session_key = _ensure_session(request)
    recent = ProcessedFile.objects.filter(session_key=session_key).order_by("-created_at")[:5]
    return JsonResponse({
        "tools": [
            {"slug": slug, "name": details[0], "description": details[1], "mode": details[2]}
            for slug, details in TOOLS.items()
        ],
        "recent": [_serialize_record(record) for record in recent],
    })


@require_GET
def api_history(request):
    session_key = _ensure_session(request)
    records = ProcessedFile.objects.filter(session_key=session_key).order_by("-created_at")[:100]
    return JsonResponse({"records": [_serialize_record(record) for record in records]})


def _serialize_record(record):
    tool_name = TOOLS.get(record.tool, (record.tool, "", "single"))[0]
    return {
        "id": record.pk,
        "tool": record.tool,
        "tool_name": tool_name,
        "original_name": record.original_name,
        "filename": record.output_file.name.rsplit("/", 1)[-1],
        "created_at": record.created_at.isoformat(),
        "download_url": f"/download/{record.pk}/",
    }


@require_POST
def api_process_tool(request, tool):
    if tool not in TOOLS:
        return JsonResponse({"error": "Unknown tool."}, status=404)
    session_key = _ensure_session(request)
    files = request.FILES.getlist("files")
    try:
        data, filename = run_tool(tool, files, request.POST)
        record = ProcessedFile(
            tool=tool,
            original_name=", ".join(file.name for file in files)[:255] or filename,
            session_key=session_key,
        )
        record.output_file.save(filename, ContentFile(data), save=True)
        return JsonResponse({
            "id": record.pk,
            "filename": record.output_file.name.rsplit("/", 1)[-1],
            "download_url": f"/download/{record.pk}/",
            "tool_name": TOOLS[tool][0],
        })
    except (ValueError, TypeError, OSError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        # Never expose server paths or internal tracebacks to the browser.
        return JsonResponse({
            "error": "Processing failed. Confirm the file is valid and required conversion software is installed."
        }, status=400)


@require_POST
def process_tool(request, tool):
    # Legacy server-rendered form endpoint retained for older bookmarks.
    if tool not in TOOLS:
        return render(request, "404.html", status=404)
    session_key = _ensure_session(request)
    files = request.FILES.getlist("files")
    try:
        data, filename = run_tool(tool, files, request.POST)
        record = ProcessedFile(
            tool=tool,
            original_name=", ".join(file.name for file in files)[:255] or filename,
            session_key=session_key,
        )
        record.output_file.save(filename, ContentFile(data), save=True)
        return render(request, "result.html", {"record": record, "tool_name": TOOLS[tool][0]})
    except (ValueError, TypeError, OSError) as exc:
        return render(request, "tool.html", {"tool": tool, "info": TOOLS[tool], "error": str(exc)}, status=400)
    except Exception:
        return render(request, "tool.html", {
            "tool": tool,
            "info": TOOLS[tool],
            "error": "Processing failed. Confirm the file is valid and the required conversion software is installed.",
        }, status=400)

def download_file(request, file_id):
    session_key = _ensure_session(request)
    record = get_object_or_404(ProcessedFile, pk=file_id, session_key=session_key)
    return FileResponse(
        record.output_file.open("rb"),
        as_attachment=True,
        filename=record.output_file.name.rsplit("/", 1)[-1],
    )
