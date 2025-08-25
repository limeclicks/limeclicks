# Development Procfile for LimeClicks
web: python manage.py runserver 0.0.0.0:8000
css: tailwindcss -i ./static/src/input.css -o ./static/dist/tailwind.css --watch
redis: redis-server --port 6379
worker: celery -A limeclicks worker --loglevel=info --pool=threads --concurrency=4 -Q celery,serp_high,serp_default,accounts,default
beat: celery -A limeclicks beat --loglevel=info
flower: celery -A limeclicks flower --port=5555