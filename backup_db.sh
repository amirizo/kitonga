#!/bin/bash

# SQLite Database Backup Script for Kitonga Wi-Fi System

set -e

# Configuration
BACKUP_DIR="./backups"
DB_FILE="./db.sqlite3"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/kitonga_db_backup_$DATE.sqlite3"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "📦 Starting SQLite database backup..."

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check if database file exists
if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}Error: Database file $DB_FILE not found!${NC}"
    exit 1
fi

# Create backup
echo "💾 Creating backup: $BACKUP_FILE"
cp "$DB_FILE" "$BACKUP_FILE"

# Verify backup
if [ -f "$BACKUP_FILE" ]; then
    ORIGINAL_SIZE=$(stat -f%z "$DB_FILE" 2>/dev/null || stat -c%s "$DB_FILE" 2>/dev/null)
    BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE" 2>/dev/null)
    
    if [ "$ORIGINAL_SIZE" -eq "$BACKUP_SIZE" ]; then
        echo -e "${GREEN}✅ Backup created successfully!${NC}"
        echo "📊 Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
    else
        echo -e "${RED}❌ Backup verification failed! Size mismatch.${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Backup failed!${NC}"
    exit 1
fi

# Clean up old backups (keep last 7 days)
echo "🧹 Cleaning up old backups (keeping last 7 days)..."
find "$BACKUP_DIR" -name "kitonga_db_backup_*.sqlite3" -mtime +7 -delete 2>/dev/null || true

# Show backup status
echo ""
echo "📋 Backup Summary:"
echo "- Database: $DB_FILE"
echo "- Backup: $BACKUP_FILE"
echo "- Size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo "- Date: $(date)"
echo ""
echo "📁 Available backups:"
ls -lah "$BACKUP_DIR"/kitonga_db_backup_*.sqlite3 2>/dev/null || echo "No previous backups found"

echo -e "${GREEN}🎉 Backup completed successfully!${NC}"
