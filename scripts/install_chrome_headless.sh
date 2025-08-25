#!/bin/bash

# Script to install Chrome/Chromium for headless Lighthouse on Ubuntu/Debian servers

echo "Installing Chrome/Chromium for headless Lighthouse..."

# Detect OS
if [ -f /etc/debian_version ]; then
    echo "Detected Debian/Ubuntu system"
    
    # Update package list
    sudo apt-get update
    
    # Install dependencies
    sudo apt-get install -y \
        wget \
        gnupg \
        ca-certificates \
        apt-transport-https \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        xdg-utils
    
    # Option 1: Install Chromium (lighter, open-source)
    echo "Installing Chromium..."
    sudo apt-get install -y chromium-browser
    
    # Option 2: Install Google Chrome (if preferred)
    # Uncomment below to install Google Chrome instead
    # wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    # echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
    # sudo apt-get update
    # sudo apt-get install -y google-chrome-stable
    
elif [ -f /etc/redhat-release ]; then
    echo "Detected RedHat/CentOS system"
    
    # Install dependencies
    sudo yum install -y \
        wget \
        liberation-fonts \
        libX11 \
        libXcomposite \
        libXcursor \
        libXdamage \
        libXext \
        libXi \
        libXtst \
        cups-libs \
        libXScrnSaver \
        libXrandr \
        alsa-lib \
        pango \
        gtk3
    
    # Install Chromium
    sudo yum install -y chromium
    
else
    echo "Unsupported OS. Please install Chrome/Chromium manually."
    exit 1
fi

# Verify installation
if command -v chromium-browser &> /dev/null; then
    echo "✅ Chromium installed successfully"
    chromium-browser --version
elif command -v google-chrome &> /dev/null; then
    echo "✅ Google Chrome installed successfully"
    google-chrome --version
else
    echo "❌ Chrome/Chromium installation failed"
    exit 1
fi

# Install Lighthouse globally via npm
if command -v npm &> /dev/null; then
    echo "Installing Lighthouse..."
    sudo npm install -g lighthouse
    echo "✅ Lighthouse installed"
    lighthouse --version
else
    echo "⚠️ npm not found. Please install Node.js and run: npm install -g lighthouse"
fi

echo "✅ Setup complete! Chrome/Chromium is ready for headless Lighthouse audits."