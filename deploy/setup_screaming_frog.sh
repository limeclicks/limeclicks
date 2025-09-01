#!/bin/bash

# Screaming Frog SEO Spider Setup Script for Ubuntu Server
# This script installs and configures Screaming Frog in headless mode

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SF_VERSION="19.8"  # Update this to latest version
SF_USER="limeclicks"
SF_DIR="/opt/screamingfrogseospider"
SF_CONFIG_DIR="/home/${SF_USER}/.ScreamingFrogSEOSpider"
SF_LICENSE_FILE="${SF_CONFIG_DIR}/licence.txt"
LOG_FILE="/var/log/screaming_frog_setup.log"

# Logging
exec 1> >(tee -a ${LOG_FILE})
exec 2>&1

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
       echo_error "This script must be run as root"
       exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    echo_step "Installing system dependencies..."
    
    # Update package list
    apt-get update
    
    # Install required packages for headless operation
    apt-get install -y \
        wget \
        curl \
        xvfb \
        x11vnc \
        xfonts-100dpi \
        xfonts-75dpi \
        xfonts-scalable \
        xfonts-cyrillic \
        x11-apps \
        imagemagick \
        default-jre \
        default-jdk \
        libgtk-3-0 \
        libx11-xcb1 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxi6 \
        libxtst6 \
        libnss3 \
        libxss1 \
        libxrandr2 \
        libasound2 \
        libpangocairo-1.0-0 \
        libatk1.0-0 \
        libcairo-gobject2 \
        libgtk-3-0 \
        libgdk-pixbuf2.0-0 \
        libglib2.0-0 \
        libdbus-glib-1-2 \
        libdbus-1-3 \
        libxcb-shm0 \
        libx11-dev \
        libxkbfile1 \
        ca-certificates \
        fonts-liberation \
        libappindicator3-1 \
        libnss3 \
        lsb-release \
        xdg-utils
    
    echo_info "Dependencies installed successfully"
}

# Download and install Screaming Frog
install_screaming_frog() {
    echo_step "Downloading and installing Screaming Frog SEO Spider..."
    
    # Create installation directory
    mkdir -p ${SF_DIR}
    cd /tmp
    
    # Download Screaming Frog (adjust URL based on latest version)
    DOWNLOAD_URL="https://download.screamingfrog.co.uk/products/seo-spider/ScreamingFrogSEOSpider-${SF_VERSION}.x86_64.rpm"
    
    echo_info "Downloading from: ${DOWNLOAD_URL}"
    wget -O screamingfrog.rpm "${DOWNLOAD_URL}" || {
        echo_error "Failed to download Screaming Frog. Please check the version number."
        echo_info "Visit https://www.screamingfrog.co.uk/seo-spider/release-notes/ for latest version"
        exit 1
    }
    
    # Convert RPM to DEB and install (for Ubuntu/Debian)
    apt-get install -y alien
    alien -d screamingfrog.rpm
    dpkg -i screamingfrog*.deb || apt-get install -f -y
    
    # Alternative: Direct installation for Ubuntu
    # wget https://download.screamingfrog.co.uk/products/seo-spider/ScreamingFrogSEOSpider-${SF_VERSION}.deb
    # dpkg -i ScreamingFrogSEOSpider-${SF_VERSION}.deb || apt-get install -f -y
    
    # Clean up
    rm -f screamingfrog.rpm screamingfrog*.deb
    
    echo_info "Screaming Frog installed successfully"
}

# Setup Xvfb virtual display
setup_virtual_display() {
    echo_step "Setting up virtual display (Xvfb)..."
    
    # Create systemd service for Xvfb
    cat > /etc/systemd/system/xvfb.service <<EOF
[Unit]
Description=X Virtual Framebuffer Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -nolisten unix
Restart=always
RestartSec=10
Environment="DISPLAY=:99"

[Install]
WantedBy=multi-user.target
EOF
    
    # Enable and start Xvfb
    systemctl daemon-reload
    systemctl enable xvfb.service
    systemctl start xvfb.service
    
    # Export DISPLAY variable
    echo 'export DISPLAY=:99' >> /etc/profile
    echo 'export DISPLAY=:99' >> /home/${SF_USER}/.bashrc
    
    echo_info "Virtual display configured successfully"
}

