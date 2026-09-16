#!/usr/bin/env python3
"""
Legacy wrapper for export_telemetry_graphs.py.
Forwarding all calls for compatibility.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.export_telemetry_graphs import generate_telemetry_figures

if __name__ == "__main__":
    generate_telemetry_figures()
