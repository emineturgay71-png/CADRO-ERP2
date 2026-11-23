#!/bin/bash
# ---------------------------------------------------------------------------
# CADRO site restore
#
# Restores a backup made by backup_site.sh into an existing site (create it first with
# `bench new-site <name> --install-app erpnext`, or restore over the same site). Everything
# in that site is replaced: database, public and private files. The encryption key of the
# backup is applied afterwards, because the encrypted fields in the database depend on it.
#
# The Bench must run the same app commits as the backup (see backup_metadata.json).
#
# Usage (inside the bench container):
#   bash scripts/restore_site.sh <site-name> <backup-path>
#
# Confirmation: type RESTORE-<site-name> when asked, or export CADRO_RESTORE_CONFIRM with
# that value for unattended runs (for example drills).
# DB root password: DB_PASSWORD, or DB_PASSWORD_FILE (the compose secret).
# ---------------------------------------------------------------------------

set -euo pipefail

SITE_NAME="${1:?Site name required}"
BACKUP_PATH="${2:?Backup path required}"
BENCH_PATH="${FRAPPE_BENCH_PATH:-${HOME}/frappe-bench}"

if [ -z "${DB_PASSWORD:-}" ] && [ -n "${DB_PASSWORD_FILE:-}" ]; then
    DB_PASSWORD="$(cat "${DB_PASSWORD_FILE}")"
fi
: "${DB_PASSWORD:?DB_PASSWORD or DB_PASSWORD_FILE is required (database root password)}"

[ -d "${BACKUP_PATH}" ] || { echo "ERROR: backup directory not found: ${BACKUP_PATH}" >&2; exit 1; }
[ -f "${BACKUP_PATH}/backup_metadata.json" ] || { echo "ERROR: backup_metadata.json missing in ${BACKUP_PATH}" >&2; exit 1; }
[ -f "${BACKUP_PATH}/SHA256SUMS" ] || { echo "ERROR: SHA256SUMS missing in ${BACKUP_PATH}" >&2; exit 1; }
[ -d "${BENCH_PATH}/sites/${SITE_NAME}" ] || { echo "ERROR: site ${SITE_NAME} does not exist; create it first" >&2; exit 1; }

echo "Verifying backup integrity ..."
(cd "${BACKUP_PATH}" && sha256sum --check --quiet SHA256SUMS) || { echo "ERROR: checksum mismatch, backup is damaged" >&2; exit 1; }

newest() {
    ls -1t "${BACKUP_PATH}"/$1 2>/dev/null | head -n1
}
DB_FILE="$(newest '*-database.sql.gz')"
PUBLIC_FILES="$(newest '*-files.tar')"
PRIVATE_FILES="$(newest '*-private-files.tar')"
SITE_CONFIG_BACKUP="$(newest '*-site_config_backup.json')"
[ -n "${DB_FILE}" ] || { echo "ERROR: no database dump in ${BACKUP_PATH}" >&2; exit 1; }

# Warn when the app commits differ: restoring across versions can need a migrate.
for app in frappe erpnext payments; do
    expected="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['apps'].get(sys.argv[2],'unknown'))" "${BACKUP_PATH}/backup_metadata.json" "${app}")"
    actual="$(git -C "${BENCH_PATH}/apps/${app}" rev-parse HEAD 2>/dev/null || echo unknown)"
    if [ "${expected}" != "${actual}" ]; then
        echo "WARNING: ${app} is at ${actual}, the backup was made at ${expected}"
    fi
done

echo "WARNING: this replaces all data of site '${SITE_NAME}' with ${BACKUP_PATH}"
CONFIRMATION="${CADRO_RESTORE_CONFIRM:-}"
if [ -z "${CONFIRMATION}" ]; then
    read -r -p "Type 'RESTORE-${SITE_NAME}' to confirm: " CONFIRMATION
fi
if [ "${CONFIRMATION}" != "RESTORE-${SITE_NAME}" ]; then
    echo "Restore aborted."
    exit 2
fi

cd "${BENCH_PATH}"
args=(--site "${SITE_NAME}" --force restore "${DB_FILE}"
      --db-root-username root --db-root-password "${DB_PASSWORD}")
[ -n "${PUBLIC_FILES}" ] && args+=(--with-public-files "${PUBLIC_FILES}")
[ -n "${PRIVATE_FILES}" ] && args+=(--with-private-files "${PRIVATE_FILES}")
echo "Restoring database and files ..."
bench "${args[@]}"

# The encryption key must match the one the data was encrypted with.
if [ -n "${SITE_CONFIG_BACKUP}" ]; then
    key="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('encryption_key',''))" "${SITE_CONFIG_BACKUP}")"
    if [ -n "${key}" ]; then
        bench --site "${SITE_NAME}" set-config encryption_key "${key}"
    fi
fi

bench --site "${SITE_NAME}" migrate
bench --site "${SITE_NAME}" clear-cache
echo "Restore complete for ${SITE_NAME}."
