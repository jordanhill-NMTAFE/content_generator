#!/usr/bin/env python3
"""
Setup script for man page installation.
Can be run manually or as part of the package installation process.
"""

import argparse
import os
import sys
from pathlib import Path

# Add the build_hooks module to the path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from build_hooks import post_install_manpage, install_manpage, get_install_dirs
except ImportError as e:
    print(f"❌ Could not import build hooks: {e}")
    sys.exit(1)


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Install man page for gen tool")
    parser.add_argument(
        "--system", action="store_true", help="Install system-wide (requires sudo)"
    )
    parser.add_argument(
        "--user", action="store_true", help="Install for current user only"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check if man page is already installed"
    )
    parser.add_argument(
        "--uninstall", action="store_true", help="Uninstall the man page"
    )

    args = parser.parse_args()

    if args.check:
        check_installation()
    elif args.uninstall:
        uninstall_manpage()
    elif args.system:
        install_system_wide()
    elif args.user:
        install_user_local()
    else:
        # Default behavior - use post_install_manpage
        post_install_manpage()


def check_installation():
    """Check if the man page is already installed."""
    print("🔍 Checking man page installation...")

    # Check system locations
    system_locations = [
        Path("/usr/local/share/man/man1/gen.1"),
        Path("/usr/share/man/man1/gen.1"),
        Path.home() / ".local/share/man/man1/gen.1",
    ]

    found = False
    for location in system_locations:
        if location.exists():
            print(f"✅ Found man page at: {location}")
            found = True

    if not found:
        print("❌ Man page not found in any standard location")
        return False

    # Test if man command works
    try:
        import subprocess

        result = subprocess.run(
            ["man", "gen"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print("✅ Man page is accessible via 'man gen'")
        else:
            print("⚠️  Man page found but not accessible via 'man gen'")
    except Exception as e:
        print(f"⚠️  Could not test man page access: {e}")

    return True


def uninstall_manpage():
    """Uninstall the man page."""
    print("🗑️  Uninstalling man page...")

    # Get installation directories
    install_dirs = get_install_dirs()
    man_dir = install_dirs["man_dir"]
    is_system = install_dirs["is_system"]

    manpage_path = man_dir / "gen.1"

    if not manpage_path.exists():
        print("❌ Man page not found at expected location")
        return

    try:
        if is_system:
            # System installation - need sudo
            import subprocess

            subprocess.run(["sudo", "rm", str(manpage_path)], check=True)
            print("✅ Man page uninstalled from system location")
        else:
            # User installation
            manpage_path.unlink()
            print("✅ Man page uninstalled from user location")

        # Update man database
        try:
            for cmd in ["mandb", "makewhatis"]:
                try:
                    if is_system:
                        subprocess.run(["sudo", cmd], check=True)
                    else:
                        subprocess.run([cmd], check=True)
                    print(f"✅ Updated man database using: {cmd}")
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
        except Exception as e:
            print(f"⚠️  Could not update man database: {e}")

    except Exception as e:
        print(f"❌ Failed to uninstall man page: {e}")


def install_system_wide():
    """Install man page system-wide."""
    print("🔧 Installing man page system-wide...")

    # Get the package directory
    try:
        import content_generator

        package_dir = Path(content_generator.__file__).parent.parent
    except ImportError:
        package_dir = Path(__file__).parent

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
            print("❌ Man page source not found")
            return

    # Create post-install script for system installation
    post_install_script = package_dir / "post_install_manpage.sh"

    script_content = f"""#!/bin/bash
# Post-installation script for man page installation
# Run this script with sudo to install the man page system-wide

set -e

MANPAGE_SOURCE="{manpage_source}"
MAN_DIR="/usr/local/share/man/man1"

echo "Installing man page to $MAN_DIR..."

# Create man directory if it doesn't exist
sudo mkdir -p "$MAN_DIR"

# Copy man page
sudo cp "$MANPAGE_SOURCE" "$MAN_DIR/"

# Set proper permissions
sudo chmod 644 "$MAN_DIR/gen.1"

# Update man database
if command -v mandb >/dev/null 2>&1; then
    sudo mandb
elif command -v makewhatis >/dev/null 2>&1; then
    sudo makewhatis
else
    echo "Warning: Could not update man database"
fi

echo "✅ Man page installed successfully!"
echo "You can now use: man gen"
"""

    with open(post_install_script, "w") as f:
        f.write(script_content)

    os.chmod(post_install_script, 0o755)
    print(f"📝 Created post-install script: {post_install_script}")
    print("💡 Run 'sudo ./post_install_manpage.sh' to install the man page system-wide")


def install_user_local():
    """Install man page for current user."""
    print("👤 Installing man page for current user...")

    # Get the package directory
    try:
        import content_generator

        package_dir = Path(content_generator.__file__).parent.parent
    except ImportError:
        package_dir = Path(__file__).parent

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
            print("❌ Man page source not found")
            return

    # Get installation directories
    install_dirs = get_install_dirs()
    man_dir = Path.home() / ".local/share/man/man1"  # Force user installation

    install_manpage(manpage_source, man_dir)

    # Add to MANPATH if needed
    shell_config = None
    for config_file in [".bashrc", ".zshrc", ".bash_profile"]:
        config_path = Path.home() / config_file
        if config_path.exists():
            shell_config = config_path
            break

    if shell_config:
        manpath_line = 'export MANPATH="$HOME/.local/share/man:$MANPATH"'
        try:
            with open(shell_config, "r") as f:
                content = f.read()

            if manpath_line not in content:
                with open(shell_config, "a") as f:
                    f.write(f"\n# Added by content-generator\n{manpath_line}\n")
                print(f"📝 Added MANPATH to {shell_config}")
                print(
                    "💡 Please restart your shell or run: source " + str(shell_config)
                )
            else:
                print("✅ MANPATH already configured")
        except Exception as e:
            print(f"⚠️  Could not update shell config: {e}")

    print("✅ Man page installed for current user")
    print("💡 You can now use: man gen")


if __name__ == "__main__":
    main()
