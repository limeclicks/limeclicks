#!/bin/bash
# Build script for Tailwind CSS with DaisyUI

# Use Node.js 22 if using nvm
if command -v nvm &> /dev/null; then
    source ~/.nvm/nvm.sh
    nvm use 22 2>/dev/null || nvm use default
fi

# Build Tailwind CSS
echo "Building Tailwind CSS with DaisyUI..."
npx tailwindcss -i ./static/src/input.css -o ./staticfiles/dist/tailwind.css --minify

# Fix permissions
chmod 755 ./staticfiles/dist/tailwind.css 2>/dev/null

echo "✅ Tailwind CSS built successfully!"
echo "   Output: ./staticfiles/dist/tailwind.css"