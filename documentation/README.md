# LimeClicks Documentation

This folder contains all project documentation organized for easy access and maintenance.

## 📁 Documentation Index

### 🚀 Deployment & Setup
- **[SERVER_SETUP.md](SERVER_SETUP.md)** - Complete server setup and deployment guide
- **[PRODUCTION_OPTIMIZATION_NOTES.md](PRODUCTION_OPTIMIZATION_NOTES.md)** - Production environment optimizations and current status

### 🔧 Technical Configuration
- **[SCREAMING_FROG_SETUP.md](SCREAMING_FROG_SETUP.md)** - Screaming Frog SEO Spider integration setup
- **[REDIS_OPTIMIZATION_GUIDE.md](REDIS_OPTIMIZATION_GUIDE.md)** - Redis memory management and optimization
- **[R2_CORS_SETUP.md](R2_CORS_SETUP.md)** - Cloudflare R2 CORS configuration for performance data
- **[DATABASE_CONNECTION_MANAGEMENT.md](DATABASE_CONNECTION_MANAGEMENT.md)** - Database connection pooling and management

### 🎨 User Interface & Features
- **[ADMIN_INTERFACE_GUIDE.md](ADMIN_INTERFACE_GUIDE.md)** - Django Unfold admin interface documentation
- **[README_pagespeed.md](README_pagespeed.md)** - PageSpeed Insights API integration guide

## 🏗️ Architecture Overview

LimeClicks is built with:

- **Backend**: Django 5.2.5 with PostgreSQL
- **Frontend**: TailwindCSS + DaisyUI + HTMX
- **Task Queue**: Celery with Redis
- **Caching**: Redis
- **Storage**: Cloudflare R2 (S3-compatible)
- **Monitoring**: Custom health checks and monitoring scripts

## 📊 Key Integrations

- **SEO Tools**: Screaming Frog, PageSpeed Insights
- **Data Sources**: DataForSEO API, Scrape.do API
- **Infrastructure**: Cloudflare (CDN, R2 storage)
- **Email**: Brevo (formerly Sendinblue)

## 🔄 Quick Start

1. Follow [SERVER_SETUP.md](SERVER_SETUP.md) for initial deployment
2. Configure integrations using the technical guides
3. Apply production optimizations from [PRODUCTION_OPTIMIZATION_NOTES.md](PRODUCTION_OPTIMIZATION_NOTES.md)
4. Monitor using the health check scripts

## 📝 Maintenance

- Regular review of production optimization notes
- Update configuration as needed
- Monitor Redis memory usage
- Keep documentation updated with changes

---

For specific technical issues, refer to the individual documentation files above.