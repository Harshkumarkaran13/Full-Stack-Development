# PDF Master

**PDF Master** is a full-stack document workspace built with **Django 6.1 + React 19 + Vite 8 + Tailwind CSS 4 + Motion for React**. It provides PDF utilities, document conversions, file protection and a separate Windows desktop locker. No public user registration is required.

> This is a portfolio / academic project. Review the deployment security checklist before exposing it to the public internet.

## Product features

### PDF tools
- Merge multiple PDFs and split selected pages.
- Best-effort compress and repair PDF structure.
- Rotate pages, add text watermarks and page numbers, and remove pages.
- Convert PDF pages to images and images to PDF.
- Extract PDF text; convert PDF to Word and PDF to HTML.
- Inspect document metadata, page text, annotations, embedded-file indicators and selected active-content indicators with PDF Scanner.
- Password-lock and unlock PDFs.

### Document conversions

| Conversion | Input | Output | Notes |
|---|---|---|---|
| Text to Word | `.txt` | `.docx` | UTF-8 text; source lines become paragraphs |
| Word to Text | `.docx` | `.txt` | Extracts paragraphs and tables |
| PDF to Word | `.pdf` | `.docx` | Best with text-based PDFs; complex layouts can change |
| Word to PDF | `.doc` / `.docx` | `.pdf` | Requires LibreOffice on the Django host |
| Text to PDF | `.txt` | `.pdf` | Plain-text layout |
| HTML to PDF | `.html` / `.htm` | `.pdf` | Requires LibreOffice on the Django host |
| PDF to HTML | `.pdf` | `.html` | Exports a text/layout representation |

### Security tools
- **PDF Locker:** applies native PDF password encryption.
- **Text Locker:** encrypts UTF-8 text files into `.pmx` containers.
- **Folder Locker (dashboard):** opens instructions for the Windows desktop shortcut workflow. It does not generate an encrypted download from the website.
- **File Locker (web):** encrypts arbitrary uploaded files into `.pme` containers.
- **Message Locker:** encrypts a typed message into `.pmx`.
- **Windows Desktop Locker:** creates a protected `.pmlock` container for files and folders.

Web-based file lockers create encrypted downloads because a website cannot directly replace local Windows folders or register File Explorer actions. The dashboard routes Folder Locker to the Windows companion for the requested double-click workflow: its **Lock Folder** action encrypts the folder, verifies the encrypted copy, removes the unprotected original by ordinary filesystem deletion, and replaces it with a folder-looking `.lnk` shortcut. Double-clicking that shortcut launches PDF Master Locker and asks for the password. The encrypted `.pmlock` file lives in a hidden `.PDFMasterVault` directory beside the shortcut.

**Security limitation:** this is a shortcut-based password gate, not a virtual filesystem or full-disk encryption. The source is removed using ordinary deletion, not secure erasure. After opening, a plaintext working copy exists under `%LOCALAPPDATA%\PDFMaster\Unlocked` until it is cleared. Do not treat this as a replacement for BitLocker, VeraCrypt, or an enterprise data-loss-prevention system.

## Technology stack

The dashboard uses a Figma-inspired component and spacing system with responsive layouts, animated transitions, hover states and reduced-motion support. It is implemented in React; it is not an exported Figma design file.


| Layer | Technology |
|---|---|
| Backend | Python 3.12+, Django 6.1, SQLite (default) |
| Frontend | React 19.3, Vite 8, Tailwind CSS 4 |
| Animation | Motion for React (`motion/react`) |
| Icons | Lucide React |
| PDF / documents | PyMuPDF, pypdf, Pillow, pdf2docx, python-docx |
| Encryption | cryptography (Fernet for web formats; AES-256-GCM for `.pmlock`) |
| Windows desktop | Tkinter + PowerShell shortcut creation |

## Requirements

- Python **3.12 or newer**
- Node.js **22.12 or newer** and npm
- Windows 10/11 for the Desktop Locker folder-shortcut workflow
- LibreOffice (optional; needed for Word-to-PDF and HTML-to-PDF)
- Modern Chromium-based browser recommended for browser folder selection

## Windows installation

### 1. Install Python and Node.js

