"""
PDF Processing for RecipePDF.

Core responsibilities:
- Extract text + layout information from PDFs using PyMuPDF (fitz)
- Detect individual recipes using font size / position heuristics
- Render PDF pages to high-quality images (for preview in UI)
- Provide clean structured data for the database layer
"""

from __future__ import annotations
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import io
import re
import json

# --------------------------- PDF Metadata & Basic Info ---------------------------

def get_pdf_metadata(pdf_path: str | Path) -> Dict[str, Any]:
    """Return basic info about the PDF."""
    doc = fitz.open(str(pdf_path))
    try:
        meta = doc.metadata or {}
        return {
            "title": meta.get("title") or Path(pdf_path).stem,
            "author": meta.get("author") or "",
            "page_count": len(doc),
            "file_size": Path(pdf_path).stat().st_size if Path(pdf_path).exists() else 0,
        }
    finally:
        doc.close()

# --------------------------- Page Rendering ---------------------------

def render_page_to_image(pdf_path: str | Path, page_num: int, 
                         dpi: int = 150, max_width: int = 900) -> Optional[Image.Image]:
    """
    Render a single PDF page to a PIL Image.
    Good balance of quality vs speed/memory for UI preview.
    """
    doc = fitz.open(str(pdf_path))
    try:
        if page_num < 0 or page_num >= len(doc):
            return None
        page = doc[page_num]
        
        # Matrix for DPI (72 is base)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Convert to PIL
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Downscale if too wide for UI
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        return img
    except Exception as e:
        print(f"[PDF] Error rendering page {page_num}: {e}")
        return None
    finally:
        doc.close()

def render_page_to_bytes(pdf_path: str | Path, page_num: int, dpi: int = 140) -> Optional[bytes]:
    """Render page and return PNG bytes (useful for caching)."""
    img = render_page_to_image(pdf_path, page_num, dpi=dpi)
    if img is None:
        return None
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

# --------------------------- Text Extraction (Detailed) ---------------------------

def extract_page_text_detailed(page: fitz.Page) -> Dict[str, Any]:
    """
    Get rich text information from a page.
    Returns blocks, lines, spans with font sizes, positions, etc.
    """
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    
    # Also get plain text for search (good enough for most cases)
    plain_text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    
    # Get text blocks in reading order (more reliable for some PDFs)
    text_blocks = page.get_text("blocks")
    
    return {
        "dict_blocks": blocks,
        "plain_text": plain_text.strip(),
        "text_blocks": text_blocks,
    }

# --------------------------- Recipe Heuristics ---------------------------

# Common section headers we look for
INGREDIENT_HEADERS = re.compile(
    r"^(ingredients?|ingredientes|ingrédients|zutaten|ingredienti|ingredientes)\s*:?\s*$", 
    re.IGNORECASE | re.MULTILINE
)
INSTRUCTION_HEADERS = re.compile(
    r"^(instructions?|directions?|method|preparation|preparación|préparation|anleitung|istruzioni|passos|passi|steps?|modo de preparo)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE
)
SERVES_PATTERN = re.compile(r"\b(serves?|servings?|yield|makes?|para\s+\d+|rinde)\s*:?\s*\d+", re.IGNORECASE)

def _looks_like_title(span: Dict[str, Any], avg_font_size: float, page_height: float) -> bool:
    """
    Heuristic: Is this span likely a recipe title?
    - Relatively large font
    - Short text (1-8 words typical)
    - Not too low on the page (titles are usually upper half)
    - Not a common header word
    """
    text = span.get("text", "").strip()
    size = span.get("size", 0)
    origin = span.get("origin", (0, 0))  # (x, y) baseline
    y_pos = origin[1] if origin else 0
    
    if not text or len(text) < 3:
        return False
    if len(text) > 80:
        return False
    if y_pos > page_height * 0.65:  # too far down
        return False
    
    # Font size signal (relative to page average)
    if size < max(9, avg_font_size * 1.15):
        return False
    
    # Reject obvious non-titles
    lower = text.lower()
    bad_starts = ("page ", "chapter", "contents", "index", "copyright", "isbn", 
                  "photo", "photograph", "recipe list", "introduction")
    if any(lower.startswith(b) for b in bad_starts):
        return False
    if lower in {"ingredients", "directions", "instructions", "notes", "tips"}:
        return False
    
    # Must contain mostly letters
    letters = sum(c.isalpha() for c in text)
    if letters < 3:
        return False
    
    return True

def _extract_ingredients_and_instructions(full_text: str) -> Tuple[str, str]:
    """
    Given a chunk of recipe text, try to split into ingredients and instructions.
    Very heuristic but works surprisingly well on many cookbooks.
    """
    ingredients = ""
    instructions = ""
    
    # Try to locate sections
    ing_match = INGREDIENT_HEADERS.search(full_text)
    inst_match = INSTRUCTION_HEADERS.search(full_text)
    
    if ing_match:
        start_ing = ing_match.end()
        # Ingredients go until we hit instructions or a long paragraph that looks like prose
        if inst_match and inst_match.start() > start_ing:
            ingredients = full_text[start_ing:inst_match.start()].strip()
            instructions = full_text[inst_match.end():].strip()
        else:
            # Take a generous chunk after "Ingredients"
            ingredients = full_text[start_ing : start_ing + 1800].strip()
            # Try to cut at first long sentence after ingredients
            remaining = full_text[start_ing + 800:]
            instructions = remaining.strip()
    elif inst_match:
        # No ingredients header, but we have instructions
        instructions = full_text[inst_match.end():].strip()
        # Assume everything before was ingredients-ish
        ingredients = full_text[:inst_match.start()].strip()
    else:
        # Last resort: split roughly in half or look for bullet/number patterns
        lines = [l.strip() for l in full_text.splitlines() if l.strip()]
        if len(lines) > 6:
            mid = len(lines) // 2
            ingredients = "\n".join(lines[:mid])
            instructions = "\n".join(lines[mid:])
        else:
            instructions = full_text
    
    # Clean up
    ingredients = re.sub(r"\n{3,}", "\n\n", ingredients).strip()
    instructions = re.sub(r"\n{3,}", "\n\n", instructions).strip()
    
    return ingredients, instructions

