#!/usr/bin/env python3
"""
Post-installation script for content-generator package.
Handles man page installation after package installation.
"""

import os
import sys
from pathlib import Path

# Add the build_hooks module to the path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from build_hooks import post_install_manpage

    post_install_manpage()
except ImportError as e:
    print(f"⚠️  Could not import build hooks: {e}")
    print("💡 Man page installation skipped")
except Exception as e:
    print(f"❌ Man page installation failed: {e}")
    print("💡 You can install the man page manually using: ./install_manpage.sh")
