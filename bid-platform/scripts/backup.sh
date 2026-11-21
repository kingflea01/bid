#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DESTINATION="${BACKUP_ROOT}/${TIMESTAMP}"
mkdir -p "${DESTINATION}"

POSTGRES_USER="${POSTGRES_USER:-bid}"
POSTGRES_DB="${POSTGRES_DB:-bid_platform}"

# 数据库与文件必须配套保留，恢复时应先验证备份完整性再操作生产数据。
docker compose --env-file "${ENV_FILE}" exec -T postgres \
  pg_dump --username "${POSTGRES_USER}" --format custom --file - "${POSTGRES_DB}" \
  > "${DESTINATION}/postgres.dump"
docker compose --env-file "${ENV_FILE}" exec -T api \
  tar -C /data/files -czf - . > "${DESTINATION}/files.tar.gz"
printf 'POSTGRES_DB=%s\nPOSTGRES_USER=%s\n' "${POSTGRES_DB}" "${POSTGRES_USER}" \
  > "${DESTINATION}/backup-manifest.env"
sha256sum "${DESTINATION}/postgres.dump" "${DESTINATION}/files.tar.gz" \
  > "${DESTINATION}/SHA256SUMS"

printf 'Backup created at %s\n' "${DESTINATION}"
