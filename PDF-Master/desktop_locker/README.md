# PDF Master Desktop Locker (Windows)

A Windows companion app for opening password-protected PDF Master containers from File Explorer.

## Folder Locker — double-click experience

1. Run `run_locker.bat`.
2. Choose **Lock a Folder**, pick the original folder and set a password (10+ characters).
3. Confirm the warning. PDF Master creates an encrypted AES-256-GCM `.pmlock` container inside a hidden `.PDFMasterVault` directory next to the selected folder.
4. The app authenticates and reconstructs the encrypted contents for verification before removing the original folder.
5. The original folder is replaced by a folder-icon Windows shortcut (`FolderName.lnk`) with the same base name. Double-click it in File Explorer; the password prompt opens. Windows may display the shortcut overlay or suffix depending on Explorer settings.
6. Enter the password to restore and open a working folder under `%LOCALAPPDATA%\PDFMaster\Unlocked`.
7. Close the files and use **Clear Unlocked Copies** when finished.

The visible item is a Windows shortcut, not a real directory. This is a shortcut-based password gate. It is not a Windows Explorer shell extension or a mounted encrypted drive. Windows does not expose a supported built-in way for a Python script to attach a custom password dialog to an arbitrary normal directory, so PDF Master swaps the directory for a `.lnk` shortcut after verifying its encrypted container.

**Important:** replacing the original uses ordinary filesystem deletion, not secure erasure. Deleted data may remain recoverable from disk, backups, sync tools or SSD wear-leveling. The unlocked working copy is plaintext until you clear it; closing the Explorer window does not automatically re-lock it.

## File Locker

Choose **Lock a File** to create a `.pmlock` container. To double-click `.pmlock` files directly in File Explorer, run `install_file_association.bat` once. The original file is preserved by default; remove it yourself only after confirming the protected copy works.

## Run from source

From the repository root, activate the project virtual environment and run:

```powershell
.\.venv\Scripts\Activate.ps1
python desktop_locker\locker.pyw
```

Or run `run_locker.bat` from the `desktop_locker` folder. Tkinter must be included with the Python installation (select Tcl/Tk during setup).

## Build standalone EXE

```powershell
cd desktop_locker
build_windows_exe.bat
```

The output is `desktop_locker\dist\PDFMasterLocker.exe`. The folder shortcut creator automatically prefers that executable when present; otherwise it launches `pythonw.exe` and the source script.

## Cryptography and format

- AES-256-GCM authenticated encryption.
- PBKDF2-HMAC-SHA256 with 600,000 iterations.
- Random per-container salt and nonce; authentication failure rejects wrong passwords and modified files.
- Symbolic links are skipped during folder packaging to avoid following external paths.
- Passwords are never stored. Forgotten passwords cannot be recovered.
- `.pmlock` is separate from the web app's older `.pmx`, `.pme` and `.pmf` formats.
