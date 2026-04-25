#!/bin/bash
# Deploy Pawly stack to VPS.
# Usage: ./scripts/deploy.sh user@your-server-ip
#
# Prerequisites on the server:
#   apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx
#   systemctl enable --now docker nginx

set -euo pipefail

SERVER="${1:?Usage: $0 user@server}"
REMOTE_DIR="/opt/pawly"

echo "==> Syncing files to $SERVER:$REMOTE_DIR"
rsync -avz --exclude '.git' \
           --exclude '__pycache__' \
           --exclude '*.pyc' \
           --exclude 'node_modules' \
           --exclude '.env' \
           --filter=':- .gitignore' \
           . "$SERVER:$REMOTE_DIR/"

echo "==> Syncing .env (secrets — not in git)"
rsync -avz .env "$SERVER:$REMOTE_DIR/.env"

echo "==> Syncing nginx config"
rsync -avz nginx/pawly.conf "$SERVER:/tmp/pawly.conf"

ssh "$SERVER" bash -s << 'ENDSSH'
set -euo pipefail

REMOTE_DIR="/opt/pawly"
cd "$REMOTE_DIR"

# Install nginx config
if [ ! -f /etc/nginx/sites-enabled/pawly ]; then
  cp /tmp/pawly.conf /etc/nginx/sites-available/pawly
  ln -sf /etc/nginx/sites-available/pawly /etc/nginx/sites-enabled/pawly
  echo "Nginx config installed. Run certbot before reloading nginx:"
  echo "  certbot --nginx -d api.pawly.app -d langfuse.pawly.app -d metabase.pawly.app"
else
  cp /tmp/pawly.conf /etc/nginx/sites-available/pawly
  nginx -t && systemctl reload nginx
  echo "Nginx config updated and reloaded."
fi

# Pull latest images and start stack (prod: no override file)
docker compose -f docker-compose.yml pull --quiet
docker compose -f docker-compose.yml up -d --remove-orphans

echo ""
echo "==> Stack status:"
docker compose -f docker-compose.yml ps

echo ""
echo "==> Done. Services:"
echo "    api.pawly.app        → Pawly bot + API"
echo "    langfuse.pawly.app   → Langfuse traces"
echo "    metabase.pawly.app   → Metabase dashboard"
ENDSSH
