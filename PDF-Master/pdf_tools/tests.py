import io
import json
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from pypdf import PdfReader, PdfWriter

from .services import (
    decrypt_any_file,
    decrypt_folder,
    decrypt_text_file,
    encrypt_any_file,
    encrypt_folder,
    encrypt_message,
    encrypt_text_file,
    pdf_scanner,
    parse_pages,
    _lock_pdf,
    _unlock_pdf,
    text_to_word,
    word_to_text,
)


class DocumentServiceTests(SimpleTestCase):
    def test_parse_pages(self):
        self.assertEqual(parse_pages("1-3,5", 5), [1, 2, 3, 5])

    def test_text_locker_round_trip(self):
        source = SimpleUploadedFile("notes.txt", "hello PDF Master".encode(), content_type="text/plain")
        encrypted, encrypted_name = encrypt_text_file(source, "sample-password-123")
        self.assertEqual(encrypted_name, "encrypted-text.pmx")
        protected = SimpleUploadedFile("notes.pmx", encrypted)
        plain, output_name = decrypt_text_file(protected, "sample-password-123")
        self.assertEqual(plain, b"hello PDF Master")
        self.assertEqual(output_name, "decrypted-text.txt")

    def test_generic_file_locker_round_trip(self):
        source = SimpleUploadedFile("photo.png", b"image bytes")
        encrypted, _ = encrypt_any_file(source, "sample-password-123")
        protected = SimpleUploadedFile("protected.pme", encrypted)
        plain, name = decrypt_any_file(protected, "sample-password-123")
        self.assertEqual(plain, b"image bytes")
        self.assertEqual(name, "photo.png")

    def test_folder_locker_round_trip(self):
        files = [
            SimpleUploadedFile("hello.txt", b"hello"),
            SimpleUploadedFile("data.csv", b"a,b\n1,2"),
        ]
        manifest = json.dumps([
            {"index": 0, "path": "Project/hello.txt"},
            {"index": 1, "path": "Project/Reports/data.csv"},
        ])
        encrypted, _ = encrypt_folder(files, manifest, "sample-password-123")
        protected = SimpleUploadedFile("project.pmf", encrypted)
        archive_data, archive_name = decrypt_folder(protected, "sample-password-123")
        self.assertTrue(archive_name.endswith(".zip"))
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            self.assertEqual(archive.namelist(), ["Project/hello.txt", "Project/Reports/data.csv"])
            self.assertEqual(archive.read("Project/hello.txt"), b"hello")

    def test_text_word_round_trip(self):
        source = SimpleUploadedFile("notes.txt", "First line\nSecond line".encode())
        docx_data, _ = text_to_word(source)
        docx_upload = SimpleUploadedFile("converted.docx", docx_data)
        text_data, _ = word_to_text(docx_upload)
        self.assertIn(b"First line", text_data)
        self.assertIn(b"Second line", text_data)


    def test_pdf_locker_round_trip(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        source_buffer = io.BytesIO()
        writer.write(source_buffer)
        source = SimpleUploadedFile("blank.pdf", source_buffer.getvalue())
        locked, _ = _lock_pdf(source, "sample-password-123")
        locked_reader = PdfReader(io.BytesIO(locked))
        self.assertTrue(locked_reader.is_encrypted)
        self.assertTrue(bool(locked_reader.decrypt("sample-password-123")))
        unlocked, _ = _unlock_pdf(SimpleUploadedFile("locked.pdf", locked), "sample-password-123")
        self.assertEqual(len(PdfReader(io.BytesIO(unlocked)).pages), 1)

    def test_pdf_scanner_report(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        buffer = io.BytesIO()
        writer.write(buffer)
        upload = SimpleUploadedFile("blank.pdf", buffer.getvalue())
        report, filename = pdf_scanner(upload)
        self.assertEqual(filename, "pdf-scan-report.txt")
        self.assertIn(b"PDF MASTER", report)
        self.assertIn(b"not antivirus", report.lower())
