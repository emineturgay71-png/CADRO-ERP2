#!/bin/bash
# ---------------------------------------------------------------------------
# CADRO backup verification
#
# Checks a backup directory made by backup_site.sh without touching any site:
#   - the SHA256SUMS manifest matches every file,
#   - the database dump (*-database.sql.gz) exists and is a valid, non-empty gzip stream,
#   - the site configuration backup (*-site_config_backup.json) exists (it holds the
#     encryption key; a database dump without it cannot be fully restored),
#   - backup_metadata.json exists and is valid JSON.
#
# Usage: bash scripts/verify_backup.sh <backup-dir>
# Exit status: 0 = verified, 1 = a check failed (the reason is printed to stderr).
# ---------------------------------------------------------------------------

set -uo pipefail

DIR="${1:?Backup directory required}"
failed=0

fail() {
    echo "VERIFY FAILED: $1" >&2
    failed=1
}

[ -d "${DIR}" ] || { echo "VERIFY FAILED: not a directory: ${DIR}" >&2; exit 1; }

if [ -f "${DIR}/SHA256SUMS" ]; then
    (cd "${DIR}" && sha256sum --quiet -c SHA256SUMS) || fail "checksum manifest does not match"
else
    fail "SHA256SUMS is missing"
fi

db_dump="$(ls -1 "${DIR}"/*-database.sql.gz 2>/dev/null | head -n1)"
if [ -z "${db_dump}" ]; then
    fail "database dump (*-database.sql.gz) is missing"
elif ! gzip -t "${db_dump}" 2>/dev/null; then
    fail "database dump is not a valid gzip stream"
elif [ "$(gzip -dc "${db_dump}" | head -c 1024 | wc -c)" -eq 0 ]; then
    fail "database dump is empty"
fi

ls "${DIR}"/*-site_config_backup.json >/dev/null 2>&1 || fail "site config backup (*-site_config_backup.json) is missing"

if [ -f "${DIR}/backup_metadata.json" ]; then
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "${DIR}/backup_metadata.json" 2>/dev/null \
        || fail "backup_metadata.json is not valid JSON"
else
    fail "backup_metadata.json is missing"
fi

if [ "${failed}" -eq 0 ]; then
    echo "Backup verified: ${DIR}"
fi
exit "${failed}"
