#!/bin/bash

# LimeClicks Fast Development Startup Script (skips dependency checks)

echo "🚀 Starting LimeClicks Development Environment (Fast Mode)..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual configuration values"
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis is not running. Please start Redis first:"
    echo "   sudo systemctl start redis"
    echo "   OR"
    echo "   redis-server"
    exit 1
fi

echo "⚡ Skipping dependency checks (fast mode)"

# Quick migrate check
echo "🗃️  Checking for pending migrations..."
python manage.py migrate --check > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "📝 Running pending migrations..."
    python manage.py migrate
fi

echo "✅ Ready to start!"
echo ""
echo "🎯 Starting all services with Honcho..."
echo "   - Django (port 8000)"
echo "   - Tailwind CSS (watch mode)"
echo "   - Redis (port 6379)"  
echo "   - Celery Worker"
echo "   - Celery Beat (scheduler)"
echo "   - Flower (port 5555)"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start all services with auto-reload
honcho -f Procfile.dev start