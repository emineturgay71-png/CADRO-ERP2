#!/bin/bash
# ---------------------------------------------------------------------------
# CADRO site backup
#
# Creates a timestamped backup of a Frappe site: compressed database dump, public and
# private files, the site configuration (it holds the encryption key that the encrypted
# fields in the database need), a checksum manifest and a metadata file with the app
# commits. Restore it with restore_site.sh.
#
# Usage (inside the bench container):
#   bash scripts/backup_site.sh <site-name> [backup-dir]
#
# The default backup directory lives in the persistent bench volume, next to the bench
# (<bench>/../cadro-backups). That is NOT an off-host copy: copy the directory out of the
# volume (docker cp, object storage) to keep a backup that survives losing the volume.
# ---------------------------------------------------------------------------

set -euo pipefail

SITE_NAME="${1:?Site name required}"
BENCH_PATH="${FRAPPE_BENCH_PATH:-${HOME}/frappe-bench}"
BACKUP_ROOT="${2:-$(dirname "${BENCH_PATH}")/cadro-backups}"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_PATH="${BACKUP_ROOT}/${SITE_NAME}-${TIMESTAMP}"

if [ ! -d "${BENCH_PATH}/sites/${SITE_NAME}" ]; then
    echo "ERROR: site directory not found: ${BENCH_PATH}/sites/${SITE_NAME}" >&2
    exit 1
fi

mkdir -p "${BACKUP_PATH}"
echo "Backing up ${SITE_NAME} to ${BACKUP_PATH} ..."

cd "${BENCH_PATH}"
bench --site "${SITE_NAME}" backup --with-files --backup-path "${BACKUP_PATH}"

app_commit() {
    git -C "${BENCH_PATH}/apps/$1" rev-parse HEAD 2>/dev/null || echo "unknown"
}

cat > "${BACKUP_PATH}/backup_metadata.json" <<EOF
{
    "site_name": "${SITE_NAME}",
    "timestamp": "${TIMESTAMP}",
    "apps": {
        "frappe": "$(app_commit frappe)",
        "erpnext": "$(app_commit erpnext)",
        "payments": "$(app_commit payments)"
    }
}
EOF

# Integrity manifest: verified again by restore_site.sh before anything is replaced.
(cd "${BACKUP_PATH}" && sha256sum -- * | grep -v 'SHA256SUMS$' > SHA256SUMS)

echo "Backup complete: ${BACKUP_PATH}"
ls -l "${BACKUP_PATH}"
