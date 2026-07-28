#!/usr/bin/env python3
"""
Compile django.po translation file to django.mo binary format.

This script uses polib to compile the Arabic translation catalog.
Run from any directory - paths are resolved relative to the script location.

Usage:
    python scripts/compile_po.py
"""

import sys
from pathlib import Path

try:
    import polib
except ImportError:
    print("Error: polib is not installed.")
    print("Install it with: pip install polib")
    sys.exit(1)

# Resolve paths relative to script location
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
po_path = project_root / "locale" / "ar" / "LC_MESSAGES" / "django.po"
mo_path = po_path.with_suffix(".mo")

# Verify PO file exists
if not po_path.exists():
    print(f"Error: PO file not found at {po_path}")
    sys.exit(1)

# Load and compile
try:
    print(f"Loading translation file: {po_path}")
    po = polib.pofile(str(po_path))
    
    # Display statistics
    total = len(po)
    translated = len([e for e in po if e.msgstr and not e.obsolete])
    untranslated = len([e for e in po if not e.msgstr and not e.obsolete])
    
    print(f"\nTranslation statistics:")
    print(f"  Total entries: {total}")
    print(f"  Translated: {translated}")
    print(f"  Untranslated: {untranslated}")
    
    if translated > 0:
        percentage = (translated / max(total, 1)) * 100
        print(f"  Completion: {percentage:.1f}%")
    
    # Compile to .mo
    print(f"\nCompiling to: {mo_path}")
    po.save_as_mofile(str(mo_path))
    
    print(f"OK: compiled {translated} entries -> {mo_path}")
    print("Activate via language switcher or LANGUAGE_CODE=ar")
    
except Exception as e:
    print(f"Error compiling PO file: {e}")
    sys.exit(1)
