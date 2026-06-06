# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for RecipePDF.
You can build with: pyinstaller recipepdf.spec
"""

from PyInstaller.utils.hooks import collect_all
import pymupdf  # ensure it's importable

block_cipher = None

# Collect everything PyMuPDF needs (very important)
pymupdf_datas, pymupdf_binaries, pymupdf_hiddenimports = collect_all('pymupdf')
fitz_datas, fitz_binaries, fitz_hiddenimports = collect_all('fitz')

datas = []
datas += pymupdf_datas
datas += fitz_datas
# Add our assets folder if it exists
datas.append(('assets', 'assets'))

binaries = pymupdf_binaries + fitz_binaries
hiddenimports = [
    'fitz',
    'pymupdf',
    'customtkinter',
    'PIL',
    'PIL._tkinter_finder',
] + pymupdf_hiddenimports + fitz_hiddenimports

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'numpy', 'matplotlib'],  # optional size savings
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RecipePDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Windowed app (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if __import__('os').path.exists('assets/icon.ico') else None,
)