def _find_recipe_boundaries(detailed_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Core heuristic engine.
    Scans all pages and tries to identify where recipes start and end.
    Returns list of recipe dicts with page ranges and extracted text.
    """
    recipes: List[Dict[str, Any]] = []
    current_recipe: Optional[Dict[str, Any]] = None
    
    for page_idx, page_data in enumerate(detailed_pages):
        blocks = page_data.get("dict_blocks", [])
        plain = page_data.get("plain_text", "")
        page_height = page_data.get("height", 792)
        
        # Calculate average font size on page (for relative comparisons)
        sizes = []
        for b in blocks:
            if b.get("type") != 0:  # 0 = text
                continue
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    if s.get("size"):
                        sizes.append(s["size"])
        avg_size = sum(sizes) / len(sizes) if sizes else 11.0
        
        # Look for title candidates on this page
        title_candidates: List[Tuple[float, str, int]] = []  # (score, text, y)
        
        for b in blocks:
            if b.get("type") != 0:
                continue
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    if _looks_like_title(s, avg_size, page_height):
                        text = s["text"].strip()
                        y = s.get("origin", (0, 999))[1]
                        # Prefer larger fonts and higher on page
                        score = s["size"] * 10 - (y / 30)
                        title_candidates.append((score, text, page_idx))
        
        title_candidates.sort(reverse=True)
        
        # If we found strong title candidates, start new recipe(s)
        if title_candidates:
            best_title = title_candidates[0][1]
            
            # Close previous recipe if open
            if current_recipe:
                current_recipe["page_end"] = page_idx
                current_recipe["raw_text"] = current_recipe.get("raw_text", "") + "\n\n" + plain[:1200]
                recipes.append(current_recipe)
            
            current_recipe = {
                "title": best_title[:120],
                "page_start": page_idx,
                "page_end": page_idx,
                "raw_text": plain,
                "ingredients": "",
                "instructions": "",
            }
        else:
            # Accumulate text into current recipe
            if current_recipe:
                current_recipe["raw_text"] = current_recipe.get("raw_text", "") + "\n\n" + plain
                current_recipe["page_end"] = page_idx
    
    # Close last recipe
    if current_recipe:
        current_recipe["page_end"] = len(detailed_pages) - 1
        recipes.append(current_recipe)
    
    # Post-process: split raw_text into ingredients + instructions
    for rec in recipes:
        raw = rec.pop("raw_text", "")
        ing, inst = _extract_ingredients_and_instructions(raw)
        rec["ingredients"] = ing
        rec["instructions"] = inst
    
    # Filter out junk recipes (very short titles with almost no content)
    filtered = []
    for r in recipes:
        content_len = len((r.get("ingredients") or "") + (r.get("instructions") or ""))
        if len(r["title"]) >= 4 and content_len > 40:
            filtered.append(r)
    
    return filtered

def process_cookbook(pdf_path: str | Path, progress_callback=None) -> Dict[str, Any]:
    """
    Full processing pipeline for one cookbook PDF.
    
    Returns:
    {
        "metadata": {...},
        "recipes": [ {...}, ... ],
        "pages": [ {"page_num": 0, "text": "..."}, ... ],
        "total_pages": N
    }
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))
    
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    
    metadata = get_pdf_metadata(pdf_path)
    metadata["filepath"] = str(pdf_path)
    
    all_pages_data = []
    all_page_texts = []
    
    for i, page in enumerate(doc):
        if progress_callback:
            progress_callback(i + 1, total_pages, f"Processing page {i+1}/{total_pages}")
        
        page_info = extract_page_text_detailed(page)
        page_info["page_num"] = i
        page_info["height"] = page.rect.height
        all_pages_data.append(page_info)
        all_page_texts.append({
            "page_num": i,
            "text": page_info["plain_text"]
        })
    
    doc.close()
    
    # Run the recipe detection heuristic
    if progress_callback:
        progress_callback(total_pages, total_pages, "Detecting recipes...")
    
    detected_recipes = _find_recipe_boundaries(all_pages_data)
    
    # Attach source info
    for rec in detected_recipes:
        rec["source_pdf"] = str(pdf_path)
    
    result = {
        "metadata": metadata,
        "recipes": detected_recipes,
        "pages": all_page_texts,
        "total_pages": total_pages,
    }
    
    if progress_callback:
        progress_callback(total_pages, total_pages, f"Found {len(detected_recipes)} recipes")
    
    return result

# --------------------------- Convenience helpers ---------------------------

def get_page_count(pdf_path: str | Path) -> int:
    try:
        doc = fitz.open(str(pdf_path))
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0

if __name__ == "__main__":
    # Quick smoke test (run with a PDF path)
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f"Processing: {path}")
        res = process_cookbook(path, progress_callback=lambda c,t,m: print(f"  {m}"))
        print(f"\nMetadata: {res['metadata']}")
        print(f"Recipes found: {len(res['recipes'])}")
        for r in res['recipes'][:3]:
            print(f"  - {r['title']} (p.{r['page_start']+1}-{r['page_end']+1})")
    else:
        print("Usage: python pdf_processor.py /path/to/cookbook.pdf")
