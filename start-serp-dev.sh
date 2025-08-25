#!/bin/bash

# LimeClicks SERP Development Startup Script
# Optimized for SERP fetching and ranking development

echo "🔍 Starting LimeClicks SERP Development Environment..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual configuration values"
    exit 1
fi

# Check for required SERP-related env vars
if ! grep -q "SCRAPE_DO_API_KEY" .env || [ -z "$(grep SCRAPE_DO_API_KEY .env | cut -d '=' -f2)" ]; then
    echo "⚠️  SCRAPE_DO_API_KEY not configured in .env"
    echo "   Please add your Scrape.do API key to continue"
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

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm dependencies..."
    npm install
fi

echo "🐍 Checking Python dependencies..."
pip install -q -r requirements.txt

# Run database migrations
echo "🗃️  Running database migrations..."
python manage.py migrate

# Check keyword processing status
echo ""
echo "📊 Current SERP Processing Status:"
python manage.py shell -c "
from keywords.models import Keyword
from django.utils import timezone
from datetime import timedelta

total = Keyword.objects.filter(archive=False, project__active=True).count()
processing = Keyword.objects.filter(processing=True).count()
never_scraped = Keyword.objects.filter(scraped_at__isnull=True, archive=False, project__active=True).count()
cutoff = timezone.now() - timedelta(hours=24)
eligible = Keyword.objects.filter(scraped_at__lte=cutoff, archive=False, project__active=True, processing=False).count()
recent = Keyword.objects.filter(scraped_at__gte=timezone.now() - timedelta(hours=1)).count()

print(f'  Total active keywords: {total}')
print(f'  Currently processing: {processing}')
print(f'  Never scraped: {never_scraped}')
print(f'  Eligible for re-scrape: {eligible}')
print(f'  Scraped in last hour: {recent}')
"

# Reset any stuck processing flags
if [ "$1" == "--reset" ]; then
    echo ""
    echo "🔄 Resetting stuck processing flags..."
    python manage.py reset_processing_flags --stuck
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Starting SERP-focused services:"
echo "   - Django (port 8000)"
echo "   - Tailwind CSS (watch mode)"
echo "   - Celery Beat (queues keywords every minute)"
echo "   - High Priority Worker (2 threads) - for new keywords"
echo "   - Default Worker (4 threads) - for re-scraping"
echo "   - General Worker (2 threads) - for other tasks"
echo "   - Flower Monitor (port 5555)"
echo ""
echo "📡 Monitor at:"
echo "   - Django: http://localhost:8000"
echo "   - Flower: http://localhost:5555"
echo ""
echo "🔍 SERP Processing will start automatically:"
echo "   - Every minute, up to 500 keywords will be queued"
echo "   - New keywords get high priority"
echo "   - Keywords are re-scraped every 24 hours"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start SERP-focused services
honcho -f Procfile.dev.serp start