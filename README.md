# LimeClicks

A Django web application with email verification, Celery task processing, and Tailwind CSS styling.

## Features

- 🔐 User registration with email verification
- 📧 Email templates using Brevo
- 🔄 Background task processing with Celery
- 🎨 Tailwind CSS + DaisyUI styling
- 🔒 reCAPTCHA integration
- 📊 Task monitoring with Flower

## Prerequisites

- Python 3.12+
- Node.js 18+
- Redis server
- PostgreSQL database

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo>
cd limeclicks
```

### 2. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your actual values
nano .env
```

### 3. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Node.js dependencies  
npm install
```

### 4. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 5. Start Development Server

**Option A: Full Development Environment (Recommended)**
```bash
# Start all services with auto-reload
./start-dev.sh

# OR using npm
npm run dev:full
```

**Option B: Basic Development (Django + CSS only)**
```bash
# Just Django and CSS compilation
npm run dev:basic

# OR manually
honcho -f Procfile.dev.basic start
```

**Option C: Individual Services**
```bash
# Django only
python manage.py runserver

# CSS watch mode only
npm run dev:css

# Full stack with Celery
honcho -f Procfile.dev start
```

**Option D: Traditional Development**
```bash
# Just Django + CSS using concurrently
npm run dev
```

## Services

When running the full development environment, these services start:

| Service | Port | Description |
|---------|------|-------------|
| **Django** | 8000 | Main web application |
| **Redis** | 6379 | Message broker |
| **Celery Worker** | - | Background task processor |
| **Celery Beat** | - | Periodic task scheduler |  
| **Flower** | 5555 | Task monitoring UI |
| **Tailwind CSS** | - | CSS compilation (watch mode) |

## Development URLs

- **Application**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin/
- **Flower (Tasks)**: http://localhost:5555
- **Redis**: redis://localhost:6379

## Project Structure

```
limeclicks/
├── accounts/           # User authentication app
│   ├── tasks.py       # Celery tasks
│   ├── email_backend.py # Brevo email integration
│   └── ...
├── static/
│   ├── src/input.css  # Tailwind source
│   └── dist/          # Compiled CSS
├── templates/         # HTML templates
├── Procfile          # Production services
├── Procfile.dev      # Development services  
└── start-dev.sh      # Development startup script
```

## Environment Variables

Key environment variables in `.env`:

```env
# Django
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://...

# Email (Brevo)  
BREVO_API_KEY=your-api-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# reCAPTCHA
GOOGLE_RECAPTCHA_SITE_KEY=your-site-key
GOOGLE_RECAPTCHA_SECRET_KEY=your-secret-key

# Redis
REDIS_URL=redis://localhost:6379/0
```

## Available Commands

### Development
```bash
./start-dev.sh              # Full development environment with all services
npm run dev:full            # Same as above - honcho -f Procfile.dev start
npm run dev:basic           # Django + CSS only - honcho -f Procfile.dev.basic start
npm run dev                 # Django + CSS using concurrently
npm run dev:css             # CSS watch mode only
python manage.py runserver  # Django only
```

### Production
```bash
honcho start                 # Start production services
npm run build:css            # Build production CSS
python manage.py collectstatic # Collect static files
```

### Celery
```bash
# Worker
celery -A limeclicks worker --loglevel=info

# Beat (scheduler)  
celery -A limeclicks beat --loglevel=info

# Flower (monitoring)
celery -A limeclicks flower --port=5555
```

## Email Templates

The application uses Brevo email templates:

- **Template ID 1**: Password reset emails
- **Template ID 2**: Email verification

Template parameters:
- `name`: User's name
- `url`: Action URL (verification/reset link)

## Task Queue

Background tasks are processed by Celery:

- Email sending (verification, password reset)
- Periodic cleanup of expired tokens
- Welcome email after verification

## Deployment

For production deployment:

1. Set production environment variables
2. Use `Procfile` (not `Procfile.dev`) 
3. Run `npm run build:css` for optimized CSS
4. Configure Redis and database connections
5. Set up proper process management (systemd, supervisor, etc.)

## Troubleshooting

### Server Won't Start
```bash
# Check if port 8000 is already in use
lsof -i :8000

# Kill process on port 8000
fuser -k 8000/tcp

# Start with different port
python manage.py runserver 8001
```

### Redis Connection Issues
```bash
# Check if Redis is running
redis-cli ping

# Start Redis manually (if not installed as service)
redis-server

# Install Redis on Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis
```

### CSS Not Loading or "tailwindcss not found"
```bash
# Install Tailwind CSS
npm install

# Build CSS manually
npm run build:css

# Check if Tailwind is watching
npm run dev:css
```

### Celery/Flower Issues
```bash
# Install flower if missing
pip install flower

# Check worker status
celery -A limeclicks inspect active

# Start basic development without Celery
npm run dev:basic
```

### Common Development Startup Options
```bash
# Minimal - Just Django
python manage.py runserver

# Basic - Django + CSS
npm run dev:basic

# Full - All services (requires Redis)
./start-dev.sh
```