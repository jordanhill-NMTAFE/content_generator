# Man Page Installation

This document describes how to install the man page for the `gen` tool.

## Installation Options

### Option 1: System-wide Installation (Recommended)

Install the man page system-wide so it's available to all users:

```bash
# Copy the man page to the system man directory
sudo cp gen.1 /usr/local/share/man/man1/

# Update the man database
sudo mandb
```

### Option 2: User-specific Installation

Install the man page for the current user only:

```bash
# Create user man directory if it doesn't exist
mkdir -p ~/.local/share/man/man1/

# Copy the man page
cp gen.1 ~/.local/share/man/man1/

# Add to MANPATH if not already set
echo 'export MANPATH="$HOME/.local/share/man:$MANPATH"' >> ~/.bashrc
# or for zsh:
echo 'export MANPATH="$HOME/.local/share/man:$MANPATH"' >> ~/.zshrc
```

### Option 3: Package Manager Installation

If you're using a package manager, you can include the man page in your package:

```bash
# For Debian/Ubuntu packages
sudo cp gen.1 /usr/share/man/man1/

# For RPM packages
sudo cp gen.1 /usr/share/man/man1/
```

## Verification

After installation, verify the man page is working:

```bash
# View the man page
man gen

# Search for the man page
man -k gen
```

## Uninstallation

To remove the man page:

```bash
# System-wide removal
sudo rm /usr/local/share/man/man1/gen.1
sudo mandb

# User-specific removal
rm ~/.local/share/man/man1/gen.1
```

## Troubleshooting

### Man page not found

If `man gen` returns "No manual entry for gen":

1. Check if the man page is in the correct location:
   ```bash
   find /usr/local/share/man -name "gen.1"
   find ~/.local/share/man -name "gen.1"
   ```

2. Verify the MANPATH includes the correct directory:
   ```bash
   echo $MANPATH
   ```

3. Update the man database:
   ```bash
   sudo mandb
   ```

### Formatting issues

If the man page displays with formatting issues:

1. Check that the man page file has the correct permissions:
   ```bash
   ls -la gen.1
   ```

2. Verify the file is not corrupted:
   ```bash
   man -l gen.1
   ```

## Man Page Sections

The man page is organized into the following sections:

- **NAME**: Tool name and brief description
- **SYNOPSIS**: Command syntax
- **DESCRIPTION**: Detailed tool description
- **COMMANDS**: Available subcommands (init, push, config)
- **TEMPLATE TYPES**: Available configuration templates
- **EXAMPLES**: Usage examples
- **CONFIGURATION FILES**: YAML configuration format
- **ENVIRONMENT VARIABLES**: Required environment variables
- **FILES**: Important files and directories
- **EXIT STATUS**: Return codes
- **BUGS**: Bug reporting information
- **AUTHOR**: Tool authors
- **COPYRIGHT**: Copyright information
- **SEE ALSO**: Related commands and documentation

## Contributing

To update the man page:

1. Edit the `gen.1` file using standard man page formatting
2. Test the formatting: `man -l gen.1`
3. Update this installation guide if needed
4. Submit a pull request with your changes 