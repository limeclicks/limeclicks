#!/bin/bash

# Simple Django Development Server Startup

echo "🚀 Starting Django Development Server..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual configuration values"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Check for pending migrations
python manage.py migrate --check > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "📝 Running pending migrations..."
    python manage.py migrate
fi

echo "✅ Starting Django server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

# Start Django development server
python manage.py runserver