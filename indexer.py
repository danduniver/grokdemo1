"""
Indexing orchestration for RecipePDF.

Coordinates:
- Scanning a library folder for PDFs
- Calling pdf_processor
- Populating the database (cookbooks + recipes + FTS + page content)
- Progress reporting for UI
"""

from pathlib import Path
from typing import Callable, List, Optional, Dict, Any
import time

import db
import pdf_processor

# Supported extensions (currently only PDF, easy to extend later)
PDF_EXTENSIONS = {".pdf"}


def find_pdfs_in_folder(folder: str | Path, recursive: bool = True) -> List[Path]:
    """Return list of PDF files found in the given folder."""
    root = Path(folder).expanduser().resolve()
    if not root.exists():
        return []
    
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted([p for p in root.glob(pattern) if p.is_file()])


def index_single_pdf(pdf_path: Path, 
                     progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Dict[str, Any]:
    """
    Process one PDF and insert everything into the database.
    Returns summary dict.
    """
    pdf_path = Path(pdf_path)
    
    # 1. Add/update cookbook record (pending)
    meta = pdf_processor.get_pdf_metadata(pdf_path)
    cookbook_id = db.add_or_update_cookbook(
        filepath=str(pdf_path),
        title=meta["title"],
        author=meta.get("author", ""),
        page_count=meta["page_count"],
        file_size=meta["file_size"],
    )
    
    # 2. Delete old recipes + pages for this cookbook (clean reindex of this book)
    conn = db.get_connection()
    try:
        # Remove old FTS entries
        conn.execute("""
            DELETE FROM recipes_fts 
            WHERE rowid IN (SELECT id FROM recipes WHERE cookbook_id = ?)
        """, (cookbook_id,))
        conn.execute("""
            DELETE FROM page_fts 
            WHERE rowid IN (SELECT id FROM page_content WHERE cookbook_id = ?)
        """, (cookbook_id,))
        conn.execute("DELETE FROM recipes WHERE cookbook_id = ?", (cookbook_id,))
        conn.execute("DELETE FROM page_content WHERE cookbook_id = ?", (cookbook_id,))
        conn.commit()
    finally:
        conn.close()
    
    # 3. Full extraction + recipe detection
    result = pdf_processor.process_cookbook(pdf_path, progress_callback=progress_callback)
    
    # 4. Insert page content + FTS
    for page in result["pages"]:
        db.insert_page_content(cookbook_id, page["page_num"], page["text"])
    
    # Re-fetch page_content ids for FTS (rowid == primary key)
    conn = db.get_connection()
    try:
        page_rows = conn.execute("""
            SELECT id, page_num FROM page_content 
            WHERE cookbook_id = ? ORDER BY page_num
        """, (cookbook_id,)).fetchall()
        
        page_id_map = {r["page_num"]: r["id"] for r in page_rows}
        
        for page in result["pages"]:
            pid = page_id_map.get(page["page_num"])
            if pid:
                db.insert_page_fts(
                    page_id=pid,
                    text=page["text"],
                    source_book=result["metadata"]["title"],
                    page_num=page["page_num"] + 1,  # 1-based for humans
                )
    finally:
        conn.close()
    
    # 5. Insert detected recipes + FTS
    recipes_inserted = 0
    for rec in result["recipes"]:
        recipe_id = db.insert_recipe(
            cookbook_id=cookbook_id,
            title=rec["title"],
            page_start=rec["page_start"],
            page_end=rec["page_end"],
            ingredients=rec.get("ingredients", ""),
            instructions=rec.get("instructions", ""),
            raw_text="",  # we can drop heavy raw if wanted
            confidence=0.65,
        )
        
        page_info = f"p.{rec['page_start']+1}"
        if rec["page_end"] != rec["page_start"]:
            page_info = f"pp.{rec['page_start']+1}-{rec['page_end']+1}"
        
        db.insert_recipe_fts(
            recipe_id=recipe_id,
            title=rec["title"],
            ingredients=rec.get("ingredients", ""),
            instructions=rec.get("instructions", ""),
            source_book=result["metadata"]["title"],
            page_info=page_info,
        )
        recipes_inserted += 1
    
    # 6. Mark as indexed
    db.mark_cookbook_indexed(cookbook_id, status="indexed" if recipes_inserted > 0 else "indexed")
    
    return {
        "cookbook_id": cookbook_id,
        "title": result["metadata"]["title"],
        "recipes_found": recipes_inserted,
        "pages": result["total_pages"],
    }


def full_reindex(library_folder: str | Path,
                 progress_callback: Optional[Callable[[str, int, int], None]] = None,
                 recursive: bool = True) -> Dict[str, Any]:
    """
    Scan the library folder and (re)index every PDF found.
    
    progress_callback receives: (current_file_name, current_index, total_files)
    """
    pdfs = find_pdfs_in_folder(library_folder, recursive=recursive)
    total = len(pdfs)
    
    if total == 0:
        return {"indexed": 0, "errors": 0, "message": "No PDFs found"}
    
    indexed = 0
    errors = 0
    details = []
    
    for idx, pdf_path in enumerate(pdfs, 1):
        if progress_callback:
            progress_callback(pdf_path.name, idx, total)
        
        try:
            summary = index_single_pdf(
                pdf_path,
                progress_callback=lambda cur, tot, msg: None  # inner progress ignored for now
            )
            indexed += 1
            details.append(summary)
        except Exception as e:
            errors += 1
            print(f"[Indexer] Failed to index {pdf_path}: {e}")
            # Still record the cookbook so user sees it
            try:
                db.add_or_update_cookbook(str(pdf_path), title=pdf_path.stem, status="error")
            except Exception:
                pass
    
    return {
        "indexed": indexed,
        "errors": errors,
        "total_found": total,
        "details": details,
    }


def get_library_stats() -> Dict[str, Any]:
    """Convenience wrapper around db stats + folder info."""
    stats = db.get_stats()
    cookbooks = db.get_all_cookbooks()
    return {
        **stats,
        "cookbooks_list": cookbooks,
    }


if __name__ == "__main__":
    import sys
    db.init_db()
    if len(sys.argv) > 1:
        folder = sys.argv[1]
        print(f"Reindexing folder: {folder}")
        res = full_reindex(folder, progress_callback=lambda name, i, t: print(f"  [{i}/{t}] {name}"))
        print(res)
    else:
        print("Usage: python indexer.py /path/to/cookbooks/folder")
