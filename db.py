"""
Database layer for RecipePDF.

Uses SQLite + FTS5 for fast local full-text search of recipes extracted from PDFs.
All data stored in %LOCALAPPDATA%\\RecipePDF\\recipepdf.db
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import os

# Windows-friendly app data location
def get_app_data_dir() -> Path:
    """Return the application data directory for RecipePDF."""
    local_appdata = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA')
    if not local_appdata:
        local_appdata = str(Path.home() / "AppData" / "Local")
    app_dir = Path(local_appdata) / "RecipePDF"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

DB_PATH = get_app_data_dir() / "recipepdf.db"
SCHEMA_VERSION = 1

def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database (with good defaults)."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    # Performance pragmas
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db() -> None:
    """Initialize database schema if it doesn't exist."""
    conn = get_connection()
    try:
        # Cookbooks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cookbooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE NOT NULL,
                title TEXT,
                author TEXT,
                page_count INTEGER DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                added_date TEXT NOT NULL,
                last_indexed TEXT,
                status TEXT DEFAULT 'pending'   -- pending, indexed, error
            )
        """)

        # Recipes table (structured recipe records)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cookbook_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                page_start INTEGER NOT NULL,
                page_end INTEGER NOT NULL,
                ingredients TEXT,               -- JSON array or newline separated
                instructions TEXT,              -- Newline separated steps
                raw_text TEXT,                  -- Original extracted block for debugging
                confidence REAL DEFAULT 0.7,
                created_date TEXT NOT NULL,
                FOREIGN KEY (cookbook_id) REFERENCES cookbooks(id) ON DELETE CASCADE
            )
        """)

        # Full-text search virtual table (FTS5)
        # We keep a separate regular table + triggers or just rebuild on index for simplicity.
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
                title,
                ingredients,
                instructions,
                source_book,
                page_info,
                tokenize='porter unicode61'
            )
        """)

        # Page-level content (for when we want page-granular results or OCR fallback)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS page_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cookbook_id INTEGER NOT NULL,
                page_num INTEGER NOT NULL,
                text TEXT NOT NULL,
                UNIQUE(cookbook_id, page_num),
                FOREIGN KEY (cookbook_id) REFERENCES cookbooks(id) ON DELETE CASCADE
            )
        """)

        # Also FTS on pages for broad search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(
                text,
                source_book,
                page_num,
                tokenize='porter unicode61'
            )
        """)

        # Simple metadata table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)", 
                     ("schema_version", str(SCHEMA_VERSION)))

        conn.commit()
        print(f"[DB] Initialized at {DB_PATH}")
    finally:
        conn.close()

def clear_all_data() -> None:
    """Dangerous: wipe everything (used by 'Reindex All')."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM recipes_fts")
        conn.execute("DELETE FROM page_fts")
        conn.execute("DELETE FROM recipes")
        conn.execute("DELETE FROM page_content")
        conn.execute("DELETE FROM cookbooks")
        conn.commit()
    finally:
        conn.close()

# --------------------------- Cookbook operations ---------------------------

def add_or_update_cookbook(filepath: str, title: str = "", author: str = "", 
                           page_count: int = 0, file_size: int = 0) -> int:
    """Insert or update a cookbook record. Returns the cookbook id."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute("""
            INSERT INTO cookbooks (filepath, title, author, page_count, file_size, added_date, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(filepath) DO UPDATE SET
                title=excluded.title,
                author=excluded.author,
                page_count=excluded.page_count,
                file_size=excluded.file_size
            RETURNING id
        """, (filepath, title or Path(filepath).stem, author, page_count, file_size, now))
        row = cur.fetchone()
        conn.commit()
        return int(row[0])
    finally:
        conn.close()

def mark_cookbook_indexed(cookbook_id: int, status: str = "indexed") -> None:
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE cookbooks 
            SET last_indexed = ?, status = ?
            WHERE id = ?
        """, (datetime.utcnow().isoformat(), status, cookbook_id))
        conn.commit()
    finally:
        conn.close()

def get_all_cookbooks() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT id, filepath, title, author, page_count, file_size, 
                   added_date, last_indexed, status
            FROM cookbooks
            ORDER BY title COLLATE NOCASE
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_cookbook_by_id(cookbook_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM cookbooks WHERE id = ?", (cookbook_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# --------------------------- Recipe operations ---------------------------

def insert_recipe(cookbook_id: int, title: str, page_start: int, page_end: int,
                  ingredients: str = "", instructions: str = "", raw_text: str = "",
                  confidence: float = 0.6) -> int:
    """Insert a detected recipe and return its id."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute("""
            INSERT INTO recipes (cookbook_id, title, page_start, page_end, 
                                 ingredients, instructions, raw_text, confidence, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, (cookbook_id, title, page_start, page_end, ingredients, instructions, raw_text, confidence, now))
        recipe_id = int(cur.fetchone()[0])
        conn.commit()
        return recipe_id
    finally:
        conn.close()

def insert_recipe_fts(recipe_id: int, title: str, ingredients: str, instructions: str,
                      source_book: str, page_info: str) -> None:
    """Insert into the FTS index."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO recipes_fts (rowid, title, ingredients, instructions, source_book, page_info)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (recipe_id, title, ingredients or "", instructions or "", source_book, page_info))
        conn.commit()
    finally:
        conn.close()

def insert_page_content(cookbook_id: int, page_num: int, text: str) -> None:
    """Store raw page text (used for page-level search)."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO page_content (cookbook_id, page_num, text)
            VALUES (?, ?, ?)
        """, (cookbook_id, page_num, text))
        conn.commit()
    finally:
        conn.close()

def insert_page_fts(page_id: int, text: str, source_book: str, page_num: int) -> None:
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO page_fts (rowid, text, source_book, page_num)
            VALUES (?, ?, ?, ?)
        """, (page_id, text, source_book, page_num))
        conn.commit()
    finally:
        conn.close()

