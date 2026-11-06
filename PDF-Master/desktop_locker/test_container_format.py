"""Portable tests for the .pmlock container implementation."""
import tempfile
import unittest
from pathlib import Path

from container_format import LockerError, create_lock_container, unlock_container


class ContainerFormatTests(unittest.TestCase):
    def test_file_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "notes.txt"
            source.write_text("Confidential note\nSecond line", encoding="utf-8")
            container = root / "notes.txt.pmlock"
            create_lock_container(source, container, "a-long-example-password")
            self.assertTrue(container.exists())
            restored = unlock_container(container, "a-long-example-password", root / "cache")
            self.assertEqual(restored.name, "notes.txt")
            self.assertEqual(restored.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))

    def test_folder_round_trip_with_nested_and_empty_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Private Folder"
            (source / "nested").mkdir(parents=True)
            (source / "empty").mkdir()
            (source / "top.txt").write_text("top", encoding="utf-8")
            (source / "nested" / "inside.txt").write_text("inside", encoding="utf-8")
            container = root / "Private Folder.pmlock"
            create_lock_container(source, container, "a-long-example-password")
            restored = unlock_container(container, "a-long-example-password", root / "cache")
            self.assertTrue((restored / "top.txt").is_file())
            self.assertEqual((restored / "nested" / "inside.txt").read_text(encoding="utf-8"), "inside")
            self.assertTrue((restored / "empty").is_dir())

    def test_wrong_password_is_rejected_and_no_plaintext_is_left(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "secret.txt"
            source.write_text("do not expose", encoding="utf-8")
            container = root / "secret.pmlock"
            create_lock_container(source, container, "a-long-example-password")
            cache = root / "cache"
            with self.assertRaisesRegex(LockerError, "Incorrect password"):
                unlock_container(container, "incorrect-password", cache)
            self.assertFalse(cache.exists() and any(cache.iterdir()))

    def test_modified_container_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "secret.txt"
            source.write_text("integrity matters", encoding="utf-8")
            container = root / "secret.pmlock"
            create_lock_container(source, container, "a-long-example-password")
            data = bytearray(container.read_bytes())
            data[-1] ^= 0x01
            container.write_bytes(data)
            with self.assertRaisesRegex(LockerError, "Incorrect password"):
                unlock_container(container, "a-long-example-password", root / "cache")

    def test_requires_pmlock_extension(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "secret.txt"
            source.write_text("secret", encoding="utf-8")
            with self.assertRaisesRegex(LockerError, "must use the .pmlock extension"):
                create_lock_container(source, root / "secret.enc", "a-long-example-password")


if __name__ == "__main__":
    unittest.main(verbosity=2)
