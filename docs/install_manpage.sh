#!/bin/bash

# Man page installation script for gen tool
# This script installs the man page for the gen command

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANPAGE_FILE="$SCRIPT_DIR/gen.1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if man page file exists
if [[ ! -f "$MANPAGE_FILE" ]]; then
    print_error "Man page file not found: $MANPAGE_FILE"
    exit 1
fi

print_status "Found man page file: $MANPAGE_FILE"

# Function to install system-wide
install_system_wide() {
    print_status "Installing man page system-wide..."
    
    # Check if we have sudo privileges
    if ! sudo -n true 2>/dev/null; then
        print_warning "This will require sudo privileges"
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Installation cancelled"
            exit 0
        fi
    fi
    
    # Create man directory if it doesn't exist
    sudo mkdir -p /usr/local/share/man/man1/
    
    # Copy man page
    sudo cp "$MANPAGE_FILE" /usr/local/share/man/man1/
    
    # Set proper permissions
    sudo chmod 644 /usr/local/share/man/man1/gen.1
    
    # Update man database
    if command -v mandb >/dev/null 2>&1; then
        sudo mandb
    elif command -v makewhatis >/dev/null 2>&1; then
        sudo makewhatis
    else
        print_warning "Could not update man database (mandb/makewhatis not found)"
    fi
    
    print_success "Man page installed system-wide"
    print_status "You can now use: man gen"
}

# Function to install for current user
install_user_local() {
    print_status "Installing man page for current user..."
    
    # Create user man directory
    USER_MAN_DIR="$HOME/.local/share/man/man1"
    mkdir -p "$USER_MAN_DIR"
    
    # Copy man page
    cp "$MANPAGE_FILE" "$USER_MAN_DIR/"
    
    # Set proper permissions
    chmod 644 "$USER_MAN_DIR/gen.1"
    
    # Add to MANPATH if not already set
    SHELL_CONFIG=""
    if [[ -f "$HOME/.bashrc" ]]; then
        SHELL_CONFIG="$HOME/.bashrc"
    elif [[ -f "$HOME/.zshrc" ]]; then
        SHELL_CONFIG="$HOME/.zshrc"
    fi
    
    if [[ -n "$SHELL_CONFIG" ]]; then
        if ! grep -q "MANPATH.*\.local/share/man" "$SHELL_CONFIG"; then
            echo 'export MANPATH="$HOME/.local/share/man:$MANPATH"' >> "$SHELL_CONFIG"
            print_status "Added MANPATH to $SHELL_CONFIG"
            print_warning "Please restart your shell or run: source $SHELL_CONFIG"
        fi
    fi
    
    print_success "Man page installed for current user"
    print_status "You can now use: man gen"
}

# Function to test the man page
test_manpage() {
    print_status "Testing man page..."
    
    if command -v groff >/dev/null 2>&1; then
        if groff -man -Tascii "$MANPAGE_FILE" >/dev/null 2>&1; then
            print_success "Man page formatting is correct"
        else
            print_error "Man page formatting has issues"
            exit 1
        fi
    else
        print_warning "groff not found, skipping format test"
    fi
}

# Main installation logic
main() {
    echo "=== Gen Tool Man Page Installer ==="
    echo
    
    # Test the man page first
    test_manpage
    
    echo
    echo "Installation options:"
    echo "1) System-wide installation (requires sudo)"
    echo "2) User-local installation (recommended)"
    echo "3) Exit"
    echo
    
    read -p "Choose installation type (1-3): " -n 1 -r
    echo
    
    case $REPLY in
        1)
            install_system_wide
            ;;
        2)
            install_user_local
            ;;
        3)
            print_status "Installation cancelled"
            exit 0
            ;;
        *)
            print_error "Invalid option"
            exit 1
            ;;
    esac
    
    echo
    print_success "Installation complete!"
    print_status "Try running: man gen"
}

# Run main function
main "$@" 