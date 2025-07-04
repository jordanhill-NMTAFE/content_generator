# Man Page Documentation

This directory contains the man page documentation for the `gen` tool, providing comprehensive command-line reference documentation.

## Files

- **`gen.1`** - The main man page file in troff format
- **`install_manpage.sh`** - Automated installation script
- **`MANPAGE_INSTALL.md`** - Detailed installation instructions
- **`README_MANPAGE.md`** - This documentation file

## Quick Installation

### Option 1: Automated Installation (Recommended)

```bash
# Run the installation script
./install_manpage.sh
```

The script will:
- Test the man page formatting
- Offer system-wide or user-local installation
- Handle permissions and MANPATH configuration
- Provide verification steps

### Option 2: Manual Installation

```bash
# System-wide installation
sudo cp gen.1 /usr/local/share/man/man1/
sudo mandb

# User-local installation
mkdir -p ~/.local/share/man/man1/
cp gen.1 ~/.local/share/man/man1/
echo 'export MANPATH="$HOME/.local/share/man:$MANPATH"' >> ~/.bashrc
```

## Using the Man Page

After installation, you can access the documentation with:

```bash
# View the full man page
man gen

# Search for specific sections
man gen | grep -A 5 "EXAMPLES"

# Quick help
man gen | head -20
```

## Man Page Sections

The man page is organized into the following sections:

### Core Sections
- **NAME** - Tool name and brief description
- **SYNOPSIS** - Command syntax and usage
- **DESCRIPTION** - Detailed tool description and capabilities

### Commands
- **init** - Initialize new course content folders
- **push** - Generate academic documents
- **config** - Manage configuration files

### Reference
- **TEMPLATE TYPES** - Available configuration templates
- **EXAMPLES** - Practical usage examples
- **CONFIGURATION FILES** - YAML configuration format
- **ENVIRONMENT VARIABLES** - Required environment setup
- **FILES** - Important files and directories

### Metadata
- **EXIT STATUS** - Return codes and meanings
- **BUGS** - Bug reporting information
- **AUTHOR** - Tool authors
- **COPYRIGHT** - Copyright information
- **SEE ALSO** - Related commands and documentation

## Template Types Covered

The man page documents all available template types:

1. **basic** - Simple template with placeholders
2. **tafe** - TAFE-specific configuration
3. **commercial** - Professional training setup
4. **accelerated** - Fast-paced intensive learning
5. **custom** - Fully customizable template

## Examples Included

The man page provides practical examples for:

- Basic course initialization
- Configuration file usage
- Template creation
- Custom parameter usage
- Document generation

## Formatting and Standards

The man page follows standard Unix man page conventions:

- **Section 1** - User commands
- **Troff formatting** - Standard man page markup
- **Cross-references** - Links to related commands
- **Consistent structure** - Follows man page best practices

## Testing the Man Page

You can test the man page formatting:

```bash
# Test with groff (if available)
groff -man -Tascii gen.1 | head -20

# Test installation
man gen

# Search for the man page
man -k gen
```

## Troubleshooting

### Common Issues

1. **Man page not found**
   - Check installation location
   - Verify MANPATH configuration
   - Update man database

2. **Formatting issues**
   - Verify troff syntax
   - Check file permissions
   - Test with groff

3. **Installation problems**
   - Check file existence
   - Verify permissions
   - Review error messages

### Verification Commands

```bash
# Check if man page is installed
find /usr/local/share/man -name "gen.1"
find ~/.local/share/man -name "gen.1"

# Check MANPATH
echo $MANPATH

# Test man page access
man gen

# Update man database
sudo mandb
```

## Contributing

To update the man page:

1. Edit `gen.1` using standard troff formatting
2. Test formatting with `groff -man -Tascii gen.1`
3. Update installation scripts if needed
4. Test installation process
5. Submit pull request with changes

### Man Page Formatting Tips

- Use `.TH` for title header
- Use `.SH` for section headers
- Use `.SS` for subsection headers
- Use `.TP` for tagged paragraphs
- Use `.BR` for bold text
- Use `.I` for italic text
- Use `.EX` and `.EE` for examples

## Related Documentation

- **CLI Help** - `gen --help` and `gen <command> --help`
- **Configuration Guide** - See `MANPAGE_INSTALL.md`
- **Project Documentation** - Main project README
- **API Documentation** - Source code documentation

## Support

For issues with the man page:

1. Check this documentation
2. Review installation instructions
3. Test with different systems
4. Report bugs to project maintainers 