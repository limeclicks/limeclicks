#!/bin/bash

# Diagnostic script to identify pip installation issues

echo "🔍 Diagnosing pip installation issues..."
echo "=================================="

# Check Python version
echo "📌 Python version:"
python --version
echo ""

# Check pip version
echo "📌 Pip version:"
pip --version
echo ""

# Check virtual environment
echo "📌 Virtual environment:"
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✓ Active: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment active"
fi
echo ""

# Test pip connectivity
echo "📌 Testing pip connectivity:"
pip config list
echo ""

# Check for problematic packages
echo "📌 Checking problematic packages that might hang:"
echo ""

problematic_packages=(
    "psycopg2-binary"
    "pillow"
    "cryptography"
    "lxml"
    "numpy"
)

for package in "${problematic_packages[@]}"; do
    if grep -q "^$package" requirements.txt; then
        echo "⚠️  Found $package - may take time to compile"
        # Check if already installed
        if pip show $package > /dev/null 2>&1; then
            echo "   ✓ Already installed"
        else
            echo "   ⚠️ Not installed - will need to download/compile"
        fi
    fi
done

echo ""
echo "📌 Testing single package installation:"
echo "Installing a small package (six) as test..."
pip install --timeout 30 six
if [ $? -eq 0 ]; then
    echo "✓ Test package installed successfully"
else
    echo "❌ Failed to install test package - check network/pip configuration"
fi

echo ""
echo "📌 Checking disk space:"
df -h | grep -E "^/dev/" | head -5

echo ""
echo "📌 Memory available:"
free -h

echo ""
echo "=================================="
echo "Diagnosis complete!"
echo ""
echo "💡 Recommendations:"
echo "1. If packages are hanging, try installing with verbose flag:"
echo "   pip install -v -r requirements.txt"
echo ""
echo "2. For faster installation, use binary wheels:"
echo "   pip install --only-binary :all: -r requirements.txt"
echo ""
echo "3. If behind proxy, configure pip:"
echo "   pip config set global.proxy http://proxy.example.com:8080"
echo ""
echo "4. Use the fast startup script to skip dependency checks:"
echo "   ./start-dev-fast.sh"