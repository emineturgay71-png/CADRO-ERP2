#!/bin/bash
# ---------------------------------------------------------------------------
# CADRO site backup
#
# Creates a timestamped, compressed backup of a Frappe site (database dump +
# files) in a target directory. The backup can later be restored onto an
# identical Bench (same app commits) with restore_site.sh.
#
# Usage:
#   ./scripts/backup_site.sh <site-name> [backup-dir]
# ---------------------------------------------------------------------------

set -euo pipefail

SITE_NAME="${1:?Site name required}"
BACKUP_DIR="${2:-$(pwd)/cadro-backups}"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_PATH="${BACKUP_DIR}/${SITE_NAME}-${TIMESTAMP}"
SITE_PATH="${FRAPPE_BENCH_PATH:-${HOME}/frappe-bench}/sites/${SITE_NAME}"

if [ ! -d "${SITE_PATH}" ]; then
    echo "ERROR: site directory not found: ${SITE_PATH}"
    exit 1
fi

mkdir -p "${BACKUP_PATH}"
echo "Backing up ${SITE_NAME} to ${BACKUP_PATH} ..."

# Database dump
bench --site "${SITE_NAME}" backup \
    --with-files \
    --backup-path "${BACKUP_PATH}/db"

# Site files (excluding rebuildable assets)
tar -czf "${BACKUP_PATH}/site_files.tar.gz" \
    -C "$(dirname "${SITE_PATH}")" \
    --exclude="${SITE_NAME}/assets" \
    --exclude="${SITE_NAME}/.cache" \
    "${SITE_NAME}"

# Metadata file
cat > "${BACKUP_PATH}/backup_metadata.json" <<EOF
{
    "site_name": "${SITE_NAME}",
    "timestamp": "${TIMESTAMP}",
    "frappe_bench_path": "${FRAPPE_BENCH_PATH:-HOME/frappe-bench}",
    "cadro_baseline_commit": "$(git -C "$(dirname "$0")/.." rev-parse HEAD 2>/dev/null || echo 'unknown')"
}
EOF

echo "Backup complete: ${BACKUP_PATH}"