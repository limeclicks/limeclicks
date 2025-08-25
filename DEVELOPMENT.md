# LimeClicks Development Guide

## Quick Start

```bash
./dev.sh
```

This single command will:
✅ Check environment (.env file)
✅ Start Redis if needed  
✅ Install all dependencies
✅ Run database migrations
✅ Collect static files
✅ Start all services

## Commands

### Main Development Commands
```bash
./dev.sh              # Full stack (all services)
./dev.sh fast         # Skip setup, just start
./dev.sh basic        # Django + CSS only
./dev.sh status       # Check service status
./dev.sh clean        # Stop and clean everything
```

### Setup & Maintenance
```bash
./dev.sh setup        # Run full setup
./dev.sh migrate      # Database migrations only
./dev.sh deps install # Install dependencies
./dev.sh deps freeze  # Freeze current packages
./dev.sh deps check   # Check for conflicts
```

### Development Tools
```bash
./dev.sh test         # Run tests
./dev.sh shell        # Django shell
./dev.sh logs         # View all logs
./dev.sh logs celery  # Celery logs only
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Django | 8000 | http://localhost:8000 |
| Flower | 5555 | http://localhost:5555 |
| Tailwind CSS | - | Auto-compiles CSS |
| Celery Worker | - | Background tasks |
| Celery Beat | - | Scheduled tasks |
| Redis | 6379 | Cache & queue |

## Files

- `dev.sh` - Single development script for everything
- `Procfile` - All service definitions in one place
- `requirements.txt` - All dependencies (organized by category)

## Common Workflows

### First Time Setup
```bash
git clone <repo>
cd limeclicks
./dev.sh
```

### Daily Development  
```bash
./dev.sh          # Full stack
./dev.sh basic    # Lightweight (no Celery)
```

### After Git Pull
```bash
./dev.sh setup    # Update deps & migrate
./dev.sh
```

### Quick Restart
```bash
./dev.sh fast     # Skip all setup
```

## Troubleshooting

### Service Not Starting?
```bash
./dev.sh status   # Check what's running
./dev.sh clean    # Clean restart
./dev.sh
```

### Dependencies Issues?
```bash
./dev.sh deps check     # Check conflicts
pip install -r requirements.txt  # Manual install
```

### Database Issues?
```bash
./dev.sh migrate        # Run migrations
python manage.py migrate --fake  # Mark as applied
```

## Tips

- Use `./dev.sh basic` for frontend work (faster startup)
- Use `./dev.sh fast` when restarting frequently
- Check `./dev.sh status` to see what's running
- All logs are tailed together - use Ctrl+C to stop all

## Production Deployment

For production, use:
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn limeclicks.wsgi:application
```