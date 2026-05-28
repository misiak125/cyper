# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

# 1. PLAYWRIGHT: Pobiera ukryte binaria silnika Playwright (Node.js i CLI)
playwright_datas = collect_data_files('playwright', include_py_files=True)

# 2. PLAYWRIGHT STEALTH (NAPRAWA BŁĘDU): 
# Zmuszamy PyInstallera do skopiowania plików .js z pakietu playwright_stealth!
stealth_datas = collect_data_files('playwright_stealth')

# Łączymy wszystkie paczki danych do jednej listy
all_datas = playwright_datas + stealth_datas

# Ukryte importy, których PyInstaller często nie potrafi sam wyśledzić
hidden_imports = [
    'playwright_stealth',
    'thefuzz',
    'RapidFuzz',
    'Levenshtein',
    'bs4',
    'requests',
    'aiohttp',
    'urllib3',
    'asyncio',
    'csv',
    'json'
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=all_datas,  # <--- Tutaj przekazujemy nasze pliki JS i binaria
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cyper', 
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, 
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, 
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' 
)
