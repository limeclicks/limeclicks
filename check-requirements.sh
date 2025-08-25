#!/bin/bash

# Check system requirements for LimeClicks

echo "🔍 Checking System Requirements for LimeClicks..."
echo "================================================"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors=0
warnings=0

# Check Python
echo -n "Python 3.8+: "
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
    if (( $(echo "$python_version >= 3.8" | bc -l) )); then
        echo -e "${GREEN}✓${NC} ($(python3 --version 2>&1))"
    else
        echo -e "${RED}✗${NC} Python 3.8+ required (found $python_version)"
        ((errors++))
    fi
else
    echo -e "${RED}✗${NC} Python not found"
    ((errors++))
fi

# Check pip
echo -n "pip: "
if command -v pip &> /dev/null; then
    echo -e "${GREEN}✓${NC} ($(pip --version | cut -d' ' -f2))"
else
    echo -e "${RED}✗${NC} pip not found"
    ((errors++))
fi

# Check Node.js
echo -n "Node.js: "
if command -v node &> /dev/null; then
    echo -e "${GREEN}✓${NC} ($(node --version))"
else
    echo -e "${YELLOW}⚠${NC} Node.js not found (needed for Tailwind CSS)"
    ((warnings++))
fi

# Check npm
echo -n "npm: "
if command -v npm &> /dev/null; then
    echo -e "${GREEN}✓${NC} ($(npm --version))"
else
    echo -e "${YELLOW}⚠${NC} npm not found (needed for Tailwind CSS)"
    ((warnings++))
fi

# Check Redis
echo -n "Redis: "
if command -v redis-cli &> /dev/null; then
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} (running)"
    else
        echo -e "${YELLOW}⚠${NC} Redis installed but not running"
        echo "  Start with: sudo systemctl start redis OR redis-server"
        ((warnings++))
    fi
else
    echo -e "${RED}✗${NC} Redis not found"
    echo "  Install with: sudo apt install redis-server"
    ((errors++))
fi

# Check PostgreSQL
echo -n "PostgreSQL: "
if command -v psql &> /dev/null; then
    echo -e "${GREEN}✓${NC} ($(psql --version | cut -d' ' -f3))"
else
    echo -e "${RED}✗${NC} PostgreSQL client not found"
    echo "  Install with: sudo apt install postgresql-client"
    ((errors++))
fi

# Check for .env file
echo -n ".env file: "
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC} Not found (will be created from .env.example)"
    ((warnings++))
fi

# Check for virtual environment
echo -n "Virtual environment: "
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✓${NC} ($VIRTUAL_ENV)"
else
    echo -e "${YELLOW}⚠${NC} No virtual environment active"
    echo "  Create with: python3 -m venv venv && source venv/bin/activate"
    ((warnings++))
fi

# Check available disk space
echo -n "Disk space: "
available_space=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
if (( available_space >= 2 )); then
    echo -e "${GREEN}✓${NC} (${available_space}GB available)"
else
    echo -e "${YELLOW}⚠${NC} Low disk space (${available_space}GB available)"
    ((warnings++))
fi

# Check available memory
echo -n "Memory: "
available_mem=$(free -m | awk 'NR==2 {print $7}')
if (( available_mem >= 512 )); then
    echo -e "${GREEN}✓${NC} (${available_mem}MB available)"
else
    echo -e "${YELLOW}⚠${NC} Low memory (${available_mem}MB available)"
    ((warnings++))
fi

echo ""
echo "================================================"

if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
    echo -e "${GREEN}✅ All requirements met!${NC}"
    echo ""
    echo "You can now run:"
    echo "  ./start-dev.sh         - Full setup with dependency checks"
    echo "  ./start-dev-fast.sh    - Skip dependency checks"
    echo "  ./start-django.sh      - Django server only"
elif [ $errors -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Some warnings found but you can proceed${NC}"
    echo ""
    echo "Recommended startup scripts:"
    echo "  ./start-dev-fast.sh    - Skip dependency checks"
    echo "  ./start-django.sh      - Django server only"
else
    echo -e "${RED}❌ Critical requirements missing${NC}"
    echo ""
    echo "Please install missing requirements before proceeding."
    exit 1
fi