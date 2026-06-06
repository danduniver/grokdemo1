# Building RecipePDF for Windows

This document explains how to create a standalone `RecipePDF.exe` that runs on any modern Windows machine without Python installed.

## Prerequisites

- Windows 10/11 (64-bit)
- Python 3.11 or 3.12 or 3.14 installed (from python.org)
- Git (optional)

## Step-by-step Build

### 1. Clone / download the source

```powershell
cd C:\dev
git clone <your-repo> recipepdf
cd recipepdf
```

Or just unzip the source.

### 2. Create virtual environment & install deps

```powershell
python -m venv .venv
.\ .venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

### 3. (Recommended) Create a nice application icon

You can:
- Use any `.ico` file (256x256 recommended)
- Or generate one with an online tool or ImageMagick
- Place it at `assets\icon.ico`

For a quick placeholder you can skip the icon (the exe will use default Python icon).

### 4. Build with PyInstaller

We provide two easy options:

#### Option A: One-command build (recommended)

```powershell
python build.py
```

#### Option B: Manual PyInstaller command

```powershell
pyinstaller `
  --noconfirm `
  --onefile `
  --windowed `
  --name "RecipePDF" `
  --icon "assets/icon.ico" `
  --add-data "assets;assets" `
  --collect-all pymupdf `
  --hidden-import "fitz" `
  main.py
```

The `--collect-all pymupdf` is important because PyMuPDF has native DLLs and data files.

### 5. Find your executable

After successful build:

```
dist\
  RecipePDF.exe     ← This is your standalone app (80-150 MB)
```

You can copy `RecipePDF.exe` anywhere and run it.

## Creating an installer (optional)

If you want a proper installer (with Start Menu entry, uninstaller):

- Use [Inno Setup](https://jrsoftware.org/isinfo.php) (free)
- Or [NSIS](https://nsis.sourceforge.io/)

Example Inno Setup snippet is provided in `installer.iss` (create it if needed).

## Troubleshooting Common Build Issues

### "fitz / pymupdf not found in frozen app"

Add these flags:

```powershell
--collect-all pymupdf --collect-all fitz
```

### Large file size

This is normal. PyMuPDF + its fonts + the ML models it uses internally are big.

You can try `--onedir` instead of `--onefile` for slightly faster startup (creates a folder instead of single exe).

### Antivirus false positive

Some antivirus tools flag PyInstaller executables. This is a known ecosystem problem.

Solutions:
- Code sign the exe (requires certificate)
- Submit to Microsoft / Avast for whitelisting
- Use `--onedir` mode

### First run is slow

On first launch after indexing large PDFs it can take time. Subsequent runs are instant because results are cached in SQLite.

## Recommended PyInstaller spec file (advanced)

See `recipepdf.spec` example in the repo root for full control.

## Continuous Integration

You can set up GitHub Actions to automatically build the exe on every tag:

```yaml
# .github/workflows/build-windows.yml
```

(Example available upon request.)

---

You now have a professional Windows desktop application!
