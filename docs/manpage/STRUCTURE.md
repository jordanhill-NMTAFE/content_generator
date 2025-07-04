# Documentation Structure

This document explains the organization of documentation files in the content-generator project.

## 📁 Directory Structure

```
content-generator/
├── docs/                          # All documentation
│   ├── manpage/                   # Man page related files
│   │   ├── gen.1                  # Man page (troff format)
│   │   ├── MANPAGE_INSTALL.md     # Installation instructions (in docs/)
│   │   ├── README_MANPAGE.md      # General man page documentation (in docs/)
│   │   ├── UV_MANPAGE_README.md   # UV-specific installation guide
│   │   ├── STRUCTURE.md           # This file
│   │   ├── install_manpage.sh     # Interactive shell installer
│   │   ├── build_hooks.py         # Build system integration
│   │   ├── post_install.py        # Post-installation script
│   │   ├── setup_manpage.py       # Advanced Python installer
│   │   └── uv_install_manpage.py  # UV-specific installer
│   └── [other documentation]      # Other project documentation
├── src/                           # Source code
│   └── content_generator/
├── install_manpage.py             # Root wrapper script
└── pyproject.toml                 # Package configuration
```

## 🎯 **File Organization Principles**

### 1. **All Documentation in `docs/`**
- **Rule:** All documentation files go in the `docs/` folder unless they need to be in `src/`
- **Exception:** Only source code documentation (docstrings, API docs) should be in `src/`
- **Benefit:** Clean separation between code and documentation

### 2. **Categorized Documentation**
- **`docs/manpage/`** - Man page and installation scripts
- **`docs/api/`** - API documentation (if needed)
- **`docs/user/`** - User guides (if needed)
- **`docs/developer/`** - Developer documentation (if needed)

### 3. **Installation Scripts**
- **Primary:** `install_manpage.py` (root wrapper)
- **Secondary:** `docs/manpage/install_manpage.sh` (shell script)
- **Advanced:** `docs/manpage/setup_manpage.py` (full-featured)

## 📋 **File Descriptions**

### Man Page Files
- **`gen.1`** - The actual man page in troff format
- **`MANPAGE_INSTALL.md`** - Detailed installation instructions (in docs/)
- **`README_MANPAGE.md`** - General man page documentation (in docs/)
- **`UV_MANPAGE_README.md`** - UV-specific installation guide
- **`STRUCTURE.md`** - This documentation structure guide

### Installation Scripts
- **`install_manpage.py`** - Root wrapper script (recommended)
- **`install_manpage.sh`** - Interactive shell installer
- **`uv_install_manpage.py`** - UV-specific installer
- **`setup_manpage.py`** - Advanced installer with options
- **`build_hooks.py`** - Build system integration
- **`post_install.py`** - Post-installation hook

## 🚀 **Usage**

### For Users
```bash
# Simple installation (recommended)
python install_manpage.py

# Check installation
python install_manpage.py --check

# Interactive installation
./docs/manpage/install_manpage.sh
```

### For Developers
```bash
# Advanced installation options
python docs/manpage/setup_manpage.py --user
python docs/manpage/setup_manpage.py --system
python docs/manpage/setup_manpage.py --uninstall
```

### For Package Builders
- The `pyproject.toml` includes all necessary files
- Build hooks handle man page inclusion
- Shared data mapping ensures proper installation

## 🔧 **Configuration**

### PyProject.toml Integration
```toml
[tool.hatch.build.targets.wheel]
include = [
    "docs/manpage/gen.1",
    "docs/manpage/MANPAGE_INSTALL.md",
    # ... other files
]

[tool.hatch.build.targets.wheel.shared-data]
"docs/manpage/gen.1" = "share/man/man1/gen.1"
# ... other mappings
```

### Build Hooks
- **Location:** `docs/manpage/build_hooks.py`
- **Purpose:** Integrate with Python build system
- **Function:** Include man page in package data

## 📖 **Documentation Standards**

### File Naming
- **Man pages:** `*.1` (section 1 - user commands)
- **Markdown:** `*.md` (documentation)
- **Scripts:** `*_install_manpage.py` (Python installers)
- **Shell scripts:** `install_manpage.sh` (shell installer)

### Content Organization
- **README files:** Overview and quick start
- **Install guides:** Step-by-step instructions
- **Structure docs:** File organization explanation
- **API docs:** Technical reference (if needed)

## 🔄 **Maintenance**

### Adding New Documentation
1. Place in appropriate `docs/` subdirectory
2. Update this `STRUCTURE.md` if needed
3. Update `pyproject.toml` if including in package
4. Update relevant README files

### Updating Man Page
1. Edit `docs/manpage/gen.1`
2. Test formatting: `groff -man -Tascii docs/manpage/gen.1`
3. Update installation scripts if needed
4. Test installation process

### Package Updates
1. Update version in `pyproject.toml`
2. Test build process
3. Verify man page installation
4. Update documentation if needed

## ✅ **Benefits of This Structure**

1. **Clean Separation:** Code and documentation are clearly separated
2. **Easy Navigation:** Logical organization makes files easy to find
3. **Scalable:** Easy to add new documentation categories
4. **Maintainable:** Clear structure makes updates straightforward
5. **Professional:** Follows industry best practices
6. **User-Friendly:** Simple entry points for different user types

This structure ensures that all documentation is properly organized, easily accessible, and maintainable while following Python packaging best practices. 