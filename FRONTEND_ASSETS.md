# Frontend Assets Configuration

## Overview
This project uses Tailwind CSS with DaisyUI v5 for styling. The configuration files track the exact versions needed without including node_modules or compiled assets.

## Required Files for Version Control

### Files to Commit:
- `package.json` - Defines npm dependencies and versions
- `tailwind.config.js` - Tailwind configuration with DaisyUI plugin
- `static/src/input.css` - Source CSS file for Tailwind
- `build-css.sh` - Build script for generating production CSS

### Files to Ignore (already in .gitignore):
- `node_modules/` - NPM packages (install via npm install)
- `staticfiles/dist/` - Compiled CSS output
- `package-lock.json` - Can be ignored or committed based on team preference

## Version Requirements

### Current Versions:
- **Node.js**: 22.x (recommended via NVM)
- **Tailwind CSS**: ^3.4.17
- **DaisyUI**: ^5.0.54

## Setup Instructions

### 1. Install Node.js (if not installed)
```bash
# Using NVM (recommended)
nvm install 22
nvm use 22
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Build CSS
```bash
# Production build (minified)
npm run build-css

# Or use the build script
./build-css.sh

# Development (with watch mode)
npm run watch-css
```

### 4. Collect Static Files (Django)
```bash
python manage.py collectstatic --noinput
```

## File Structure
```
limeclicks/
├── package.json              # NPM dependencies
├── tailwind.config.js        # Tailwind configuration
├── build-css.sh             # Build script
├── static/
│   └── src/
│       └── input.css        # Tailwind source CSS
└── staticfiles/
    └── dist/
        └── tailwind.css     # Compiled CSS (generated, not in git)
```

## Development Workflow

1. Make changes to templates or add new Tailwind classes
2. Run `./build-css.sh` to rebuild CSS
3. Run `python manage.py collectstatic` if adding new static files
4. Test changes locally
5. Commit configuration changes (not compiled output)

## Deployment

On the production server:
1. Pull latest code
2. Run `npm install` to get correct package versions
3. Run `./build-css.sh` to build CSS
4. Run `python manage.py collectstatic`
5. Restart services if needed

## Why These Files?

- **package.json**: Ensures everyone uses the same package versions
- **tailwind.config.js**: Defines which files to scan for classes and which plugins to use
- **static/src/input.css**: Base Tailwind directives and custom CSS
- **build-css.sh**: Consistent build process across environments

This approach ensures:
- Reproducible builds across all environments
- No large compiled files in version control
- Clear dependency management
- Easy updates to package versions