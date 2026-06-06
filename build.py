#!/usr/bin/env python3
"""
Build script for RecipePDF Windows executable using PyInstaller.
Usage: python build.py
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "recipepdf.spec"

def clean():
    """Remove previous build artifacts."""
    print("🧹 Cleaning previous builds...")
    for path in [DIST_DIR, BUILD_DIR]:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    # Remove .spec if we want to always regenerate (optional)
    # SPEC_FILE.unlink(missing_ok=True)

def create_icon():
    """Create a simple placeholder icon if none exists."""
    icon_path = PROJECT_ROOT / "assets" / "icon.ico"
    if icon_path.exists():
        print(f"✓ Using existing icon: {icon_path}")
        return str(icon_path)
    
    print("⚠️  No icon found. Creating a simple placeholder...")
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGBA', (256, 256), (33, 37, 41, 255))  # Dark background
        draw = ImageDraw.Draw(img)
        
        # Draw a simple book icon shape
        # Book shape
        draw.rounded_rectangle([50, 60, 206, 196], radius=12, fill=(248, 249, 250), outline=(108, 117, 125), width=3)
        # Spine
        draw.rectangle([60, 60, 75, 196], fill=(222, 226, 230))
        # Lines (text)
        for y in range(85, 180, 18):
            draw.rectangle([90, y, 190, y+6], fill=(73, 80, 87))
        
        # Save as .ico (multi-size)
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(icon_path, format='ICO', sizes=[(256,256), (128,128), (64,64), (32,32)])
        print(f"✓ Created placeholder icon at {icon_path}")
        return str(icon_path)
    except Exception as e:
        print(f"⚠️  Could not create icon: {e}")
        return None

def build():
    """Run PyInstaller to create the executable."""
    print("\n📦 Building RecipePDF Windows executable...\n")
    
    icon = create_icon()
    
    # Prefer spec file if it exists (more reliable for PyMuPDF)
    spec = PROJECT_ROOT / "recipepdf.spec"
    if spec.exists():
        print("Using recipepdf.spec for build (recommended)...")
        args = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            str(spec),
        ]
    else:
        # Fallback manual command
        args = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--onefile",
            "--windowed",
            "--name", "RecipePDF",
            "--clean",
        ]
        
        if icon:
            args.extend(["--icon", icon])
        
        # Add data
        assets_dir = PROJECT_ROOT / "assets"
        if assets_dir.exists():
            args.extend(["--add-data", f"{assets_dir};assets"])
        
        # Critical for PyMuPDF
        args.extend([
            "--collect-all", "pymupdf",
            "--collect-all", "fitz",
            "--hidden-import", "fitz",
            "--hidden-import", "pymupdf",
        ])
        
        # Main script
        args.append("main.py")
    
    print("Running:", " ".join(args))
    print("-" * 60)
    
    result = subprocess.run(args, cwd=PROJECT_ROOT)
    
    if result.returncode == 0:
        exe_path = DIST_DIR / "RecipePDF.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 60)
            print("✅ BUILD SUCCESSFUL!")
            print(f"   Executable: {exe_path}")
            print(f"   Size:       {size_mb:.1f} MB")
            print("=" * 60)
            print("\nYou can now distribute dist/RecipePDF.exe to any Windows PC.")
            print("Tip: Rename it or create a shortcut for your desktop/start menu.")
        else:
            print("Build reported success but exe not found. Check dist/ folder.")
    else:
        print("\n❌ Build failed. See errors above.")
        sys.exit(1)

if __name__ == "__main__":
    clean()
    build()
