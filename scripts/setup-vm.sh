#!/bin/bash
# Setup VM Azure - TikTok Affiliate Agent
# Usage: bash setup-vm.sh
set -euo pipefail

log() { echo "[$(date +'%H:%M:%S')] $1"; }

log "=== Setup TikTok Affiliate Agent VM ==="

log "1. Mise a jour systeme..."
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

log "2. Installation dependances..."
sudo apt-get install -y -qq curl wget git unzip ffmpeg python3 python3-pip jq

log "3. Installation Docker..."
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
sudo systemctl enable docker && sudo systemctl start docker
sudo apt-get install -y docker-compose-plugin

log "4. Installation Azure CLI..."
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

log "5. Clone du repository..."
if [ ! -d "/opt/tiktok-affiliate-agent" ]; then
  sudo git clone https://github.com/ToutaYasso/tiktok-affiliate-agent.git /opt/tiktok-affiliate-agent
  sudo chown -R $USER:$USER /opt/tiktok-affiliate-agent
fi

log "6. Configuration backup cron..."
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/tiktok-affiliate-agent/scripts/backup-pg.sh >> /opt/tiktok-affiliate-agent/logs/backup.log 2>&1") | crontab -

log "=== Setup termine ! Edite .env puis lance: docker compose up -d ==="
