#!/usr/bin/env python3
"""
UV-specific man page installation script.
This script is designed to work with uv package management.
"""

import os
import sys
from pathlib import Path


def install_manpage_uv():
    """Install man page using uv package management."""
    print("📖 Installing man page with uv...")

    # Get the package directory from uv
    try:
        # Try to get the package location from the installed package
        import content_generator

        package_dir = Path(content_generator.__file__).parent.parent
        print(f"📦 Found package at: {package_dir}")
    except ImportError:
        # Fallback for development
        package_dir = Path(__file__).parent
        print(f"🔧 Using development directory: {package_dir}")

        # Look for the man page in the package
    manpage_source = package_dir / "docs" / "manpage" / "gen.1"

    if not manpage_source.exists():
        # Try alternative locations
        alt_locations = [
            package_dir / "gen.1",
            package_dir / "share" / "man" / "man1" / "gen.1",
            package_dir / "share" / "doc" / "content-generator" / "gen.1",
        ]

        for location in alt_locations:
            if location.exists():
                manpage_source = location
                break
        else:
            print("❌ Man page not found in package")
            print("💡 Available files in package:")
            for file in package_dir.rglob("*"):
                if file.is_file():
                    print(f"   {file.relative_to(package_dir)}")
            return False

    print(f"✅ Found man page at: {manpage_source}")

    # Determine installation location
    # For uv, we typically want user-local installation
    user_man_dir = Path.home() / ".local/share/man/man1"

    try:
        # Create the man directory
        user_man_dir.mkdir(parents=True, exist_ok=True)

        # Copy the man page
        import shutil

        shutil.copy2(manpage_source, user_man_dir / "gen.1")

        # Set proper permissions
        os.chmod(user_man_dir / "gen.1", 0o644)

        print(f"✅ Man page installed to: {user_man_dir / 'gen.1'}")

        # Update shell configuration
        update_shell_config()

        # Test installation
        test_installation()

        return True

    except Exception as e:
        print(f"❌ Failed to install man page: {e}")
        return False


def update_shell_config():
    """Update shell configuration to include MANPATH."""
    shell_configs = [".bashrc", ".zshrc", ".bash_profile"]

    for config_file in shell_configs:
        config_path = Path.home() / config_file
        if config_path.exists():
            manpath_line = 'export MANPATH="$HOME/.local/share/man:$MANPATH"'

            try:
                with open(config_path, "r") as f:
                    content = f.read()

                if manpath_line not in content:
                    with open(config_path, "a") as f:
                        f.write(
                            f"\n# Added by content-generator (uv)\n{manpath_line}\n"
                        )
                    print(f"📝 Added MANPATH to {config_path}")
                    print(f"💡 Please restart your shell or run: source {config_path}")
                else:
                    print(f"✅ MANPATH already configured in {config_path}")
                break

            except Exception as e:
                print(f"⚠️  Could not update {config_path}: {e}")


def test_installation():
    """Test if the man page installation works."""
    print("🧪 Testing man page installation...")

    try:
        import subprocess

        # Test if man page is accessible
        result = subprocess.run(
            ["man", "gen"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            print("✅ Man page is accessible via 'man gen'")
        else:
            print("⚠️  Man page installed but not accessible via 'man gen'")
            print(
                '💡 Try restarting your shell or running: export MANPATH="$HOME/.local/share/man:$MANPATH"'
            )

    except Exception as e:
        print(f"⚠️  Could not test man page access: {e}")


def main():
    """Main function for uv man page installation."""
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # Check if man page is already installed
        user_man_dir = Path.home() / ".local/share/man/man1/gen.1"
        if user_man_dir.exists():
            print("✅ Man page is already installed")
            test_installation()
        else:
            print("❌ Man page is not installed")
        return

    success = install_manpage_uv()

    if success:
        print("\n🎉 Man page installation complete!")
        print("💡 You can now use: man gen")
    else:
        print("\n❌ Man page installation failed")
        print("💡 You can try manual installation: ./install_manpage.sh")


if __name__ == "__main__":
    main()
