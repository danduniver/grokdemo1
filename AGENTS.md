# Project Rules for grokdemo1 (RecipePDF)

RecipePDF is a native Windows desktop application for searching and browsing PDF cookbooks. It uses CustomTkinter + PyMuPDF + SQLite FTS5.

## General Guidelines
- Keep the app fast, offline-first, and self-contained (single .exe build target via PyInstaller).
- PDF processing and recipe detection heuristics are core — change them carefully and test with real cookbooks.
- UI must stay responsive: long work (indexing, rendering) goes in background threads.
- All user data (index, settings) lives in %LOCALAPPDATA%\RecipePDF or equivalent app data dir. Never write to source tree at runtime.
- Prefer native Windows behaviors (os.startfile, file:// URIs with #page, taskbar integration).

## Code Style (Python)
- 4-space indentation.
- Type hints on public functions and important methods.
- Clear separation: pdf_processor.py (fitz + rendering), indexer.py (scan + recipe splitting), db.py (SQLite + FTS), main.py (UI only).
- Keep the three-panel layout (library | results | detail with preview + ingredients + instructions) stable unless a major redesign is planned.
- Update README.md + BUILD.md when changing run/build steps or adding features.

## Development Workflow
- Run from source: `python main.py` after `pip install -r requirements.txt`
- Build the Windows .exe with `python build.py` (or the manual PyInstaller command in BUILD.md)
- Test indexing + search on a variety of real PDF cookbooks (different layouts, 2-column, etc.)
- When adding features (e.g. tags, shopping list, OCR for scans), add to the "Limitations & Roadmap" section.

## GitHub / Commits
- Main branch is `main`.
- Use Grok + GitHub MCP tools for changes, reviews, and pushes when practical.
- Conventional commits preferred.

## When Using Grok Skills
- For bigger changes, use the `design` skill first to produce a short plan, then `implement` + `review`.
- The `explore` agent is useful to understand the current modules (main.py is large).

## Testing Notes
- No formal test suite yet — manual testing with real PDFs is required.
- After changes to pdf_processor or indexer, re-index a couple of books and verify title/ingredient/instruction extraction quality.