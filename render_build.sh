#!/bin/bash
# Exit on error
set -o errexit

echo "🚀 Starting Build Process..."

echo "📦 Installing Python Dependencies..."
pip install -r requirements.txt

echo "🎨 Building Frontend..."
cd web_ui
npm install
npm run build
cd ..

echo "✅ Build Complete!"
