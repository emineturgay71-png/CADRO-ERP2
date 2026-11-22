#!/bin/bash
# ---------------------------------------------------------------------------
# CADRO site restore
#
# Restores a previously created backup onto a clean site of the same name.
# The target Bench MUST have the same app commits as the backup source.
# All existing site data will be replaced.
#
# Usage:
#   ./scripts/restore_site.sh <site-name> <backup-path>
# ---------------------------------------------------------------------------

set -euo pipefail

SITE_NAME="${1:?Site name required}"
BACKUP_PATH="${2:?Backup path required}"
SITE_PATH="${FRAPPE_BENCH_PATH:-${HOME}/frappe-bench}/sites/${SITE_NAME}"

if [ ! -d "${BACKUP_PATH}" ]; then
    echo "ERROR: backup directory not found: ${BACKUP_PATH}"
    exit 1
fi

if [ ! -f "${BACKUP_PATH}/backup_metadata.json" ]; then
    echo "ERROR: backup metadata missing in ${BACKUP_PATH}"
    exit 1
fi

echo "WARNING: This will replace all data for site '${SITE_NAME}'."
echo "Source backup: ${BACKUP_PATH}"
read -r -p "Type 'RESTORE-${SITE_NAME}' to confirm: " CONFIRMATION
if [ "${CONFIRMATION}" != "RESTORE-${SITE_NAME}" ]; then
    echo "Restore aborted."
    exit 2
fi

# Restore site files
if [ -f "${BACKUP_PATH}/site_files.tar.gz" ]; then
    echo "Restoring site files..."
    tar -xzf "${BACKUP_PATH}/site_files.tar.gz" \
        -C "$(dirname "${SITE_PATH}")"
fi

# Restore database
if [ -d "${BACKUP_PATH}/db" ]; then
    echo "Restoring database..."
    pushd "${BACKUP_PATH}/db" > /dev/null
    # bench restore expects to find the sql.gz file(s) in the backup directory
    bench --site "${SITE_NAME}" restore "${BACKUP_PATH}/db"
    popd > /dev/null
fi

echo "Restore complete. Verify with: bench --site ${SITE_NAME} doctor"