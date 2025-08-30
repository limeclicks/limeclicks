# LimeClicks Procfile
# ==================
# Usage: honcho start [process]
# 
# For development: honcho start
# For production: Use gunicorn directly
# For basic mode: honcho start web css

# Core Services
# =============
web: PYTHONUNBUFFERED=1 python manage.py runserver 0.0.0.0:8000 --nothreading
css: npx tailwindcss -i ./static/src/input.css -o ./static/dist/tailwind.css --watch

# Background Processing
# ====================
worker: celery -A limeclicks worker --loglevel=info --pool=threads --concurrency=4 -Q celery,serp_high,serp_default,accounts,default
beat: celery -A limeclicks beat --loglevel=info
flower: celery -A limeclicks flower --port=5555

# Optional Services (uncomment if needed)
# =======================================
# redis: redis-server --port 6379  # Usually runs as system service
# docs: sphinx-autobuild docs docs/_build/html --port 8001
# jupyter: jupyter notebook --port 8888