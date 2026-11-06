"""Password-protected PDF Master desktop locker container format.

A .pmlock file is an authenticated AES-256-GCM encrypted ZIP payload.
The custom format is intentionally separate from the web app's legacy .pmx/.pme/.pmf files.
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Literal

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"PMLOCK01"  # 8 bytes
ITERATIONS = 600_000
SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
CHUNK_SIZE = 1024 * 1024
HEADER_SIZE = len(MAGIC) + 4 + SALT_SIZE + NONCE_SIZE
MANIFEST_NAME = ".pdfmaster-manifest.json"
SUPPORTED_KIND = ("file", "folder")


class LockerError(Exception):
    """Raised for invalid containers, passwords, or unsupported source paths."""


def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    if not isinstance(password, str) or len(password) < 10:
        raise LockerError("Use a password with at least 10 characters.")
    if iterations < 100_000 or iterations > 5_000_000:
        raise LockerError("The protected item uses an unsupported security setting.")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(password.encode("utf-8"))


def _safe_basename(value: str) -> str:
    name = Path(value).name.strip().replace("\x00", "")
    if name in {"", ".", ".."} or name.startswith(".") and name == MANIFEST_NAME:
        raise LockerError("The protected item has an invalid name.")
    if ":" in name or "/" in name or "\\" in name:
        raise LockerError("The protected item has an invalid name.")
    return name


def _compression_for(path: Path) -> int:
    # Avoid wasting CPU on formats that are generally already compressed.
    if path.suffix.lower() in {
        ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".m4v",
        ".mov", ".avi", ".mkv", ".mp3", ".aac", ".ogg", ".zip", ".7z", ".rar",
        ".gz", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp",
    }:
        return zipfile.ZIP_STORED
    return zipfile.ZIP_DEFLATED


def _make_zip(source: Path, zip_path: Path) -> tuple[Literal["file", "folder"], str, int]:
    if not source.exists():
        raise LockerError("The selected file or folder no longer exists.")
    if source.is_symlink():
        raise LockerError("Symbolic links cannot be locked.")

    skipped_symlinks = 0
    if source.is_file():
        kind: Literal["file", "folder"] = "file"
        name = _safe_basename(source.name)
        with zipfile.ZipFile(zip_path, "w", allowZip64=True) as archive:
            manifest = {"format": 1, "kind": kind, "name": name}
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False))
            archive.write(source, f"payload/{name}", compress_type=_compression_for(source))
    elif source.is_dir():
        kind = "folder"
        name = _safe_basename(source.name)
        with zipfile.ZipFile(zip_path, "w", allowZip64=True) as archive:
            manifest = {"format": 1, "kind": kind, "name": name}
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False))
            archive.writestr(f"payload/{name}/", "")
            for current, dirnames, filenames in os.walk(source, followlinks=False):
                current_path = Path(current)
                kept_dirs = []
                for dirname in dirnames:
                    child = current_path / dirname
                    if child.is_symlink():
                        skipped_symlinks += 1
                    else:
                        kept_dirs.append(dirname)
                        rel_dir = child.relative_to(source.parent).as_posix()
                        archive.writestr(f"payload/{rel_dir}/", "")
                dirnames[:] = kept_dirs
                for filename in filenames:
                    child = current_path / filename
                    if child.is_symlink():
                        skipped_symlinks += 1
                        continue
                    rel_file = child.relative_to(source.parent).as_posix()
                    archive.write(child, f"payload/{rel_file}", compress_type=_compression_for(child))
    else:
        raise LockerError("Choose a regular file or folder.")
    return kind, name, skipped_symlinks


def _encrypt_zip(zip_path: Path, output_path: Path, password: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    iterations_bytes = struct.pack(">I", ITERATIONS)
    header = MAGIC + iterations_bytes + salt + nonce
    key = _derive_key(password, salt, ITERATIONS)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = output_path.with_name(output_path.name + ".partial")
    try:
        with zip_path.open("rb") as source, partial_path.open("wb") as target:
            target.write(header)
            while True:
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                encrypted = encryptor.update(chunk)
                if encrypted:
                    target.write(encrypted)
            final = encryptor.finalize()
            if final:
                target.write(final)
            target.write(encryptor.tag)
            target.flush()
            os.fsync(target.fileno())
        os.replace(partial_path, output_path)
    except Exception:
        try:
            partial_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def create_lock_container(source_path: str | Path, output_path: str | Path, password: str) -> dict:
    """Create an authenticated .pmlock container from one file or one folder."""
    source = Path(source_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".pmlock":
        raise LockerError("The protected container must use the .pmlock extension.")
    if source == output:
        raise LockerError("The output cannot replace the source item.")
    if source.is_dir():
        try:
            output.relative_to(source)
            raise LockerError("Save the .pmlock file outside the folder being protected.")
        except ValueError:
            pass
    # Verify password policy before doing potentially expensive archive work.
    _derive_key(password, os.urandom(SALT_SIZE), ITERATIONS)
    with tempfile.TemporaryDirectory(prefix="pdfmaster-lock-") as temp_dir:
        zip_path = Path(temp_dir) / "payload.zip"
        kind, name, skipped = _make_zip(source, zip_path)
        _encrypt_zip(zip_path, output, password)
    return {"kind": kind, "name": name, "skipped_symlinks": skipped, "container": str(output)}


def _decrypt_to_zip(container: Path, zip_path: Path, password: str) -> None:
    try:
        with container.open("rb") as source:
            header = source.read(HEADER_SIZE)
            if len(header) != HEADER_SIZE or header[:8] != MAGIC:
                raise LockerError("This is not a valid PDF Master .pmlock container.")
            iterations = struct.unpack(">I", header[8:12])[0]
            salt = header[12:12 + SALT_SIZE]
            nonce = header[12 + SALT_SIZE:HEADER_SIZE]
            file_size = os.fstat(source.fileno()).st_size
            if file_size < HEADER_SIZE + TAG_SIZE:
                raise LockerError("The protected item is incomplete or damaged.")
            source.seek(-TAG_SIZE, os.SEEK_END)
            tag = source.read(TAG_SIZE)
            ciphertext_length = file_size - HEADER_SIZE - TAG_SIZE
            source.seek(HEADER_SIZE)
            key = _derive_key(password, salt, iterations)
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            remaining = ciphertext_length
            with zip_path.open("wb") as target:
                while remaining:
                    chunk = source.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise LockerError("The protected item is incomplete or damaged.")
                    remaining -= len(chunk)
                    plain = decryptor.update(chunk)
                    if plain:
                        target.write(plain)
                final = decryptor.finalize()  # Raises InvalidTag for a wrong password/tampering.
                if final:
                    target.write(final)
    except InvalidTag as exc:
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise LockerError("Incorrect password, or the protected file has been modified.") from exc
    except Exception:
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _validate_member(info: zipfile.ZipInfo, destination: Path) -> Path:
    raw = info.filename.replace("\\", "/")
    member = PurePosixPath(raw)
    if member.is_absolute() or any(part in {"..", ""} for part in member.parts):
        raise LockerError("The protected archive contains an unsafe path.")
    if member.parts and ":" in member.parts[0]:
        raise LockerError("The protected archive contains an unsafe path.")
    # Reject symbolic links in the archive.
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    if (unix_mode & 0o170000) == 0o120000:
        raise LockerError("Symbolic links are not supported in protected folders.")
    target = (destination / Path(*member.parts)).resolve()
    root = destination.resolve()
    if target != root and root not in target.parents:
        raise LockerError("The protected archive contains an unsafe path.")
    return target


def unlock_container(container_path: str | Path, password: str, cache_root: str | Path | None = None) -> Path:
    """Decrypt and extract a container into the app's managed unlocked-copy directory.

    The caller should open the returned path with the operating system's default app.
    The returned plaintext copy remains until manually removed or cleared in the app.
    """
    container = Path(container_path).expanduser().resolve()
    if not container.is_file():
        raise LockerError("The selected .pmlock file could not be found.")
    if cache_root is None:
        local_app_data = os.environ.get("LOCALAPPDATA")
        cache_root = Path(local_app_data) / "PDFMaster" / "Unlocked" if local_app_data else Path.home() / ".pdfmaster" / "Unlocked"
    cache_root = Path(cache_root).expanduser().resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    work_dir = cache_root / f"{container.stem}-{uuid.uuid4().hex[:8]}"
    payload_dir = work_dir / "payload"
    work_dir.mkdir(parents=True, exist_ok=False)
    zip_path = work_dir / "decrypted-payload.zip"
    try:
        _decrypt_to_zip(container, zip_path, password)
        with zipfile.ZipFile(zip_path, "r") as archive:
            names = set(archive.namelist())
            if MANIFEST_NAME not in names:
                raise LockerError("The protected item is missing its manifest.")
            try:
                manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LockerError("The protected item has an invalid manifest.") from exc
            kind = manifest.get("kind")
            name = _safe_basename(str(manifest.get("name", "")))
            if manifest.get("format") != 1 or kind not in SUPPORTED_KIND:
                raise LockerError("This .pmlock format version is not supported.")
            payload_dir.mkdir(parents=True, exist_ok=True)
            for info in archive.infolist():
                if info.filename == MANIFEST_NAME:
                    continue
                target = _validate_member(info, work_dir)
                if not info.filename.startswith("payload/"):
                    raise LockerError("The protected archive contains an unexpected entry.")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=CHUNK_SIZE)
        zip_path.unlink(missing_ok=True)
        if kind == "file":
            output = payload_dir / name
        else:
            output = payload_dir / name
        if not output.exists():
            raise LockerError("The protected item could not be reconstructed.")
        return output
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
