#!/bin/bash
# Backup PostgreSQL -> Azure Blob (cron quotidien 2h)
set -euo pipefail

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="affiliate_agent_${DATE}.sql.gz"
source /opt/tiktok-affiliate-agent/docker/.env

echo "[$(date)] Debut backup..."
docker exec affiliate_postgres pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} | gzip > /tmp/${BACKUP_FILE}

az storage blob upload \
  --connection-string "${AZURE_STORAGE_CONNECTION_STRING}" \
  --container-name "pg-backups" \
  --name "${BACKUP_FILE}" \
  --file "/tmp/${BACKUP_FILE}" --overwrite

rm /tmp/${BACKUP_FILE}
echo "[$(date)] Backup termine: ${BACKUP_FILE}"
