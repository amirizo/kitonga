#!/bin/bash

# Kitonga Wi-Fi Billing System - Production Deployment Script
# This script deploys the application with SQLite database

set -e

echo "🚀 Starting Kitonga Wi-Fi System Production Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please copy .env.production to .env and configure your settings"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs backups staticfiles ssl

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed!${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed!${NC}"
    echo "Please install Docker Compose first"
    exit 1
fi

# Stop any running containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down

# Build the application
echo "🔨 Building application..."
docker-compose -f docker-compose.prod.yml build

# Run database migrations
echo "🗄️ Running database migrations..."
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate

# Collect static files
echo "📦 Collecting static files..."
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput

# Create superuser (if needed)
echo "👤 Creating superuser..."
docker-compose -f docker-compose.prod.yml run --rm web python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@kitonga.klikcell.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
"

# Start the application
echo "🚀 Starting application..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
echo "🔍 Checking service health..."
if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Services are running!${NC}"
else
    echo -e "${RED}❌ Some services failed to start${NC}"
    docker-compose -f docker-compose.prod.yml logs
    exit 1
fi

# Test the health endpoint
echo "🏥 Testing health endpoint..."
sleep 5
if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Application is healthy!${NC}"
else
    echo -e "${YELLOW}⚠️ Health check failed, but this might be normal during startup${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo "📋 Next steps:"
echo "1. Configure your domain DNS to point to this server"
echo "2. Set up SSL certificates (Let's Encrypt recommended)"
echo "3. Update nginx.conf with your SSL certificate paths"
echo "4. Configure your production environment variables in .env"
echo "5. Set up your ClickPesa and NextSMS credentials"
echo "6. Configure your Mikrotik router with the production API endpoint"
echo ""
echo "🔗 Access points:"
echo "- Application: http://localhost:8000"
echo "- Admin Panel: http://localhost:8000/admin"
echo "- Health Check: http://localhost:8000/api/health/"
echo ""
echo "📊 Monitor with:"
echo "- View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "- Check status: docker-compose -f docker-compose.prod.yml ps"
echo ""
echo -e "${YELLOW}⚠️ Remember to:${NC}"
echo "- Change default admin password: admin/admin123"
echo "- Set strong SECRET_KEY in .env"
echo "- Configure firewall rules"
echo "- Set up regular database backups"
echo ""
