#!/bin/bash

# Unified Development Management Script for LimeClicks
# Usage: ./dev.sh [command] [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REDIS_PORT=6379
DJANGO_PORT=8000
FLOWER_PORT=5555

# Helper functions
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check prerequisites
check_redis() {
    if redis-cli -p $REDIS_PORT ping > /dev/null 2>&1; then
        print_status "Redis is running on port $REDIS_PORT"
        return 0
    else
        print_warning "Redis is not running"
        echo "Starting Redis..."
        if command -v systemctl &> /dev/null; then
            sudo systemctl start redis || redis-server --daemonize yes
        else
            redis-server --daemonize yes
        fi
        sleep 2
        if redis-cli -p $REDIS_PORT ping > /dev/null 2>&1; then
            print_status "Redis started successfully"
        else
            print_error "Failed to start Redis"
            return 1
        fi
    fi
}

check_env() {
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            print_warning ".env file not found. Creating from .env.example..."
            cp .env.example .env
            print_info "Please edit .env file with your configuration"
        else
            print_error ".env file not found and no .env.example available"
            return 1
        fi
    fi
}

# Install dependencies
install_deps() {
    print_info "Installing dependencies..."
    
    # Python dependencies
    if [ "$1" != "--skip-python" ]; then
        if [ -f "requirements.txt" ]; then
            print_info "Installing Python packages..."
            pip install -q -r requirements.txt
            print_status "Python dependencies installed"
        fi
    fi
    
    # Node dependencies
    if [ "$1" != "--skip-node" ]; then
        if [ -f "package.json" ] && [ ! -d "node_modules" ]; then
            print_info "Installing Node packages..."
            npm install --silent
            print_status "Node dependencies installed"
        fi
    fi
}

# Database operations
run_migrations() {
    print_info "Checking for model changes..."
    if python manage.py makemigrations --check --dry-run > /dev/null 2>&1; then
        print_status "No model changes detected"
    else
        print_warning "Model changes detected, creating migrations..."
        python manage.py makemigrations --noinput
        print_status "Migrations created"
    fi
    
    print_info "Running database migrations..."
    python manage.py migrate --noinput
    print_status "Migrations completed"
}

collect_static() {
    print_info "Collecting static files..."
    python manage.py collectstatic --noinput --clear > /dev/null 2>&1
    print_status "Static files collected"
}

