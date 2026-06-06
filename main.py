"""
RecipePDF - Main Application

A beautiful Windows desktop app for searching PDF cookbooks.
Run with: python main.py
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import webbrowser

# Local modules
import db
import indexer
import pdf_processor

# --------------------------- Configuration ---------------------------

APP_NAME = "RecipePDF"
APP_VERSION = "1.0.0"
THEME = "dark"  # or "light"

# Color palette (nice cookbook feel)
ACCENT_COLOR = "#E07A5F"      # Warm terracotta
SECONDARY = "#3D405B"         # Deep slate
SUCCESS = "#81B29A"           # Sage green

ctk.set_appearance_mode(THEME)
ctk.set_default_color_theme("blue")  # We override many colors manually

SETTINGS_FILE = db.get_app_data_dir() / "settings.json"

def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"library_folder": ""}

def save_settings(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")

# --------------------------- Main Application ---------------------------

class RecipePDFApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title(APP_NAME)
        self.geometry("1280x820")
        self.minsize(1000, 680)
        
        # State
        self.settings = load_settings()
        self.current_results: List[Dict[str, Any]] = []
        self.selected_result: Optional[Dict[str, Any]] = None
        self.current_preview_image: Optional[ctk.CTkImage] = None
        self.library_folder: str = self.settings.get("library_folder", "")
        
        # Init DB
        db.init_db()
        
        # Build UI
        self._create_widgets()
        self._create_menu()
        
        # Initial load
        self.after(150, self._initial_load)
    
    # --------------------------- UI Construction ---------------------------
    
    def _create_menu(self):
        # Simple top menu bar using CTkOptionMenu style or native
        menubar = ctk.CTkFrame(self, height=36, corner_radius=0)
        menubar.pack(fill="x", side="top")
        
        # Left side buttons (compacted for visibility)
        ctk.CTkButton(menubar, text="📁 Library", width=95,
                      command=self._choose_library_folder, fg_color=SECONDARY).pack(side="left", padx=(12, 4), pady=6)
        
        ctk.CTkButton(menubar, text="Add Cookbook", width=125,
                      command=self._add_cookbook, fg_color=SUCCESS).pack(side="left", padx=4, pady=6)
        
        ctk.CTkButton(menubar, text="🔄 Scan All", width=100,
                      command=self._start_full_reindex, fg_color=ACCENT_COLOR).pack(side="left", padx=4, pady=6)
        
        ctk.CTkButton(menubar, text="⚙️", width=40,
                      command=self._open_settings, fg_color="transparent", border_width=1).pack(side="left", padx=4, pady=6)
        
        # Right side
        ctk.CTkLabel(menubar, text=f"v{APP_VERSION}", text_color="gray60").pack(side="right", padx=16)
    
    def _create_widgets(self):
        # Main container with 3 columns
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        
        # Configure grid: left (library) | center (search+results) | right (detail)
        main.grid_columnconfigure(0, weight=0, minsize=210)   # Library
        main.grid_columnconfigure(1, weight=1, minsize=420)   # Search + Results
        main.grid_columnconfigure(2, weight=1, minsize=380)   # Detail
        main.grid_rowconfigure(0, weight=1)
        
        # ===== LEFT: Library panel =====
        left = ctk.CTkFrame(main, width=210, corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)
        
        ctk.CTkLabel(left, text="📚  MY COOKBOOKS", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="gray70").pack(anchor="w", padx=14, pady=(12, 2))
        
        # Prominent Add button in the sidebar (hard to miss)
        ctk.CTkButton(left, text="+ Add Cookbook", 
                      command=self._add_cookbook,
                      fg_color=SUCCESS, height=32, font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=12, pady=(4, 8))
        
        self.cookbook_list = ctk.CTkScrollableFrame(left, width=190, fg_color="transparent")
        self.cookbook_list.pack(fill="both", expand=True, padx=6, pady=4)
        
        self.stats_label = ctk.CTkLabel(left, text="0 cookbooks • 0 recipes", 
                                        font=ctk.CTkFont(size=11), text_color="gray60")
        self.stats_label.pack(pady=(8, 12))
        
        # ===== CENTER: Search + Results =====
        center = ctk.CTkFrame(main, corner_radius=10)
        center.grid(row=0, column=1, sticky="nsew", padx=3, pady=4)
        center.grid_rowconfigure(2, weight=1)
        center.grid_columnconfigure(0, weight=1)
        
        # Search header
        search_frame = ctk.CTkFrame(center, fg_color="transparent")
        search_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        
        ctk.CTkLabel(search_frame, text="Search recipes & ingredients", 
                     font=ctk.CTkFont(size=11), text_color="gray70").pack(anchor="w")
        
        self.search_entry = ctk.CTkEntry(
            search_frame, 
            placeholder_text="e.g.  chocolate cake,  salmon dill,  vegetarian lasagna...",
            height=42,
            font=ctk.CTkFont(size=15),
            border_color=ACCENT_COLOR,
        )
        self.search_entry.pack(fill="x", pady=(4, 0))
        self.search_entry.bind("<Return>", lambda e: self._perform_search())
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        
        # Results header
        results_header = ctk.CTkFrame(center, fg_color="transparent")
        results_header.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 2))
        
        self.results_count_label = ctk.CTkLabel(results_header, text="Enter a search term above", 
                                                font=ctk.CTkFont(size=12, weight="bold"))
        self.results_count_label.pack(side="left")
        
        ctk.CTkButton(results_header, text="Clear", width=70, height=26,
                      command=self._clear_search, fg_color="transparent", 
                      border_width=1, text_color="gray70").pack(side="right")
        
        # Results scroll area (cards)
        self.results_scroll = ctk.CTkScrollableFrame(center, fg_color="#2B2B2B", corner_radius=6)
        self.results_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=(2, 10))
        
        # ===== RIGHT: Detail Viewer =====
        self.detail_frame = ctk.CTkFrame(main, corner_radius=10)
        self.detail_frame.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=4)
        
        self._build_detail_panel()
    
    def _build_detail_panel(self):
        """Build the recipe detail viewer (right panel)."""
        # Header
        header = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))
        
        self.detail_title = ctk.CTkLabel(header, text="Select a recipe", 
                                         font=ctk.CTkFont(size=17, weight="bold"),
                                         wraplength=320, justify="left")
        self.detail_title.pack(anchor="w")
        
        self.detail_source = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=12),
                                          text_color=ACCENT_COLOR)
        self.detail_source.pack(anchor="w", pady=(1, 0))
        
        # Action buttons
        actions = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=6)
        
        self.btn_copy = ctk.CTkButton(actions, text="📋 Copy Ingredients", width=130, height=28,
                                      command=self._copy_ingredients, state="disabled")
        self.btn_copy.pack(side="left")
        
        self.btn_open_pdf = ctk.CTkButton(actions, text="📖 Open PDF", width=100, height=28,
                                          command=self._open_in_pdf_reader, state="disabled",
                                          fg_color=SUCCESS)
        self.btn_open_pdf.pack(side="left", padx=6)
        
        # PDF Page preview
        preview_label_frame = ctk.CTkFrame(self.detail_frame, fg_color="#1F1F1F", corner_radius=6)
        preview_label_frame.pack(fill="x", padx=12, pady=6)
        
        ctk.CTkLabel(preview_label_frame, text="Original page preview", 
                     font=ctk.CTkFont(size=10), text_color="gray60").pack(anchor="w", padx=8, pady=(6, 2))
        
        # Page navigation - moved above the preview image
        nav = ctk.CTkFrame(preview_label_frame, fg_color="transparent")
        nav.pack(fill="x", padx=8, pady=(2, 4))
        self.btn_prev_page = ctk.CTkButton(nav, text="◀", width=32, height=26,
                                           command=lambda: self._change_preview_page(-1), state="disabled")
        self.btn_prev_page.pack(side="left")
        self.page_info_label = ctk.CTkLabel(nav, text="—", font=ctk.CTkFont(size=11))
        self.page_info_label.pack(side="left", expand=True)
        self.btn_next_page = ctk.CTkButton(nav, text="▶", width=32, height=26,
                                           command=lambda: self._change_preview_page(1), state="disabled")
        self.btn_next_page.pack(side="right")
        
        self.preview_label = ctk.CTkLabel(preview_label_frame, text="No preview", 
                                          fg_color="#111111", corner_radius=4)
        self.preview_label.pack(padx=8, pady=(0, 8))
        
        # Ingredients
        ctk.CTkLabel(self.detail_frame, text="INGREDIENTS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray70").pack(anchor="w", padx=14, pady=(8, 2))
        
        self.ingredients_box = ctk.CTkTextbox(self.detail_frame, height=130, font=ctk.CTkFont(size=12))
        self.ingredients_box.pack(fill="x", padx=12, pady=(0, 6))
        
        # Instructions
        ctk.CTkLabel(self.detail_frame, text="INSTRUCTIONS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray70").pack(anchor="w", padx=14, pady=(4, 2))
        
        self.instructions_box = ctk.CTkTextbox(self.detail_frame, height=160, font=ctk.CTkFont(size=12))
        self.instructions_box.pack(fill="both", expand=True, padx=12, pady=(0, 10))
    
    # --------------------------- Initial Load & Refresh ---------------------------
    
    def _initial_load(self):
        self._refresh_cookbook_list()
        self._update_stats()
        
        if not self.library_folder:
            self.after(600, lambda: self._show_welcome_message())
        else:
            # Optional: auto-search last term or show recent recipes
            self.search_entry.focus()
    
    def _show_welcome_message(self):
        self.results_count_label.configure(text="Welcome! Click 'Add Cookbook' or set a Library Folder.")
        # Show a friendly empty state in results area
        self._clear_results_cards()
        empty = ctk.CTkLabel(self.results_scroll, 
                             text="👋\n\nNo cookbooks yet.\n\nClick 'Add Cookbook' above\nor set a Library Folder + Scan.",
                             font=ctk.CTkFont(size=14), text_color="gray60", justify="center")
        empty.pack(expand=True, pady=80)
    
    def _refresh_cookbook_list(self):
        """Rebuild the left sidebar list of cookbooks."""
        for child in self.cookbook_list.winfo_children():
            child.destroy()
        
        cookbooks = db.get_all_cookbooks()
        
        if not cookbooks:
            ctk.CTkLabel(self.cookbook_list, text="No cookbooks indexed yet", 
                         text_color="gray50", font=ctk.CTkFont(size=11)).pack(pady=20)
            return
        
        for cb in cookbooks:
            name = cb["title"][:32] + ("…" if len(cb["title"]) > 32 else "")
            status = cb.get("status", "indexed")
            
            frame = ctk.CTkFrame(self.cookbook_list, fg_color="#2A2A2A", corner_radius=6)
            frame.pack(fill="x", pady=3, padx=2)
            
            # Header row: icon + title + delete button
            header = ctk.CTkFrame(frame, fg_color="transparent")
            header.pack(fill="x", padx=4, pady=(4, 0))
            
            lbl = ctk.CTkLabel(header, text=f"📘 {name}", font=ctk.CTkFont(size=11, weight="bold"),
                               anchor="w", cursor="hand2")
            lbl.pack(side="left", padx=(4, 0))
            lbl.bind("<Button-1>", lambda e, cid=cb["id"]: self._filter_by_cookbook(cid))
            
            # Small delete button (X)
            del_btn = ctk.CTkButton(
                header, 
                text="✕", 
                width=20, 
                height=20,
                fg_color="transparent",
                text_color="gray60",
                hover_color="#5C3A3A",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda cid=cb["id"]: self._remove_cookbook(cid)
            )
            del_btn.pack(side="right", padx=(0, 2))
            
            info = f"{cb['page_count']} pages  •  {cb.get('author', '')[:18]}"
            ctk.CTkLabel(frame, text=info, font=ctk.CTkFont(size=9), text_color="gray50",
                         anchor="w").pack(fill="x", padx=8, pady=(0, 5))
    
    def _update_stats(self):
        stats = db.get_stats()
        self.stats_label.configure(
            text=f"{stats['cookbooks']} cookbooks • {stats['recipes']} recipes"
        )
    
    # --------------------------- Search ---------------------------
    
    def _on_search_key(self, event=None):
        # Live search with small debounce feel (simple version)
        if len(self.search_entry.get().strip()) >= 2:
            self.after_cancel(getattr(self, "_search_after_id", None)) if hasattr(self, "_search_after_id") else None
            self._search_after_id = self.after(280, self._perform_search)
    
    def _perform_search(self):
        query = self.search_entry.get().strip()
        if not query:
            self._clear_results_cards()
            self.results_count_label.configure(text="Type to search across all your cookbooks")
            return
        
        self.results_count_label.configure(text=f"Searching for “{query}”...")
        self.update_idletasks()
        
        # Do search (fast)
        recipe_results = db.search_recipes(query, limit=60)
        page_results = db.search_pages(query, limit=25)  # supplement
        
        # Merge and de-dupe a bit
        combined = recipe_results[:]
        
        # Add page results as secondary if they don't overlap much
        seen_pages = {(r.get("cookbook_id"), r.get("page_start")) for r in recipe_results}
        for p in page_results:
            key = (p.get("cookbook_id"), p.get("page_num"))
            if key not in seen_pages:
                # Convert page result to similar shape
                combined.append({
                    "id": p["id"],
                    "title": f"Page {p['page_num'] + 1}",
                    "page_start": p["page_num"],
                    "page_end": p["page_num"],
                    "ingredients": "",
                    "instructions": p["text"][:600] + "...",
                    "cookbook_title": p["cookbook_title"],
                    "cookbook_path": p["cookbook_path"],
                    "cookbook_id": p["cookbook_id"],
                    "page_info": f"p.{p['page_num'] + 1}",
                    "rank": p.get("rank", 99),
                    "is_page_result": True,
                })
        
        self.current_results = combined[:55]  # cap for UI sanity
        self._render_results_cards()
    
    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self._clear_results_cards()
        self.results_count_label.configure(text="Search cleared")
        self._clear_detail_panel()
    
    def _clear_results_cards(self):
        for child in self.results_scroll.winfo_children():
            child.destroy()
    
    def _render_results_cards(self):
        self._clear_results_cards()
        
        count = len(self.current_results)
        self.results_count_label.configure(
            text=f"{count} result{'s' if count != 1 else ''} found"
        )
        
        if count == 0:
            lbl = ctk.CTkLabel(self.results_scroll, text="No matches. Try different keywords.",
                               text_color="gray50")
            lbl.pack(pady=30)
            return
        
        for idx, res in enumerate(self.current_results):
            self._create_result_card(res, idx)
    
    def _create_result_card(self, result: Dict[str, Any], index: int):
        """Create a nice clickable recipe card."""
        card = ctk.CTkFrame(self.results_scroll, fg_color="#333333", corner_radius=8)
        card.pack(fill="x", padx=6, pady=5)
        
        # Title row
        title = result.get("title", "Untitled Recipe")
        title_lbl = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                                 anchor="w", cursor="hand2")
        title_lbl.pack(fill="x", padx=10, pady=(8, 1))
        title_lbl.bind("<Button-1>", lambda e, i=index: self._select_result(i))
        
        # Source line
        source = f"{result.get('cookbook_title', 'Unknown')}  •  {result.get('page_info', '')}"
        src_lbl = ctk.CTkLabel(card, text=source, font=ctk.CTkFont(size=10),
                               text_color=ACCENT_COLOR, anchor="w", cursor="hand2")
        src_lbl.pack(fill="x", padx=10, pady=(0, 4))
        src_lbl.bind("<Button-1>", lambda e, i=index: self._select_result(i))
        
        # Snippet
        snippet = ""
        if result.get("ingredients"):
            snippet = result["ingredients"][:140].replace("\n", " ")
        elif result.get("instructions"):
            snippet = result["instructions"][:140].replace("\n", " ")
        
        if snippet:
            snip = ctk.CTkLabel(card, text=snippet + "…", font=ctk.CTkFont(size=10),
                                text_color="gray75", anchor="w", wraplength=520, justify="left")
            snip.pack(fill="x", padx=10, pady=(0, 8))
        
        # Click whole card
        card.bind("<Button-1>", lambda e, i=index: self._select_result(i))
    
    def _select_result(self, index: int):
        if index < 0 or index >= len(self.current_results):
            return
        self.selected_result = self.current_results[index]
        self._populate_detail_panel(self.selected_result)
    
    # --------------------------- Detail Panel ---------------------------
    
    def _populate_detail_panel(self, result: Dict[str, Any]):
        """Fill right panel with recipe data + render first relevant page."""
        self.detail_title.configure(text=result.get("title", "Recipe"))
        
        src = f"{result.get('cookbook_title', '')} — {result.get('page_info', '')}"
        self.detail_source.configure(text=src)
        
        # Ingredients
        self.ingredients_box.delete("0.0", "end")
        ings = result.get("ingredients", "") or result.get("instructions", "")[:500]
        if not ings:
            ings = "(No ingredients parsed — see page preview below)"
        self.ingredients_box.insert("0.0", ings)
        
        # Instructions
        self.instructions_box.delete("0.0", "end")
        inst = result.get("instructions", "")
        if not inst or inst == ings:
            inst = "(See the original page preview for full instructions)"
        self.instructions_box.insert("0.0", inst)
        
        # Enable buttons
        self.btn_copy.configure(state="normal")
        self.btn_open_pdf.configure(state="normal")
        
        # Render preview of the starting page
        self._render_preview_for_result(result)
    
    def _render_preview_for_result(self, result: Dict[str, Any]):
        """Render the PDF page image for the selected result."""
        # Clear any previous preview state (including _current_preview from another recipe)
        # This ensures that when the user selects a new recipe, we start fresh.
        self._clear_preview()

        pdf_path = result.get("cookbook_path")
        page_num = result.get("page_start", 0)
        
        if not pdf_path or not Path(pdf_path).exists():
            self._reset_preview_to_text("PDF file not found on disk")
            return
        
        try:
            # Render at a good UI size (target ~300px wide for the preview area)
            img = pdf_processor.render_page_to_image(pdf_path, page_num, dpi=140, max_width=300)
            if img:
                # Force a consistent display size for reliability
                display_width = min(img.width, 300)
                ratio = display_width / img.width if img.width > 0 else 1
                display_height = int(img.height * ratio)
                
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, 
                                       size=(display_width, display_height))
                
                # Proper way to update image in CustomTkinter repeatedly
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img          # Keep raw Tk reference
                self.current_preview_image = ctk_img
                self.preview_label.update_idletasks()
                
                # Store current preview state for page nav
                self._current_preview = {
                    "pdf_path": pdf_path,
                    "page_num": page_num,
                    "total_pages": result.get("cookbook_page_count", 999),
                    "result": result,
                }
                self._update_page_nav()
            else:
                self._reset_preview_to_text("Could not render page")
        except Exception as e:
            print(f"[Preview] Error rendering page: {e}")
            self._reset_preview_to_text(f"Preview error: {e}")
    
    def _change_preview_page(self, delta: int):
        if not hasattr(self, "_current_preview"):
            return
        state = self._current_preview
        new_page = max(0, min(state["page_num"] + delta, state.get("total_pages", 200) - 1))
        if new_page == state["page_num"]:
            return
        
        state["page_num"] = new_page
        try:
            img = pdf_processor.render_page_to_image(state["pdf_path"], new_page, dpi=140, max_width=300)
            if img:
                display_width = min(img.width, 300)
                ratio = display_width / img.width if img.width > 0 else 1
                display_height = int(img.height * ratio)
                
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, 
                                       size=(display_width, display_height))
                
                # Robust image update for repeated use
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img
                self.current_preview_image = ctk_img
                self.preview_label.update_idletasks()
                self._update_page_nav()
        except Exception as e:
            print("Page change error:", e)
    
    def _update_page_nav(self):
        if not hasattr(self, "_current_preview"):
            self.page_info_label.configure(text="—")
            self.btn_prev_page.configure(state="disabled")
            self.btn_next_page.configure(state="disabled")
            return
        
        state = self._current_preview
        self.page_info_label.configure(text=f"Page {state['page_num'] + 1}")
        
        self.btn_prev_page.configure(state="normal" if state["page_num"] > 0 else "disabled")
        # We don't know exact total easily here, so leave enabled
        self.btn_next_page.configure(state="normal")
    
    def _clear_preview(self):
        """Reset preview area (used when clearing the whole detail panel)."""
        try:
            self.preview_label.configure(image=None, text="No preview")
        except Exception:
            pass
        self.preview_label.image = None
        self.current_preview_image = None
        if hasattr(self, "_current_preview"):
            del self._current_preview

    def _reset_preview_to_text(self, text: str):
        """Safely reset the preview label to show only text (used on errors)."""
        try:
            self.preview_label.configure(image=None, text=text)
        except Exception:
            pass
        self.preview_label.image = None
        self.current_preview_image = None
        if hasattr(self, "_current_preview"):
            del self._current_preview
    
    def _clear_detail_panel(self):
        self.detail_title.configure(text="Select a recipe")
        self.detail_source.configure(text="")
        self.ingredients_box.delete("0.0", "end")
        self.instructions_box.delete("0.0", "end")
        self.btn_copy.configure(state="disabled")
        self.btn_open_pdf.configure(state="disabled")
        self._clear_preview()
        self.page_info_label.configure(text="—")
    
    # --------------------------- Actions ---------------------------
    
    def _copy_ingredients(self):
        if not self.selected_result:
            return
        text = self.ingredients_box.get("0.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo(APP_NAME, "Ingredients copied to clipboard!")
    
    def _open_in_pdf_reader(self):
        if not self.selected_result:
            return

        path = self.selected_result.get("cookbook_path")
        if not path or not Path(path).exists():
            messagebox.showwarning("File not found", "The PDF file could not be located.")
            return

        # Determine which page to open.
        # We now trust the internal preview state (_current_preview) as the source of truth.
        # This is updated whenever you use the ◀ ▶ buttons or select a new recipe.
        if hasattr(self, "_current_preview") and self._current_preview:
            page_num = self._current_preview.get("page_num", 0) + 1
            print(f"[Open PDF] Using page from current preview: {page_num}")
        else:
            page_start = self.selected_result.get("page_start", 0)
            page_num = page_start + 1
            print(f"[Open PDF] No preview state — using original page_start: {page_num}")

        # Strategy 1: File URI with #page fragment (works for Edge, Chrome, some viewers)
        try:
            file_uri = f'file:///{path.replace("\\", "/")}#page={page_num}'
            os.startfile(file_uri)
            return
        except Exception:
            pass

        # Strategy 2: Try via webbrowser module (sometimes passes fragment more reliably)
        try:
            import webbrowser
            file_uri = f'file:///{path.replace("\\", "/")}#page={page_num}'
            webbrowser.open(file_uri)
            return
        except Exception:
            pass

        # Strategy 3: Aggressively try to find and launch Adobe (Reader or full Acrobat) with /A parameter
        adobe_paths = [
            r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"C:\Program Files\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"C:\Program Files (x86)\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
            r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
            r"C:\Program Files (x86)\Adobe\Acrobat 2020\Acrobat\Acrobat.exe",
            r"C:\Program Files\Adobe\Acrobat 2020\Acrobat\Acrobat.exe",
            r"C:\Program Files (x86)\Adobe\Acrobat 2024\Acrobat\Acrobat.exe",
            r"C:\Program Files\Adobe\Acrobat 2024\Acrobat\Acrobat.exe",
        ]
        for adobe_exe in adobe_paths:
            if Path(adobe_exe).exists():
                try:
                    import subprocess
                    subprocess.Popen([adobe_exe, "/A", f"page={page_num}", path])
                    return
                except Exception:
                    pass

        # Final fallback
        try:
            os.startfile(path)
            try:
                self.clipboard_clear()
                self.clipboard_append(str(page_num))
                clipboard_msg = f"\n(Page number {page_num} has been copied to your clipboard.)"
            except Exception:
                clipboard_msg = ""

            messagebox.showinfo(
                APP_NAME,
                f"PDF opened in your default viewer.\n\n"
                f"Please navigate manually to page {page_num}.{clipboard_msg}\n\n"
                f"Automatic page jumping is not supported by all PDF viewers."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not open PDF:\n{e}")
    
    def _filter_by_cookbook(self, cookbook_id: int):
        """Show only recipes from one cookbook (simple implementation)."""
        cb = db.get_cookbook_by_id(cookbook_id)
        if not cb:
            return
        
        recipes = db.get_recipes_for_cookbook(cookbook_id)
        if not recipes:
            messagebox.showinfo(APP_NAME, "No recipes were detected in this cookbook yet.\nTry re-scanning it.")
            return
        
        # Convert to result-like shape for display
        self.current_results = []
        for r in recipes:
            self.current_results.append({
                "id": r["id"],
                "title": r["title"],
                "page_start": r["page_start"],
                "page_end": r["page_end"],
                "ingredients": r.get("ingredients", ""),
                "instructions": r.get("instructions", ""),
                "cookbook_title": cb["title"],
                "cookbook_path": cb["filepath"],
                "cookbook_id": cb["id"],
                "page_info": f"pp.{r['page_start']+1}-{r['page_end']+1}",
            })
        
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, f"[Filtered: {cb['title']}]")
        self._render_results_cards()
    
    # --------------------------- Library & Indexing ---------------------------
    
    def _choose_library_folder(self):
        folder = filedialog.askdirectory(title="Choose your PDF Cookbooks folder")
        if folder:
            self.library_folder = folder
            self.settings["library_folder"] = folder
            save_settings(self.settings)
            messagebox.showinfo(APP_NAME, 
                f"Library folder set to:\n{folder}\n\nClick 'Scan / Reindex All' to index your PDFs.")
            self._update_stats()
    
    def _add_cookbook(self):
        """Button handler for 'Add Cookbook'. Opens the C: drive and lets the user choose PDF file(s) to add."""
        files = filedialog.askopenfilenames(
            title="Add Cookbook - Select PDF file(s)",
            initialdir="C:\\",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if not files:
            return

        added = 0
        errors = []

        self._set_ui_busy(True)

        for filepath in files:
            try:
                p = Path(filepath)
                if not p.exists() or p.suffix.lower() != ".pdf":
                    errors.append(f"{p.name} (not a valid PDF)")
                    continue

                # This adds the cookbook to DB + fully indexes it
                indexer.index_single_pdf(p)
                added += 1
            except Exception as e:
                errors.append(f"{Path(filepath).name}: {str(e)[:80]}")

        self._set_ui_busy(False)

        # Refresh the whole UI
        self._refresh_cookbook_list()
        self._update_stats()
        self._clear_search()

        if added > 0:
            msg = f"Added and indexed {added} cookbook(s)."
            if errors:
                msg += f"\n\n{len(errors)} file(s) had issues:\n" + "\n".join(errors[:4])
            messagebox.showinfo(APP_NAME, msg)
        elif errors:
            messagebox.showerror(APP_NAME, "Could not add the selected files:\n\n" + "\n".join(errors[:5]))

    def _remove_cookbook(self, cookbook_id: int):
        """Remove a single cookbook from the index (PDF file itself is not deleted)."""
        cb = db.get_cookbook_by_id(cookbook_id)
        if not cb:
            return

        title = cb.get("title", "this cookbook")
        if not messagebox.askyesno(
            APP_NAME,
            f"Remove “{title}” from your library?\n\n"
            "This will delete it from search results only.\n"
            "Your original PDF file will stay on disk."
        ):
            return

        try:
            db.delete_cookbook(cookbook_id)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Failed to remove cookbook:\n{e}")
            return

        self._refresh_cookbook_list()
        self._update_stats()
        self._clear_search()

    def _start_full_reindex(self):
        if not self.library_folder:
            messagebox.showwarning(APP_NAME, "Please set your Library Folder first (top left button).")
            self._choose_library_folder()
            return
        
        if not Path(self.library_folder).exists():
            messagebox.showerror(APP_NAME, "The library folder no longer exists.")
            return
        
        # Confirmation for potentially long operation
        if not messagebox.askyesno(APP_NAME, 
                "This will scan all PDFs in your library folder and may take a while.\n\nContinue?"):
            return
        
        # Disable UI during indexing
        self._set_ui_busy(True)
        
        progress_win = ctk.CTkToplevel(self)
        progress_win.title("Indexing Cookbooks")
        progress_win.geometry("420x160")
        progress_win.resizable(False, False)
        
        status_label = ctk.CTkLabel(progress_win, text="Starting scan...", font=ctk.CTkFont(size=13))
        status_label.pack(pady=16)
        
        progress_bar = ctk.CTkProgressBar(progress_win, width=360)
        progress_bar.pack(pady=8)
        progress_bar.set(0)
        
        detail_label = ctk.CTkLabel(progress_win, text="", font=ctk.CTkFont(size=11), text_color="gray60")
        detail_label.pack(pady=4)
        
        def progress_cb(filename: str, current: int, total: int):
            pct = current / total if total > 0 else 0
            progress_bar.set(pct)
            status_label.configure(text=f"Processing ({current}/{total})")
            detail_label.configure(text=filename)
            progress_win.update_idletasks()
        
        def worker():
            try:
                result = indexer.full_reindex(
                    self.library_folder,
                    progress_callback=progress_cb,
                    recursive=True
                )
                self.after(0, lambda: self._indexing_finished(result, progress_win))
            except Exception as ex:
                self.after(0, lambda: self._indexing_error(str(ex), progress_win))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _indexing_finished(self, result: Dict[str, Any], progress_win: ctk.CTkToplevel):
        progress_win.destroy()
        self._set_ui_busy(False)
        
        msg = f"Indexed {result['indexed']} cookbooks"
        if result.get("errors"):
            msg += f" ({result['errors']} errors)"
        
        messagebox.showinfo(APP_NAME, msg)
        
        # Refresh everything
        self._refresh_cookbook_list()
        self._update_stats()
        self._clear_search()
    
    def _indexing_error(self, error_msg: str, progress_win: ctk.CTkToplevel):
        progress_win.destroy()
        self._set_ui_busy(False)
        messagebox.showerror(APP_NAME, f"Indexing failed:\n{error_msg}")
    
    def _set_ui_busy(self, busy: bool):
        """Simple busy state (disables some controls)."""
        state = "disabled" if busy else "normal"
        # We could gray out more things; for now just the search
        self.search_entry.configure(state=state)
    
    # --------------------------- Settings ---------------------------
    
    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("480x320")
        win.resizable(False, False)
        
        ctk.CTkLabel(win, text="RecipePDF Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=16)
        
        # Library path
        lib_frame = ctk.CTkFrame(win, fg_color="transparent")
        lib_frame.pack(fill="x", padx=20, pady=8)
        
        ctk.CTkLabel(lib_frame, text="Current Library Folder:").pack(anchor="w")
        lib_path_var = ctk.StringVar(value=self.library_folder or "(not set)")
        ctk.CTkLabel(lib_frame, textvariable=lib_path_var, text_color=ACCENT_COLOR,
                     wraplength=420).pack(anchor="w", pady=2)
        
        def choose_new():
            folder = filedialog.askdirectory(title="Choose Library Folder")
            if folder:
                self.library_folder = folder
                self.settings["library_folder"] = folder
                save_settings(self.settings)
                lib_path_var.set(folder)
        
        ctk.CTkButton(lib_frame, text="Change Library Folder", command=choose_new).pack(pady=8)
        
        # Danger zone
        ctk.CTkLabel(win, text="Danger Zone", font=ctk.CTkFont(weight="bold"),
                     text_color="#E57373").pack(anchor="w", padx=20, pady=(16, 4))
        
        def do_clear():
            if messagebox.askyesno("Clear All Data", 
                    "This will DELETE the entire search index.\nYour PDF files will NOT be deleted.\n\nAre you sure?"):
                db.clear_all_data()
                self._refresh_cookbook_list()
                self._update_stats()
                self._clear_search()
                messagebox.showinfo(APP_NAME, "All indexed data cleared.")
                win.destroy()
        
        ctk.CTkButton(win, text="Clear Entire Index (keep PDFs)", fg_color="#8B3A3A",
                      command=do_clear).pack(padx=20, pady=4, anchor="w")
        
        ctk.CTkLabel(win, text="Tip: Just delete the %LOCALAPPDATA%\\RecipePDF folder to completely reset.",
                     font=ctk.CTkFont(size=10), text_color="gray50").pack(padx=20, pady=10, anchor="w")
    
# --------------------------- Entry Point ---------------------------

def main():
    # Make sure DB exists
    db.init_db()
    
    app = RecipePDFApp()
    
    # Windows-specific: nice taskbar icon (if we had a .ico)
    try:
        import ctypes
        myappid = f"recipepdf.app.{APP_VERSION}"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
    
    app.mainloop()


if __name__ == "__main__":
    main()
