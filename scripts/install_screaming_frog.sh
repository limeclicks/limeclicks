#!/bin/bash

# Install Screaming Frog SEO Spider on Ubuntu/Debian
# This script requires sudo privileges

echo "============================================"
echo "Screaming Frog SEO Spider Installation Script"
echo "============================================"

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "This script is for Linux systems only."
    exit 1
fi

# Check for sudo privileges
if [ "$EUID" -ne 0 ]; then 
    echo "Please run this script with sudo: sudo bash $0"
    exit 1
fi

echo ""
echo "Installing dependencies..."
# Install Java if not present
if ! command -v java &> /dev/null; then
    echo "Installing Java..."
    apt-get update
    apt-get install -y default-jre
else
    echo "Java is already installed"
fi

# Install wget if not present
if ! command -v wget &> /dev/null; then
    echo "Installing wget..."
    apt-get install -y wget
fi

# Install required libraries
echo "Installing required libraries..."
apt-get install -y libgtk-3-0 libx11-xcb1 libdbus-glib-1-2

echo ""
echo "Downloading Screaming Frog SEO Spider..."

# Download Screaming Frog
DOWNLOAD_URL="https://download.screamingfrog.co.uk/products/seo-spider/screamingfrogseospider_18.3_all.deb"
TEMP_FILE="/tmp/screamingfrogseospider.deb"

wget -O "$TEMP_FILE" "$DOWNLOAD_URL"

if [ $? -ne 0 ]; then
    echo "Failed to download Screaming Frog"
    exit 1
fi

echo ""
echo "Installing Screaming Frog SEO Spider..."
dpkg -i "$TEMP_FILE"

# Fix any dependency issues
apt-get install -f -y

# Clean up
rm -f "$TEMP_FILE"

# Verify installation
if command -v screamingfrogseospider &> /dev/null; then
    echo ""
    echo "✓ Screaming Frog SEO Spider installed successfully!"
    echo ""
    echo "You can now run it with: screamingfrogseospider"
    echo ""
    echo "For headless/CLI mode, use:"
    echo "  screamingfrogseospider --headless --crawl <URL> --save-crawl --output-folder <folder>"
    echo ""
    echo "License key should be placed in: ~/.screamingfrogseospider"
    echo "Or set via environment variable: SCREAMING_FROG_LICENSE"
else
    echo ""
    echo "✗ Installation failed. Please check the error messages above."
    exit 1
fi

echo ""
echo "Installation complete!"