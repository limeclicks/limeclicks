#!/bin/bash

# Simple Development Server Script
# Just run: ./dev.sh

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Stopping services...${NC}"
    pkill -f "python manage.py runserver" 2>/dev/null || true
    pkill -f "celery -A limeclicks" 2>/dev/null || true
    pkill -f "tailwindcss" 2>/dev/null || true
    redis-cli shutdown 2>/dev/null || true
    echo -e "${GREEN}✓ All services stopped${NC}"
    exit 0
}

trap cleanup EXIT INT TERM

# Start Redis if not running
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${BLUE}Starting Redis...${NC}"
    redis-server --daemonize yes
fi

# Build CSS once
echo -e "${BLUE}Building CSS...${NC}"
npx tailwindcss -i ./static/src/input.css -o ./static/dist/tailwind.css

# Set environment
export PYTHONUNBUFFERED=1

# Start all services
echo -e "\n${GREEN}Starting Development Services${NC}"
echo "================================"

# Start Django
python manage.py runserver 0.0.0.0:8000 2>&1 | sed 's/^/[Django] /' &

# Start CSS watcher
npx tailwindcss -i ./static/src/input.css -o ./static/dist/tailwind.css --watch 2>&1 | sed 's/^/[CSS] /' &

# Start Celery worker
celery -A limeclicks worker --loglevel=info --pool=threads --concurrency=4 2>&1 | sed 's/^/[Worker] /' &

# Start Celery beat
celery -A limeclicks beat --loglevel=info 2>&1 | sed 's/^/[Beat] /' &

# Wait for services to start
sleep 5

# Start Flower
celery -A limeclicks flower --port=5555 2>&1 | sed 's/^/[Flower] /' &

echo -e "\n${GREEN}✓ All services started!${NC}\n"
echo "Django: http://localhost:8000"
echo "Flower: http://localhost:5555"
echo -e "\nPress Ctrl+C to stop\n"
echo "================================"

# Keep running
wait