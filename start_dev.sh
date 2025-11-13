#!/bin/bash

# Kitonga Development Server Startup Script

echo "=================================="
echo "🚀 Kitonga Wi-Fi Billing System"
echo "   Development Server"
echo "=================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please edit it with your credentials."
        echo ""
    else
        echo "❌ .env.example not found. Please create .env manually."
        exit 1
    fi
fi

# Set DEBUG mode for development
export DEBUG=True

echo "📋 Configuration:"
echo "   - DEBUG mode: Enabled"
echo "   - Protocol: HTTP (not HTTPS)"
echo "   - Default port: 8000"
echo ""

# Check if migrations are needed
echo "🔍 Checking database..."
python manage.py migrate --check 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Database migrations needed!"
    read -p "Run migrations now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python manage.py migrate
    fi
fi

echo ""
echo "=================================="
echo "✅ Starting Development Server"
echo "=================================="
echo ""
echo "📍 Access your server at:"
echo "   🌐 Admin: http://localhost:8000/admin/"
echo "   🌐 API:   http://localhost:8000/api/"
echo ""
echo "⚠️  IMPORTANT: Use HTTP, not HTTPS!"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the development server
python manage.py runserver 0.0.0.0:8000
