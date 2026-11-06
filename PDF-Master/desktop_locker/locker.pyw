"""Windows desktop interface for opening PDF Master .pmlock containers."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from container_format import LockerError, create_lock_container, unlock_container

APP_DIR = Path(__file__).resolve().parent


def _default_cache() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "PDFMaster" / "Unlocked" if base else Path.home() / ".pdfmaster" / "Unlocked"


class PDFMasterLocker(tk.Tk):
    def __init__(self, open_path: str | None = None):
        super().__init__()
        self.title("PDF Master Locker")
        self.geometry("620x430")
        self.minsize(560, 390)
        self.configure(bg="#101827")
        self._style()
        self.delete_original = tk.BooleanVar(value=False)
        self._build()
        if open_path:
            self.after(250, lambda: self.open_container(Path(open_path)))

    def _style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#101827")
        style.configure("TLabel", background="#101827", foreground="#e5edf7", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#ffffff")
        style.configure("Sub.TLabel", foreground="#9fb0c5", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(14, 11))
        style.configure("Primary.TButton", background="#2563eb", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure("TCheckbutton", background="#101827", foreground="#dbe6f3")

    def _build(self):
        outer = ttk.Frame(self, padding=28)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="PDF MASTER", style="Sub.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Desktop Locker", style="Title.TLabel").pack(anchor="w", pady=(3, 4))
        ttk.Label(
            outer,
            text="Protect files and folders in an encrypted vault. Files use .pmlock containers; folders become clickable Windows shortcuts that ask for a password.",
            style="Sub.TLabel", wraplength=540,
        ).pack(anchor="w", pady=(0, 22))

        cards = ttk.Frame(outer)
        cards.pack(fill="x")
        ttk.Button(cards, text="Lock a File", style="Primary.TButton", command=self.lock_file).pack(fill="x", pady=5)
        ttk.Button(cards, text="Lock a Folder", style="Primary.TButton", command=self.lock_folder).pack(fill="x", pady=5)
        ttk.Button(cards, text="Open Protected Item (.pmlock)", command=self.choose_container).pack(fill="x", pady=5)
        ttk.Checkbutton(
            outer,
            text="Delete the original FILE after successful locking (ordinary deletion; not secure erasure)",
            variable=self.delete_original,
        ).pack(anchor="w", pady=(13, 6))
        ttk.Label(
            outer,
            text="Folder locking replaces the original folder with a shortcut after encryption is verified. Unlocked working copies remain until you clear them below.",
            style="Sub.TLabel", wraplength=540,
        ).pack(anchor="w", pady=(3, 14))
        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", side="bottom")
        ttk.Button(bottom, text="Clear Unlocked Copies", command=self.clear_cache).pack(side="left")
        ttk.Label(bottom, text="AES-256-GCM · PBKDF2-SHA256", style="Sub.TLabel").pack(side="right")

    def _lock(self, source: Path):
        password = simpledialog.askstring("Create password", "Create a password (minimum 10 characters):", show="*", parent=self)
        if password is None:
            return
        if len(password) < 10:
            messagebox.showerror("Password too short", "Use at least 10 characters.", parent=self)
            return
        confirm = simpledialog.askstring("Confirm password", "Enter the password again:", show="*", parent=self)
        if confirm is None:
            return
        if password != confirm:
            messagebox.showerror("Passwords do not match", "The two passwords are different.", parent=self)
            return
        suggested = source.name + ".pmlock"
        output_name = filedialog.asksaveasfilename(
            parent=self, title="Save protected container", initialdir=str(source.parent),
            initialfile=suggested, defaultextension=".pmlock",
            filetypes=[("PDF Master protected item", "*.pmlock")],
        )
        if not output_name:
            return
        output = Path(output_name)
        try:
            result = create_lock_container(source, output, password)
            deleted_note = ""
            if self.delete_original.get():
                remove = messagebox.askyesno(
                    "Remove original?",
                    f"The encrypted container was created successfully.\n\nRemove the original source?\n{source}\n\nThis uses normal file deletion, not forensic secure erasure.",
                    icon="warning", parent=self,
                )
                if remove:
                    if source.is_dir():
                        shutil.rmtree(source)
                    else:
                        source.unlink()
                    deleted_note = "\nThe original source was removed."
            skipped = result["skipped_symlinks"]
            skipped_note = f"\nSkipped symbolic links: {skipped}" if skipped else ""
            messagebox.showinfo(
                "Protected item created",
                f"Created: {output}\n\nThe .pmlock file is the protected item. Double-click it to enter the password and open a working copy.{deleted_note}{skipped_note}",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Could not lock item", str(exc), parent=self)

    def lock_file(self):
        filename = filedialog.askopenfilename(parent=self, title="Choose a file to protect", filetypes=[("All files", "*.*")])
        if filename:
            self._lock(Path(filename))

    def _create_folder_shortcut(self, source: Path, container: Path) -> Path:
        # Create a Windows Explorer shortcut that launches the password prompt.
        if os.name != "nt":
            raise RuntimeError("Folder shortcuts that open from Windows File Explorer are available on Windows only.")
        shortcut = source.with_name(source.name + ".lnk")
        if shortcut.exists():
            raise FileExistsError(f"A shortcut already exists at: {shortcut}")

        # Launch the packaged executable when present; otherwise launch pythonw + this script.
        packaged = APP_DIR / "dist" / "PDFMasterLocker.exe"
        if getattr(sys, "frozen", False):
            target = Path(sys.executable)
            arguments = subprocess.list2cmdline([str(container)])
            working_dir = target.parent
        elif packaged.is_file():
            target = packaged
            arguments = subprocess.list2cmdline([str(container)])
            working_dir = packaged.parent
        else:
            python_exe = Path(sys.executable)
            pythonw = python_exe.with_name("pythonw.exe")
            target = pythonw if pythonw.exists() else python_exe
            arguments = subprocess.list2cmdline([str(APP_DIR / "locker.pyw"), str(container)])
            working_dir = APP_DIR

        # Use environment variables to avoid PowerShell string interpolation of user paths.
        ps_script = r'''$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($env:PM_SHORTCUT_PATH)
$link.TargetPath = $env:PM_SHORTCUT_TARGET
$link.Arguments = $env:PM_SHORTCUT_ARGS
$link.WorkingDirectory = $env:PM_SHORTCUT_WORKDIR
$link.IconLocation = "$env:SystemRoot\System32\shell32.dll,3"
$link.Description = 'Password-protected folder - PDF Master'
$link.Save()
'''
        env = os.environ.copy()
        env.update({
            "PM_SHORTCUT_PATH": str(shortcut),
            "PM_SHORTCUT_TARGET": str(target),
            "PM_SHORTCUT_ARGS": arguments,
            "PM_SHORTCUT_WORKDIR": str(working_dir),
        })
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, env=env, check=False,
        )
        if completed.returncode != 0 or not shortcut.is_file():
            shortcut.unlink(missing_ok=True)
            detail = (completed.stderr or completed.stdout or "Windows could not create the folder shortcut.").strip()
            raise RuntimeError(detail[:500])
        return shortcut

    def lock_folder(self):
        folder = filedialog.askdirectory(parent=self, title="Choose a folder to protect", mustexist=True)
        if not folder:
            return
        source = Path(folder).resolve()
        if source.parent == source:
            messagebox.showerror("Cannot lock drive root", "Choose a folder inside the drive, not the drive root.", parent=self)
            return
        password = simpledialog.askstring(
            "Create folder password",
            f"Create a password for '{source.name}' (minimum 10 characters):",
            show="*", parent=self,
        )
        if password is None:
            return
        if len(password) < 10:
            messagebox.showerror("Password too short", "Use at least 10 characters.", parent=self)
            return
        confirm = simpledialog.askstring("Confirm password", "Enter the folder password again:", show="*", parent=self)
        if confirm is None:
            return
        if password != confirm:
            messagebox.showerror("Passwords do not match", "The two passwords are different.", parent=self)
            return

        warning = (
            "PDF Master will encrypt this folder, verify the encrypted copy, and replace the original folder "
            "with a clickable Windows shortcut that asks for your password.\n\n"
            f"Folder: {source}\n\n"
            "The unprotected original must be removed for the shortcut to protect access. This is ordinary "
            "file deletion, NOT forensic secure erasure; old data may remain recoverable from disk.\n\n"
            "After unlocking, a decrypted working copy remains in your Windows user profile until you clear it.\n\n"
            "Continue?"
        )
        if not messagebox.askyesno("Replace folder with password shortcut?", warning, icon="warning", parent=self):
            return

        vault_dir = source.parent / ".PDFMasterVault"
        container = vault_dir / f"{source.name}.pmlock"
        shortcut = source.with_name(source.name + ".lnk")
        if shortcut.exists():
            messagebox.showerror("Shortcut already exists", f"Remove or rename this existing shortcut first:\n{shortcut}", parent=self)
            return
        if container.exists():
            messagebox.showerror("Protected item already exists", f"A vault item already exists:\n{container}\n\nRename or remove it before locking this folder again.", parent=self)
            return

        try:
            vault_dir.mkdir(parents=True, exist_ok=True)
            # Hide the encrypted vault folder in Windows Explorer; its contents remain ciphertext.
            subprocess.run(["attrib", "+h", str(vault_dir)], capture_output=True, check=False)
            create_lock_container(source, container, password)

            # Verify the container can be authenticated and reconstructed before touching the source.
            with tempfile.TemporaryDirectory(prefix="pdfmaster-verify-") as verify_dir:
                restored = unlock_container(container, password, Path(verify_dir) / "verify-cache")
                if not restored.is_dir():
                    raise LockerError("The encrypted folder failed verification.")

            self._create_folder_shortcut(source, container)
            try:
                shutil.rmtree(source)
            except Exception:
                shortcut.unlink(missing_ok=True)
                raise

            messagebox.showinfo(
                "Folder locked",
                f"Your folder is now represented by a password-protected shortcut:\n\n{shortcut}\n\n"
                "Double-click that folder shortcut in File Explorer to enter the password.\n\n"
                f"Encrypted vault: {container}\n\n"
                "When unlocked, the restored working folder opens in File Explorer. Clear unlocked copies "
                "from PDF Master after you finish using the files.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Could not lock folder",
                f"{exc}\n\nIf the encrypted .pmlock file was created, your original folder has been left in place unless the success message appeared.",
                parent=self,
            )

    def choose_container(self):
        filename = filedialog.askopenfilename(
            parent=self, title="Open protected item", filetypes=[("PDF Master protected item", "*.pmlock")]
        )
        if filename:
            self.open_container(Path(filename))

    def open_container(self, container: Path):
        if not container.is_file():
            messagebox.showerror("File not found", f"Cannot find:\n{container}", parent=self)
            return
        password = simpledialog.askstring(
            "Password required", f"Enter the password to open:\n{container.name}", show="*", parent=self
        )
        if password is None:
            return
        try:
            unlocked_path = unlock_container(container, password, _default_cache())
            if os.name == "nt":
                os.startfile(str(unlocked_path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(unlocked_path)])
            else:
                subprocess.Popen(["xdg-open", str(unlocked_path)])
            messagebox.showinfo(
                "Item unlocked",
                f"Opened a decrypted working copy.\n\nLocation:\n{unlocked_path}\n\nDelete this copy when you no longer need it, or use Clear Unlocked Copies.",
                parent=self,
            )
        except LockerError as exc:
            messagebox.showerror("Unable to unlock", str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror("Unable to open item", str(exc), parent=self)

    def clear_cache(self):
        cache = _default_cache()
        if not cache.exists():
            messagebox.showinfo("No unlocked copies", "There are no unlocked copies to clear.", parent=self)
            return
        if not messagebox.askyesno(
            "Clear unlocked copies?",
            f"This permanently removes the PDF Master unlocked working-copy folder:\n\n{cache}\n\nClose documents opened from this folder first. Continue?",
            icon="warning", parent=self,
        ):
            return
        try:
            shutil.rmtree(cache)
            messagebox.showinfo("Completed", "Unlocked working copies were removed.", parent=self)
        except Exception as exc:
            messagebox.showerror("Could not clear copies", f"Close any files using this folder and try again.\n\n{exc}", parent=self)


def main():
    open_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = PDFMasterLocker(open_path)
    app.mainloop()


if __name__ == "__main__":
    main()