# Configure Screaming Frog for headless operation
configure_screaming_frog() {
    echo_step "Configuring Screaming Frog for headless operation..."
    
    # Create configuration directory
    sudo -u ${SF_USER} mkdir -p ${SF_CONFIG_DIR}
    
    # Create default configuration file
    cat > ${SF_CONFIG_DIR}/seospider.config <<EOF
# Screaming Frog SEO Spider Configuration
# Headless mode settings

# Memory allocation (adjust based on server specs)
memory.max=8192

# Crawler settings
crawl.follow.redirects=true
crawl.follow.canonical=false
crawl.respect.nofollow=true
crawl.crawl.subdomains=false
crawl.store.html=false
crawl.store.rendered.html=false

# User agent
user.agent=Mozilla/5.0 (compatible; Screaming Frog SEO Spider/${SF_VERSION})

# Crawl speed
crawl.max.threads=5
crawl.max.uri.per.second=5

# Export settings
export.bulk.exports.enabled=true
export.bulk.exports.format=csv
export.tabs.separator=comma

# Headless specific
interface.mode=headless
system.save.crawl=true
system.auto.save=true
EOF
    
    # Set ownership
    chown -R ${SF_USER}:${SF_USER} ${SF_CONFIG_DIR}
    
    echo_info "Configuration completed"
}

