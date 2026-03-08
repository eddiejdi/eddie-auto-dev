#!/bin/bash
# Minimal Email Server Deployment Script

set -e

echo "=================================="
echo "Email Server Setup (Minimal)"
echo "=================================="

# Check prerequisites
echo "✓ Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "✗ Docker not found"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "✗ Docker Compose not found"; exit 1; }

# Create network if needed
echo "✓ Checking Docker network..."
docker network ls | grep -q homelab_monitoring || {
    echo "  Creating homelab_monitoring network..."
    docker network create homelab_monitoring
}

# Generate passwords
DB_PASSWORD=$(openssl rand -base64 24)
echo "✓ Generated secure password"

# Create .env file
cat > .env.email << EOF
DB_PASSWORD=${DB_PASSWORD}
DOMAIN=mail.rpa4all.com
ADMIN_EMAIL=admin@mail.rpa4all.com
EOF

echo "✓ Created .env.email"

# Create SSL directory
mkdir -p ~/.letsencrypt/{live,renewal}
chmod 700 ~/.letsencrypt

echo "✓ SSL directory ready"

# Start containers
echo "⏳ Starting containers..."
docker-compose -f docker-compose.email-simple.yml up -d

echo "⏳ Waiting for services... (30s)"
sleep 30

echo ""
echo "✓ Deployment complete!"
echo ""
echo "Access Roundcube at: https://mail.rpa4all.com/"
echo ""
echo "Your system needs:"
echo "1. SSL certificates at ~/.letsencrypt/live/mail.rpa4all.com/"
echo "2. Postfix/Dovecot running on host (ports 25, 143, 993)"
echo "3. DNS MX records configured"
echo ""
echo "Commands:"
echo "  docker-compose -f docker-compose.email-simple.yml ps"
echo "  docker-compose -f docker-compose.email-simple.yml logs -f"
