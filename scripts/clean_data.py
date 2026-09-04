#!/usr/bin/env python3
"""
Clean Data Script Launcher (scripts/clean_data.py)
Forwards directly to clean_test_data.py for full database data wipe.
"""
import sys
from pathlib import Path

# Forward execution to clean_test_data.py
script_path = Path(__file__).resolve().parent / "clean_test_data.py"
import runpy
runpy.run_path(str(script_path), run_name="__main__")
