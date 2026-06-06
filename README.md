# grokdemo1 — RecipePDF

**Search your PDF cookbooks. Discover recipes instantly.**

A beautiful, fast, native Windows desktop application (the main deliverable of the grokdemo1 project) that lets you drop your PDF cookbooks into a folder and instantly search across every recipe.

> This project is developed with assistance from Grok (xAI). The source lives at https://github.com/danduniver/grokdemo1 and is the canonical home for the RecipePDF Windows app.

## Features

- 📚 **Import any PDF cookbook** — Point it at a folder full of PDFs.
- 🔍 **Powerful full-text search** — Search by recipe name, ingredient, technique, or anything in the book.
- 📖 **Smart recipe detection** — Automatically identifies individual recipes using layout analysis.
- 🖼️ **Page preview** — See the original cookbook page rendered beautifully right in the app.
- 🪟 **Native Windows experience** — Fast, offline, dark theme, keyboard friendly.
- 📋 **One-click actions** — Copy ingredients, open full PDF in your favorite reader, etc.

## Screenshots

*(Add screenshots here after building)*

## Quick Start (for users)

### Option 1: Use the pre-built .exe (recommended)

1. Download the latest `RecipePDF.exe` from Releases (or build it yourself — see below).
2. Double-click `RecipePDF.exe`. No installation needed.
3. Click **"Set Library Folder"** and pick the folder containing your PDF cookbooks.
4. Click **"Scan / Reindex All"** and wait while it processes your books (one-time cost).
5. Type in the big search box — "beef stew", "chocolate chip", "pasta puttanesca", etc.

Results appear instantly with page previews.

### Option 2: Run from source (developers / customization)

Requires Python 3.11 or newer.

```powershell
cd "C:\Users\dandu\OneDrive\Desktop\grokdemo1"

python -m venv .venv
.\ .venv\Scripts\Activate.ps1

pip install -r requirements.txt

python main.py
```

First run will prompt you for a cookbooks folder.

## How to Use

1. **Set your library folder**
   - Go to Settings → Library Folder
   - Choose (or create) a folder where you will place all your cookbook PDFs.

2. **Add cookbooks** (two easy ways)
   - **Fast way**: Click **"Add Cookbook"** and select any PDF files on your computer (it starts at the C: drive).
   - **Bulk way**: Drop many PDFs into your Library Folder, then click **"Scan / Reindex All"**.
   - You can mix both methods — cookbooks added individually or via folder scan all live together.

3. **Search**
   - Type anything: "chocolate cake", "pork tenderloin garlic", "vegan lasagna".
   - Results appear instantly.

4. **Manage your library**
   - Click any cookbook name in the left sidebar to filter to just that book.
   - Click the small **✕** next to a cookbook to remove it from search (your PDF file stays safe on disk).
   - Use **"➕ Add PDF(s)"** anytime to bring in individual cookbooks from anywhere.

## Keyboard Shortcuts

| Shortcut       | Action                    |
|----------------|---------------------------|
| `Ctrl + F`     | Focus search box          |
| `Esc`          | Clear search / close detail |
| `↑` `↓`        | Navigate search results   |
| `Enter`        | Open selected recipe      |
| `Ctrl + R`     | Re-scan cookbooks         |

## Building the Windows Executable

See [BUILD.md](BUILD.md) for detailed instructions using PyInstaller.

The resulting `.exe` is ~80-120 MB (includes PyMuPDF) but completely self-contained and fast.

## How It Works

1. You point RecipePDF at a folder full of PDF cookbooks.
2. It uses **PyMuPDF** to extract text with layout information (font sizes, positions).
3. A smart heuristic detector finds recipe titles (large text) + splits content into "Ingredients" and "Instructions".
4. Everything is indexed into a local SQLite database with **FTS5** full-text search.
5. When you search, it shows ranked results + renders the original PDF page as an image for reference.
6. Your PDFs never leave your computer.

## Technical Details

- **PDF Engine**: PyMuPDF (fitz) — best-in-class text extraction + high-quality page rendering.
- **Search**: SQLite FTS5 with Porter stemming (very fast, completely local).
- **UI**: CustomTkinter — modern dark theme that feels like a real native Windows app.
- **Storage**: `%LOCALAPPDATA%\RecipePDF\recipepdf.db` (plus a small settings.json).
- **Recipe Parsing**: Font-size + position + keyword heuristics. Works great on most professionally laid-out cookbooks.

## Limitations & Roadmap

| Current Limitation                  | Planned Improvement                  |
|-------------------------------------|--------------------------------------|
| Scanned (image) PDFs                | Optional OCR using Tesseract         |
| Heuristic recipe detection          | User can manually mark recipes       |
| No tag / category system            | Auto + manual tagging                |
| Single user / machine               | Export / import index (future)       |

## Contributing

Bug reports and ideas are very welcome! Especially around:
- Better recipe boundary detection for weirdly formatted books
- Beautiful icons / splash screen
- Shopping list generation from selected recipes

## License

MIT License

---

Built with care for people who still love real cookbooks (even when they're PDFs).