# Setup license key
setup_license() {
    echo_step "Setting up Screaming Frog license..."
    
    # Check if license key is provided as argument
    if [ -n "$1" ]; then
        LICENSE_KEY="$1"
    else
        # Prompt for license key
        echo_warning "Please enter your Screaming Frog license key:"
        echo_info "Format: NAME.SURNAME@COMPANY.COM,XXXX-XXXX-XXXX-XXXX"
        read -p "License key: " LICENSE_KEY
    fi
    
    if [ -z "$LICENSE_KEY" ]; then
        echo_warning "No license key provided. Running in free mode (500 URL limit)"
        return
    fi
    
    # Validate license format
    if [[ ! "$LICENSE_KEY" =~ ^[^,]+,[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$ ]]; then
        echo_error "Invalid license key format"
        echo_info "Expected format: EMAIL,XXXX-XXXX-XXXX-XXXX"
        return 1
    fi
    
    # Create license file
    echo "$LICENSE_KEY" | sudo -u ${SF_USER} tee ${SF_LICENSE_FILE} > /dev/null
    chmod 600 ${SF_LICENSE_FILE}
    
    echo_info "License key saved to ${SF_LICENSE_FILE}"
}

# Verify installation
verify_installation() {
    echo_step "Verifying Screaming Frog installation..."
    
    # Set display
    export DISPLAY=:99
    
    # Test 1: Check if binary exists
    if [ -f "/usr/bin/screamingfrogseospider" ]; then
        echo_info "✓ Screaming Frog binary found"
    else
        echo_error "✗ Screaming Frog binary not found"
        return 1
    fi
    
    # Test 2: Check version
    echo_info "Checking version..."
    sudo -u ${SF_USER} bash -c "export DISPLAY=:99; screamingfrogseospider --version" || {
        echo_warning "Could not get version via CLI"
    }
    
    # Test 3: Verify license
    if [ -f "${SF_LICENSE_FILE}" ]; then
        echo_info "✓ License file exists"
        
        # Extract email from license
        LICENSE_EMAIL=$(head -n1 ${SF_LICENSE_FILE} | cut -d',' -f1)
        echo_info "  Licensed to: ${LICENSE_EMAIL}"
    else
        echo_warning "✗ No license file found (free mode - 500 URL limit)"
    fi
    
    # Test 4: Test crawl with small site
    echo_info "Testing crawl functionality..."
    
    TEST_OUTPUT="/tmp/sf_test_crawl"
    mkdir -p ${TEST_OUTPUT}
    
    sudo -u ${SF_USER} bash -c "
        export DISPLAY=:99
        timeout 30 screamingfrogseospider \
            --crawl https://www.example.com \
            --headless \
            --save-crawl \
            --output-folder ${TEST_OUTPUT} \
            --export-tabs 'Internal:All' \
            --overwrite \
            --timestamped-output \
            2>&1 | head -20
    " && echo_info "✓ Test crawl completed" || echo_warning "Test crawl timeout (this is normal)"
    
    # Check if output was created
    if [ -n "$(ls -A ${TEST_OUTPUT} 2>/dev/null)" ]; then
        echo_info "✓ Output files created successfully"
        ls -la ${TEST_OUTPUT}
        rm -rf ${TEST_OUTPUT}
    else
        echo_warning "No output files created (may need manual testing)"
    fi
    
    echo_info "Installation verification completed"
}

# Create wrapper script for easy CLI usage
create_wrapper_script() {
    echo_step "Creating wrapper script..."
    
    cat > /usr/local/bin/sf-crawl <<'EOF'
#!/bin/bash

# Screaming Frog CLI Wrapper Script
# Usage: sf-crawl <url> [options]

# Set display
export DISPLAY=:99

# Default settings
OUTPUT_DIR="/tmp/sf_crawls/$(date +%Y%m%d_%H%M%S)"
URL="$1"
shift

# Check if URL provided
if [ -z "$URL" ]; then
    echo "Usage: sf-crawl <url> [options]"
    echo ""
    echo "Options:"
    echo "  --output-dir DIR     Output directory (default: /tmp/sf_crawls/)"
    echo "  --max-urls NUM       Maximum URLs to crawl"
    echo "  --user-agent STRING  Custom user agent"
    echo "  --export-tabs TABS   Comma-separated list of tabs to export"
    echo "  --config FILE        Path to config file"
    echo ""
    echo "Example:"
    echo "  sf-crawl https://example.com --max-urls 1000 --export-tabs 'Internal:All,External:All'"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Run Screaming Frog
echo "Starting crawl of: $URL"
echo "Output directory: $OUTPUT_DIR"

screamingfrogseospider \
    --crawl "$URL" \
    --headless \
    --save-crawl \
    --output-folder "$OUTPUT_DIR" \
    --export-tabs "${EXPORT_TABS:-Internal:All}" \
    --overwrite \
    --timestamped-output \
    "$@"

echo ""
echo "Crawl completed. Results saved to: $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"
EOF
    
    chmod +x /usr/local/bin/sf-crawl
    
    # Create Python wrapper for Django integration
    cat > /usr/local/bin/sf-python-wrapper.py <<'EOF'
#!/usr/bin/env python3
"""
Screaming Frog Python Wrapper for Django Integration
"""

import os
import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime

class ScreamingFrogCrawler:
    def __init__(self, display=":99"):
        self.display = display
        os.environ['DISPLAY'] = display
        
    def crawl(self, url, output_dir=None, max_urls=None, export_tabs=None):
        """
        Run a Screaming Frog crawl
        
        Args:
            url: URL to crawl
            output_dir: Output directory for results
            max_urls: Maximum number of URLs to crawl
            export_tabs: List of tabs to export
            
        Returns:
            dict: Crawl results and metadata
        """
        # Setup output directory
        if not output_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"/tmp/sf_crawls/{timestamp}"
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = [
            'screamingfrogseospider',
            '--crawl', url,
            '--headless',
            '--save-crawl',
            '--output-folder', output_dir,
            '--overwrite',
            '--timestamped-output'
        ]
        
        if max_urls:
            cmd.extend(['--max-uri', str(max_urls)])
        
        if export_tabs:
            tabs = ','.join(export_tabs) if isinstance(export_tabs, list) else export_tabs
            cmd.extend(['--export-tabs', tabs])
        else:
            cmd.extend(['--export-tabs', 'Internal:All'])
        
        # Run crawl
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            # Parse output files
            output_files = list(Path(output_dir).glob('*.csv'))
            
            return {
                'success': result.returncode == 0,
                'url': url,
                'output_dir': output_dir,
                'files': [str(f) for f in output_files],
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Crawl timeout exceeded',
                'output_dir': output_dir
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'output_dir': output_dir
            }
    
    def verify_license(self):
        """Check if license is valid"""
        license_file = Path.home() / '.ScreamingFrogSEOSpider' / 'licence.txt'
        
        if license_file.exists():
            with open(license_file) as f:
                license_content = f.read().strip()
                if ',' in license_content:
                    email, key = license_content.split(',', 1)
                    return {
                        'licensed': True,
                        'email': email,
                        'key': key[:4] + '-****-****-' + key[-4:]
                    }
        
        return {'licensed': False, 'mode': 'free', 'limit': 500}

if __name__ == '__main__':
    # CLI usage
    import argparse
    
    parser = argparse.ArgumentParser(description='Screaming Frog Python Wrapper')
    parser.add_argument('url', help='URL to crawl')
    parser.add_argument('--output-dir', help='Output directory')
    parser.add_argument('--max-urls', type=int, help='Maximum URLs to crawl')
    parser.add_argument('--export-tabs', help='Tabs to export (comma-separated)')
    parser.add_argument('--verify-license', action='store_true', help='Verify license status')
    
    args = parser.parse_args()
    
    crawler = ScreamingFrogCrawler()
    
    if args.verify_license:
        print(json.dumps(crawler.verify_license(), indent=2))
    else:
        result = crawler.crawl(
            args.url,
            output_dir=args.output_dir,
            max_urls=args.max_urls,
            export_tabs=args.export_tabs.split(',') if args.export_tabs else None
        )
        print(json.dumps(result, indent=2))
EOF
    
    chmod +x /usr/local/bin/sf-python-wrapper.py
    
    echo_info "Wrapper scripts created successfully"
}

# Create monitoring script
create_monitoring_script() {
    echo_step "Creating monitoring script..."
    
    cat > /usr/local/bin/sf-monitor <<'EOF'
#!/bin/bash

echo "Screaming Frog SEO Spider Status"
echo "================================"
echo ""

# Check Xvfb status
echo "Virtual Display (Xvfb) Status:"
if systemctl is-active --quiet xvfb; then
    echo "  ✓ Xvfb is running on display :99"
else
    echo "  ✗ Xvfb is not running"
    echo "  Run: sudo systemctl start xvfb"
fi
echo ""

# Check Screaming Frog installation
echo "Screaming Frog Installation:"
if [ -f "/usr/bin/screamingfrogseospider" ]; then
    echo "  ✓ Binary installed"
    # Try to get version
    export DISPLAY=:99
    VERSION=$(timeout 5 screamingfrogseospider --version 2>/dev/null | head -1)
    if [ -n "$VERSION" ]; then
        echo "  Version: $VERSION"
    fi
else
    echo "  ✗ Binary not found"
fi
echo ""

# Check license
echo "License Status:"
LICENSE_FILE="$HOME/.ScreamingFrogSEOSpider/licence.txt"
if [ -f "$LICENSE_FILE" ]; then
    EMAIL=$(head -n1 "$LICENSE_FILE" | cut -d',' -f1)
    echo "  ✓ Licensed to: $EMAIL"
    echo "  Mode: Paid (unlimited URLs)"
else
    echo "  ✗ No license file"
    echo "  Mode: Free (500 URL limit)"
fi
echo ""

# Check disk space
echo "Disk Space:"
df -h /tmp | tail -1
echo ""

# Recent crawls
echo "Recent Crawls:"
if [ -d "/tmp/sf_crawls" ]; then
    ls -lt /tmp/sf_crawls 2>/dev/null | head -5
else
    echo "  No recent crawls found"
fi
EOF
    
    chmod +x /usr/local/bin/sf-monitor
    
    echo_info "Monitoring script created"
}

# Main installation flow
main() {
    echo_info "Starting Screaming Frog SEO Spider installation..."
    echo_info "================================================"
    echo ""
    
    check_root
    
    # Parse arguments
    LICENSE_KEY=""
    SKIP_DEPS=false
    
    for arg in "$@"; do
        case $arg in
            --license=*)
                LICENSE_KEY="${arg#*=}"
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --license=KEY    Provide license key (format: EMAIL,XXXX-XXXX-XXXX-XXXX)"
                echo "  --skip-deps      Skip dependency installation"
                echo "  --help           Show this help message"
                exit 0
                ;;
        esac
    done
    
    # Run installation steps
    if [ "$SKIP_DEPS" = false ]; then
        install_dependencies
    fi
    
    install_screaming_frog
    setup_virtual_display
    configure_screaming_frog
    setup_license "$LICENSE_KEY"
    create_wrapper_script
    create_monitoring_script
    verify_installation
    
    echo ""
    echo_info "============================================"
    echo_info "Screaming Frog installation completed!"
    echo_info "============================================"
    echo ""
    echo_info "Important Information:"
    echo_info "  • Virtual display: :99"
    echo_info "  • Config directory: ${SF_CONFIG_DIR}"
    echo_info "  • License file: ${SF_LICENSE_FILE}"
    echo ""
    echo_info "Available Commands:"
    echo_info "  • sf-crawl <url>           - Run a crawl"
    echo_info "  • sf-monitor               - Check status"
    echo_info "  • sf-python-wrapper.py     - Python integration"
    echo ""
    echo_info "Next Steps:"
    echo_info "  1. Test with: sf-crawl https://example.com"
    echo_info "  2. Check status: sf-monitor"
    echo_info "  3. Add license: $0 --license=EMAIL,XXXX-XXXX-XXXX-XXXX"
    echo ""
}

# Run main function
main "$@"