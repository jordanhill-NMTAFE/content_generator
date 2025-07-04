#!/usr/bin/env python3
"""
Simple script to run push validation tests.
"""

import sys
from pathlib import Path

# Add tests to path
sys.path.insert(0, str(Path(__file__).parent / "tests"))

from run_push_validation import main

if __name__ == "__main__":
    main()
