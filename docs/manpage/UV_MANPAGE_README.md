# UV Man Page Installation

This document describes how to install and use the man page with `uv` package management.

## Quick Installation

### Option 1: Install Package and Man Page

```bash
# Install the package with uv
uv pip install .

# Install the man page
python install_manpage.py
```

### Option 2: Install Package and Man Page in One Step

```bash
# Install package and run post-install script
uv pip install . && python install_manpage.py
```

### Option 3: Development Installation

```bash
# Install in development mode
uv pip install -e .

# Install man page
python install_manpage.py
```

## Verification

After installation, verify the man page is working:

```bash
# Check if man page is installed
python install_manpage.py --check

# View the man page
man gen

# Test the gen command
gen --help
```

## Manual Installation

If the automatic installation doesn't work, you can install manually:

```bash
# Find the package location
python -c "import content_generator; print(content_generator.__file__)"

# Install man page manually
./docs/manpage/install_manpage.sh
```

## Troubleshooting

### Man page not found

If `man gen` returns "No manual entry for gen":

1. Check if the man page is installed:
   ```bash
   python install_manpage.py --check
   ```

2. Verify MANPATH is set:
   ```bash
   echo $MANPATH
   ```

3. Restart your shell or reload configuration:
   ```bash
   source ~/.bashrc  # or ~/.zshrc
   ```

### Package not found

If the package is not found during installation:

1. Make sure you're in the correct directory:
   ```bash
   pwd  # Should be in the content_generator directory
   ```

2. Check if pyproject.toml exists:
   ```bash
   ls pyproject.toml
   ```

3. Try installing with explicit path:
   ```bash
   uv pip install -e .
   ```

## UV-Specific Features

The UV installation script provides:

- **Automatic package detection**: Finds the installed package location
- **User-local installation**: Installs to `~/.local/share/man/man1/`
- **Shell configuration**: Updates `.bashrc` or `.zshrc` with MANPATH
- **Installation verification**: Tests if the man page is accessible
- **Fallback options**: Multiple installation methods

## Package Structure

When installed with UV, the package includes:

```
content-generator/
├── src/
│   └── content_generator/
├── docs/
│   └── manpage/
│       ├── gen.1                          # Man page
│       ├── MANPAGE_INSTALL.md            # Installation guide
│       ├── README_MANPAGE.md             # Man page documentation (in docs/)
│       ├── UV_MANPAGE_README.md          # UV-specific guide
│       ├── install_manpage.sh            # Manual installation script
│       ├── build_hooks.py                # Build hooks
│       ├── post_install.py               # Post-install script
│       ├── setup_manpage.py              # Setup script
│       └── uv_install_manpage.py         # UV-specific installer
└── install_manpage.py                    # Root wrapper script
```

## Environment Variables

The installation may set these environment variables:

- `MANPATH`: Updated to include `~/.local/share/man`

## Commands

### Available Commands

```bash
# Install man page
python install_manpage.py

# Check installation status
python install_manpage.py --check

# Install system-wide (requires sudo)
python setup_manpage.py --system

# Install for current user
python setup_manpage.py --user

# Uninstall man page
python setup_manpage.py --uninstall
```

### Gen Tool Commands

```bash
# View help
gen --help

# Initialize a course
gen init --course-name "My Course"

# Create configuration
gen config --template tafe

# Generate documents
gen push --target /path/to/course
```

## Integration with UV

The man page installation is designed to work seamlessly with UV:

1. **Package installation**: UV installs the package with all man page files
2. **Post-installation**: Run the UV-specific installer to set up the man page
3. **Environment management**: UV manages the Python environment, we handle the man page
4. **Development workflow**: Works with `uv pip install -e .` for development

## Best Practices

1. **Always install man page after package installation**
2. **Use user-local installation for development**
3. **Check installation status before using**
4. **Restart shell after installation**
5. **Keep man page updated with package updates**

## Support

For issues with UV man page installation:

1. Check this documentation
2. Run `python install_manpage.py --check`
3. Try manual installation with `./docs/manpage/install_manpage.sh`
4. Report bugs to project maintainers 