#!/bin/bash
# Build script for Vercel deployment
# Attempts C++ compilation but gracefully falls back to Python engine if it fails

set -e

echo "🔨 Starting Checkora build for Vercel..."

# Ensure Django static files are collected
echo "📦 Collecting Django static files..."
python manage.py collectstatic --noinput

# Attempt C++ engine compilation (optional - Python fallback available)
echo "⚙️ Attempting C++ engine compilation..."
if g++ -O2 -o game/engine/main game/engine/main.cpp 2>/dev/null; then
    echo "✅ C++ engine compiled successfully"
    chmod +x game/engine/main
else
    echo "⚠️  C++ compilation failed - Python engine will be used as fallback"
fi

# Create public directory for Vercel
mkdir -p public
echo '<!-- Vercel placeholder -->' > public/placeholder.html

echo "✅ Build complete!"
