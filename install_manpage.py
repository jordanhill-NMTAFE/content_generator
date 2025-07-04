#!/usr/bin/env python3
"""
Simple wrapper script to install the man page.
This script delegates to the actual installation scripts in docs/manpage/.
"""

import sys
from pathlib import Path

# Add the docs/manpage directory to the path
manpage_dir = Path(__file__).parent / "docs" / "manpage"
sys.path.insert(0, str(manpage_dir))

try:
    from uv_install_manpage import main

    main()
except ImportError as e:
    print(f"❌ Could not import man page installer: {e}")
    print("💡 Make sure you're running this from the project root directory")
    sys.exit(1)
