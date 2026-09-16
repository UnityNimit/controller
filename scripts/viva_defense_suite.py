#!/usr/bin/env python3
"""
Legacy wrapper for benchmark_suite.py.
Forwarding all calls to benchmark_suite for compatibility.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.benchmark_suite import main

if __name__ == "__main__":
    main()
