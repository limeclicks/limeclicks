#!/bin/bash

# LimeClicks Development Startup Script

echo "🚀 Starting LimeClicks Development Environment..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual configuration values"
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis is not running. Please start Redis first:"
    echo "   sudo systemctl start redis"
    echo "   OR"
    echo "   redis-server"
    exit 1
fi

# Install npm dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm dependencies..."
    npm install
fi

# Install Python dependencies if needed
echo "🐍 Checking Python dependencies..."
pip install -q -r requirements.txt

# Run database migrations
echo "🗃️  Running database migrations..."
python manage.py migrate

# Collect static files if needed
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Setup complete!"
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