Install Python 3.12+ and Node.js 22.12+. During Python setup, include Tcl/Tk so the desktop companion can use Tkinter. During Node setup, npm is included.

### 2. Install backend dependencies

Open the repository root (`pdf_master`) in VS Code. The easiest setup is to double-click `setup_windows.bat`; it creates the virtual environment, installs Python and React dependencies, builds the frontend and prepares the database. You can also run the manual commands below (do not type the `PS C:\...>` prompt):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py check
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install frontend dependencies and build React

Open a **second terminal** at the same repository root:

```powershell
cd frontend
npm install
npm run build
cd ..
```

The production React bundle is generated in `static/react/` and served by Django.

### 4. Start the website

Back in the repository root:

```powershell
python manage.py runserver
```

Then double-click `run_windows.bat` (or run `python manage.py runserver`) and open **http://127.0.0.1:8000/**.

### 5. Optional: run React in development mode

Keep Django running in one terminal. In another terminal:

```powershell
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173/**. Vite proxies API and download requests to Django on port 8000. The development origin is included in the local CSRF trusted-origin defaults.

## Windows Desktop Locker

1. Use the same `.venv` and install `requirements.txt`.
2. Run `desktop_locker\run_locker.bat` or `python desktop_locker\locker.pyw`.
3. Choose **Lock a Folder**, select a folder, and set a password.
4. Confirm the warning that the unprotected original will be removed after the encrypted copy is verified.
5. The folder is replaced in its original parent directory by a folder-icon shortcut with the same displayed name. Double-click it to enter the password.
6. After unlocking, the restored working folder opens in File Explorer. Use **Clear Unlocked Copies** after closing files when you want to remove plaintext working copies.

For individual `.pmlock` file containers, run `desktop_locker\install_file_association.bat` once to register double-click support. Folder shortcuts launch the companion directly and do not depend on that association. An optional standalone EXE can be built with `desktop_locker\build_windows_exe.bat`.

## macOS / Linux backend setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py check
cd frontend && npm install && npm run build && cd ..
python manage.py runserver
```

The Windows folder shortcut workflow is Windows-only.

## File handling and privacy

- Source uploads are limited to 25 MB; web Folder Locker applies a 25 MB combined limit and a 500-file limit.
- Recent processing records and download endpoints are scoped to the current Django session.
- Processed outputs are stored under `media/processed/`; automatic retention cleanup is not implemented yet.
- Self-host sensitive documents only on infrastructure you control. Use HTTPS in production and private media storage.
- Web `.pmx`, `.pme`, and `.pmf` formats are separate from desktop `.pmlock`. Keep passwords safe; lost passwords cannot be recovered.

## Known limitations

- PDF-to-Word is not a perfect layout-preserving conversion. Image-only scanned PDFs require OCR, which is not included.
- PDF Scanner performs structural/heuristic inspection only. It is not antivirus software and cannot certify a document as safe.
- Compression is best-effort and may not reduce every PDF.
- Text-to-PDF uses a simple layout, not a full word processor.
- Word-to-Text accepts `.docx`; Word-to-PDF accepts `.doc` and `.docx` through LibreOffice.
- Desktop Locker's unlocked working copies remain in the user's profile until manually cleared. Closing File Explorer does not automatically re-encrypt that working copy.
- Ordinary deletion does not guarantee physical erasure on SSDs, journaled filesystems, cloud-synced drives or backups.

## GitHub publishing checklist

1. Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False` and `DJANGO_ALLOWED_HOSTS` in the deployment environment.
2. Configure HTTPS, secure cookies, production static serving and private media storage.
3. Add upload throttling, server-side retention cleanup and operational monitoring.
4. Configure backups and a production database where appropriate.
5. Run `python manage.py check --deploy` with deployment settings.
6. Do not commit private documents, vault containers, unlocked copies, `.env`, local database files or user secrets.

## GitHub commands

```bash
git init
git add .
git commit -m "Build PDF Master document workspace"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

GitHub Actions runs Python tests, Django checks, the desktop container tests and the React production build.

## License

Add a license before accepting contributions or redistributing this project. No license is assumed by this repository template.