# Main commands
case "$1" in
    start|"")
        echo -e "${GREEN}🚀 Starting LimeClicks Development Environment${NC}"
        echo "================================================"
        
        # Check environment
        check_env || exit 1
        check_redis || exit 1
        
        # Run setup if needed
        if [ "$2" != "--skip-setup" ]; then
            install_deps
            run_migrations
            collect_static
        fi
        
        echo ""
        print_info "Starting services:"
        echo "  • Django server on http://localhost:$DJANGO_PORT (with SSE support)"
        echo "  • Tailwind CSS watcher"
        echo "  • Celery worker (4 threads)"
        echo "  • Celery beat scheduler"
        echo "  • Flower monitor on http://localhost:$FLOWER_PORT"
        echo ""
        echo "Press Ctrl+C to stop all services"
        echo ""
        
        # Set environment for SSE support (disable output buffering)
        export PYTHONUNBUFFERED=1
        
        # Start all services
        honcho start
        ;;
    
    fast)
        echo -e "${GREEN}⚡ Fast Start (skip setup)${NC}"
        check_redis || exit 1
        # Set environment for SSE support (disable output buffering)
        export PYTHONUNBUFFERED=1
        honcho start
        ;;
    
    basic)
        echo -e "${GREEN}🎯 Basic Mode (Django + CSS only)${NC}"
        check_env || exit 1
        
        if [ "$2" != "--skip-setup" ]; then
            run_migrations
        fi
        
        # Set environment for SSE support (disable output buffering)
        export PYTHONUNBUFFERED=1
        
        honcho start web css
        ;;
    
    setup)
        echo -e "${GREEN}🔧 Running Setup${NC}"
        check_env || exit 1
        install_deps
        run_migrations
        collect_static
        print_status "Setup complete"
        ;;
    
    migrate)
        run_migrations
        ;;
    
    deps)
        case "$2" in
            install)
                install_deps
                ;;
            freeze)
                pip freeze > requirements_frozen_$(date +%Y%m%d).txt
                print_status "Dependencies frozen to requirements_frozen_$(date +%Y%m%d).txt"
                ;;
            check)
                print_info "Checking for dependency conflicts..."
                pip check
                ;;
            *)
                echo "Usage: $0 deps {install|freeze|check}"
                ;;
        esac
        ;;
    
    clean)
        print_warning "Cleaning development environment..."
        
        # Kill running services
        pkill -f "python manage.py runserver" 2>/dev/null || true
        pkill -f "celery" 2>/dev/null || true
        pkill -f "tailwindcss" 2>/dev/null || true
        
        # Clean Python cache
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        
        # Clean static files
        if [ -d "staticfiles" ]; then
            rm -rf staticfiles
        fi
        
        print_status "Environment cleaned"
        ;;
    
    status)
        echo -e "${BLUE}📊 Service Status${NC}"
        echo "=================="
        
        # Check Redis
        if redis-cli -p $REDIS_PORT ping > /dev/null 2>&1; then
            print_status "Redis: Running on port $REDIS_PORT"
        else
            print_error "Redis: Not running"
        fi
        
        # Check Django
        if curl -s http://localhost:$DJANGO_PORT > /dev/null 2>&1; then
            print_status "Django: Running on port $DJANGO_PORT"
        else
            print_error "Django: Not running"
        fi
        
        # Check Celery
        if pgrep -f "celery.*worker" > /dev/null; then
            print_status "Celery Worker: Running"
        else
            print_error "Celery Worker: Not running"
        fi
        
        if pgrep -f "celery.*beat" > /dev/null; then
            print_status "Celery Beat: Running"
        else
            print_error "Celery Beat: Not running"
        fi
        
        # Check Flower
        if curl -s http://localhost:$FLOWER_PORT > /dev/null 2>&1; then
            print_status "Flower: Running on port $FLOWER_PORT"
        else
            print_error "Flower: Not running"
        fi
        ;;
    
    test)
        echo -e "${GREEN}🧪 Running Tests${NC}"
        python manage.py test "${@:2}"
        ;;
    
    shell)
        python manage.py shell
        ;;
    
    logs)
        case "$2" in
            celery)
                tail -f logs/celery*.log 2>/dev/null || echo "No Celery logs found"
                ;;
            django)
                tail -f logs/django*.log 2>/dev/null || echo "No Django logs found"
                ;;
            *)
                echo "Tailing all logs..."
                tail -f logs/*.log 2>/dev/null || echo "No logs found"
                ;;
        esac
        ;;
    
    help|--help|-h)
        echo "LimeClicks Development Management Script"
        echo "========================================"
        echo ""
        echo "Usage: ./dev.sh [command] [options]"
        echo ""
        echo "Commands:"
        echo "  start           - Start all services with setup (default)"
        echo "  fast            - Fast start (skip setup steps)"
        echo "  basic           - Start only Django and CSS watcher"
        echo "  setup           - Run setup only (deps, migrations, static)"
        echo "  migrate         - Run database migrations"
        echo "  deps [action]   - Manage dependencies (install/freeze/check)"
        echo "  clean           - Clean up environment"
        echo "  status          - Check service status"
        echo "  test [args]     - Run Django tests"
        echo "  shell           - Open Django shell"
        echo "  logs [service]  - Tail logs (celery/django/all)"
        echo "  help            - Show this help message"
        echo ""
        echo "Options:"
        echo "  --skip-setup    - Skip dependency installation and migrations"
        echo "  --skip-python   - Skip Python dependency installation"
        echo "  --skip-node     - Skip Node dependency installation"
        echo ""
        echo "Examples:"
        echo "  ./dev.sh                    # Start all services"
        echo "  ./dev.sh fast               # Quick start without setup"
        echo "  ./dev.sh basic              # Django + CSS only"
        echo "  ./dev.sh deps install       # Install dependencies"
        echo "  ./dev.sh test accounts      # Run tests for accounts app"
        ;;
    
    *)
        print_error "Unknown command: $1"
        echo "Run './dev.sh help' for usage information"
        exit 1
        ;;
esac