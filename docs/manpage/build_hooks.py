"""
Build hooks for content-generator package.
Handles man page installation and package data inclusion.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def install_manpage(manpage_source: Path, install_dir: Path) -> None:
    """Install man page to the specified directory."""
    try:
        # Create the man directory if it doesn't exist
        install_dir.mkdir(parents=True, exist_ok=True)

        # Copy the man page
        shutil.copy2(manpage_source, install_dir / "gen.1")

        # Set proper permissions (644 for man pages)
        os.chmod(install_dir / "gen.1", 0o644)

        print(f"✅ Man page installed to: {install_dir / 'gen.1'}")

    except Exception as e:
        print(f"❌ Failed to install man page: {e}")
        raise


def update_man_database() -> None:
    """Update the man database if possible."""
    try:
        # Try different man database update commands
        for cmd in ["mandb", "makewhatis"]:
            try:
                subprocess.run([cmd], check=True, capture_output=True)
                print(f"✅ Updated man database using: {cmd}")
                return
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue

        print("⚠️  Could not update man database (mandb/makewhatis not found)")

    except Exception as e:
        print(f"⚠️  Man database update failed: {e}")


def get_install_dirs() -> Dict[str, Path]:
    """Get installation directories based on the environment."""
    # Check if we're in a virtual environment
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        # Virtual environment - install to user directory
        user_man_dir = Path.home() / ".local" / "share" / "man" / "man1"
        return {"man_dir": user_man_dir, "is_system": False}
    else:
        # System installation - install to system directory
        system_man_dir = Path("/usr/local/share/man/man1")
        return {"man_dir": system_man_dir, "is_system": True}


class BuildHook:
    """Custom build hook for man page installation."""

    def __init__(
        self, source: str, build_dir: str, target_name: str, version: str, **kwargs: Any
    ) -> None:
        self.source = Path(source)
        self.build_dir = Path(build_dir)
        self.target_name = target_name
        self.version = version

    def initialize(self, version: str, build_data: Dict[str, Any]) -> None:
        """Initialize the build process."""
        print("🔧 Initializing build with man page support...")

        # Add man page to build data
        manpage_source = self.source / "docs" / "manpage" / "gen.1"
        if manpage_source.exists():
            build_data["include"].append("docs/manpage/gen.1")
            print("✅ Man page included in build data")
        else:
            print("⚠️  Man page not found: docs/manpage/gen.1")

    def clean(self, directory: str) -> None:
        """Clean build artifacts."""
        print("🧹 Cleaning build artifacts...")
        # This is handled automatically by hatchling

    def build(self, directory: str, **kwargs: Any) -> None:
        """Build the package."""
        print("📦 Building package with man page...")

        # The actual build is handled by hatchling
        # We just need to ensure our files are included
        pass


def post_install_manpage() -> None:
    """Post-installation hook for man page installation."""
    print("📖 Installing man page...")

    # Get the package directory
    try:
        import content_generator

        package_dir = Path(content_generator.__file__).parent.parent
    except ImportError:
        # Fallback for development
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
            print("❌ Man page not found in package")
            return

    # Get installation directories
    install_dirs = get_install_dirs()
    man_dir = install_dirs["man_dir"]
    is_system = install_dirs["is_system"]

    if is_system:
        print("🔧 Installing man page system-wide...")
        # For system installation, we'll create a post-install script
        # that the user can run with sudo
        post_install_script = package_dir / "post_install_manpage.sh"

        script_content = f"""#!/bin/bash
# Post-installation script for man page installation
# Run this script with sudo to install the man page system-wide

set -e

MANPAGE_SOURCE="{manpage_source}"
MAN_DIR="{man_dir}"

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
        print(
            "💡 Run 'sudo ./post_install_manpage.sh' to install the man page system-wide"
        )

    else:
        print("👤 Installing man page for current user...")
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
                        "💡 Please restart your shell or run: source "
                        + str(shell_config)
                    )
                else:
                    print("✅ MANPATH already configured")
            except Exception as e:
                print(f"⚠️  Could not update shell config: {e}")

        print("✅ Man page installed for current user")
        print("💡 You can now use: man gen")


# Entry point for post-installation
if __name__ == "__main__":
    post_install_manpage()