# --------------------------- Search ---------------------------

def _safe_fts_query(user_query: str) -> str:
    """Sanitize arbitrary user input for safe use with FTS5 MATCH clause."""
    if not user_query:
        return ""
    # Remove characters that commonly break FTS5 syntax
    cleaned = user_query.replace('"', " ").replace("'", " ").replace("(", " ").replace(")", " ")
    # Split into words and wrap each safely as a phrase
    words = [w.strip() for w in cleaned.split() if w.strip()]
    if not words:
        return ""
    # "word1" "word2" "word3"  →  very reliable for FTS5
    return " ".join(f'"{w}"' for w in words)


def search_recipes(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Full-text search using FTS5.
    Returns enriched results joining recipes + cookbooks.
    """
    if not query or not query.strip():
        return []

    safe_query = _safe_fts_query(query)
    if not safe_query:
        return []

    conn = get_connection()
    try:
        # Use FTS5 MATCH with ranking
        sql = """
            SELECT 
                r.id,
                r.title,
                r.page_start,
                r.page_end,
                r.ingredients,
                r.instructions,
                r.confidence,
                c.title AS cookbook_title,
                c.filepath AS cookbook_path,
                c.id AS cookbook_id,
                recipes_fts.page_info,
                bm25(recipes_fts) AS rank
            FROM recipes_fts
            JOIN recipes r ON r.id = recipes_fts.rowid
            JOIN cookbooks c ON c.id = r.cookbook_id
            WHERE recipes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        rows = conn.execute(sql, (safe_query, limit)).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            # Clean up ingredients/instructions for display
            if d.get("ingredients"):
                try:
                    parsed = json.loads(d["ingredients"])
                    d["ingredients_list"] = parsed if isinstance(parsed, list) else []
                except Exception:
                    d["ingredients_list"] = [line.strip() for line in d["ingredients"].split("\n") if line.strip()]
            results.append(d)
        return results
    finally:
        conn.close()

def search_pages(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Search at page granularity (useful when recipe detection misses things)."""
    if not query or not query.strip():
        return []

    safe_query = _safe_fts_query(query)
    if not safe_query:
        return []

    conn = get_connection()
    try:
        sql = """
            SELECT 
                pc.id,
                pc.page_num,
                pc.text,
                c.title AS cookbook_title,
                c.filepath AS cookbook_path,
                c.id AS cookbook_id,
                page_fts.page_num AS fts_page,
                bm25(page_fts) AS rank
            FROM page_fts
            JOIN page_content pc ON pc.id = page_fts.rowid
            JOIN cookbooks c ON c.id = pc.cookbook_id
            WHERE page_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        rows = conn.execute(sql, (safe_query, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_recipes_for_cookbook(cookbook_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT r.*, c.title AS cookbook_title, c.filepath AS cookbook_path
            FROM recipes r
            JOIN cookbooks c ON c.id = r.cookbook_id
            WHERE r.cookbook_id = ?
            ORDER BY r.page_start
        """, (cookbook_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_recipe_by_id(recipe_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT r.*, c.title AS cookbook_title, c.filepath AS cookbook_path
            FROM recipes r
            JOIN cookbooks c ON c.id = r.cookbook_id
            WHERE r.id = ?
        """, (recipe_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_stats() -> Dict[str, int]:
    """Return simple stats for the UI status bar."""
    conn = get_connection()
    try:
        cookbooks = conn.execute("SELECT COUNT(*) FROM cookbooks").fetchone()[0]
        recipes = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
        pages = conn.execute("SELECT COUNT(*) FROM page_content").fetchone()[0]
        return {"cookbooks": cookbooks, "recipes": recipes, "pages": pages}
    finally:
        conn.close()

def delete_cookbook(cookbook_id: int) -> None:
    """Delete a cookbook and all its recipes/pages (cascades)."""
    conn = get_connection()
    try:
        # FTS rows are not auto-deleted on row delete for external content style,
        # so we manually clean FTS for this cookbook's recipes.
        conn.execute("""
            DELETE FROM recipes_fts 
            WHERE rowid IN (SELECT id FROM recipes WHERE cookbook_id = ?)
        """, (cookbook_id,))
        conn.execute("""
            DELETE FROM page_fts 
            WHERE rowid IN (SELECT id FROM page_content WHERE cookbook_id = ?)
        """, (cookbook_id,))
        conn.execute("DELETE FROM cookbooks WHERE id = ?", (cookbook_id,))
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    # Quick self-test
    init_db()
    print("DB ready at", DB_PATH)
    print("Stats:", get_stats())
