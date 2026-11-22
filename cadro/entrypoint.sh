#!/bin/bash
# ---------------------------------------------------------------------------
# CADRO evaluation entrypoint
#
# This script provisions a Frappe Bench at the pinned commits recorded in
# cadro.baseline.json. It is designed for staging/pilot evaluation.
#
# Production use requires:
#   - immutable container digests
#   - SBOM and license inventory
#   - secrets management (not env vars in compose)
# ---------------------------------------------------------------------------

set -uo pipefail
# Note: 'set -e' intentionally NOT used — bench commands may return non-zero
# exit codes for warnings (e.g. redis_cache unavailable during build). We
# check critical steps explicitly below.

FRAPPE_BENCH_PATH="${FRAPPE_BENCH_PATH:-/home/frappe/cadro-data/frappe-bench}"
SITE_NAME="${SITE_NAME:-cadro-pilot.localhost}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-3306}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD is required}"
FRAPPE_COMMIT="${FRAPPE_COMMIT:-96c27e16ed5cfcfaf27d1db2f40c5c7acf871bbd}"
ERPNEXT_COMMIT="${ERPNEXT_COMMIT:-920f1d5b3d18142cf3c4cc6edf59e53950a7832b}"
PAYMENTS_COMMIT="${PAYMENTS_COMMIT:-d6df15a6ce91e508d58fe34ba53e27f3b63d344e}"

# Locale defaults applied once, on fresh site provisioning only.
CADRO_LANGUAGE="${CADRO_LANGUAGE:-tr}"
CADRO_COUNTRY="${CADRO_COUNTRY:-Türkiye}"
CADRO_TIME_ZONE="${CADRO_TIME_ZONE:-Europe/Istanbul}"
CADRO_DATE_FORMAT="${CADRO_DATE_FORMAT:-dd.mm.yyyy}"
CADRO_NUMBER_FORMAT="${CADRO_NUMBER_FORMAT:-#.###,##}"
CADRO_LOCALE_OVERLAY="${CADRO_LOCALE_OVERLAY:-/home/frappe/cadro-locale/${CADRO_LANGUAGE}.po}"
CADRO_LOCALE_PATCH="${CADRO_LOCALE_PATCH:-/home/frappe/cadro-locale/frappe_${CADRO_LANGUAGE}_overlay.po}"
CADRO_LOCALE_MERGE="${CADRO_LOCALE_MERGE:-/home/frappe/cadro-locale/merge_po.py}"
CADRO_ERPNEXT_SRC="${CADRO_ERPNEXT_SRC:-/home/frappe/cadro-erpnext/erpnext}"
CADRO_BANKING_SRC="${CADRO_BANKING_SRC:-/home/frappe/cadro-erpnext/banking/src}"
# Hashes of the CADRO code applied to the bench; lives in the bench volume.
CADRO_STATE_DIR="${FRAPPE_BENCH_PATH}/.cadro-state"

# Check out an app at a pinned commit. bench get-app clones with --depth 1 and names
# the remote "upstream", so the remote is looked up instead of assumed.
pin_app() {
    local app_dir="${FRAPPE_BENCH_PATH}/apps/$1" commit="$2" remote
    [ -d "${app_dir}/.git" ] || return 1
    remote="$(git -C "${app_dir}" remote | head -n1)"
    git -C "${app_dir}" fetch --depth 1 "${remote}" "${commit}" && git -C "${app_dir}" checkout "${commit}"
}

dir_hash() {
    (cd "$1" && find . -type f -not -name '*.pyc' -not -path '*/__pycache__/*' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha1sum | sha1sum | cut -d' ' -f1)
}

# Overlay the CADRO erpnext package and banking sources (shipped in the image) onto the
# pinned upstream app, only when they differ from what was applied last time.
#   fresh  - first provisioning; assets are built later by the provisioning steps
#   update - restart of an existing bench; migrate / rebuild what changed
apply_cadro_code() {
    local mode="$1" app="${FRAPPE_BENCH_PATH}/apps/erpnext" new old
    mkdir -p "${CADRO_STATE_DIR}"

    if [ -d "${CADRO_ERPNEXT_SRC}" ]; then
        new="$(dir_hash "${CADRO_ERPNEXT_SRC}")"
        old="$(cat "${CADRO_STATE_DIR}/erpnext.sha" 2>/dev/null || true)"
        if [ "${new}" != "${old}" ]; then
            cp -a "${CADRO_ERPNEXT_SRC}/." "${app}/erpnext/" && \
                echo "Applied CADRO erpnext package (${mode})"
            if [ "${mode}" = "update" ]; then
                (cd "${FRAPPE_BENCH_PATH}" && bench --site "${SITE_NAME}" migrate && bench build --app erpnext) || \
                    echo "WARNING: migrate/build after erpnext update had issues"
            fi
            echo "${new}" > "${CADRO_STATE_DIR}/erpnext.sha"
        fi
    else
        echo "WARNING: ${CADRO_ERPNEXT_SRC} not found; running upstream erpnext unmodified"
    fi

    if [ -d "${CADRO_BANKING_SRC}" ]; then
        new="$(dir_hash "${CADRO_BANKING_SRC}")"
        old="$(cat "${CADRO_STATE_DIR}/banking.sha" 2>/dev/null || true)"
        if [ "${new}" != "${old}" ]; then
            rm -rf "${app}/banking/src" && cp -a "${CADRO_BANKING_SRC}" "${app}/banking/src" && \
                echo "Applied CADRO banking sources (${mode})"
            if [ "${mode}" = "update" ]; then
                (cd "${app}/banking" && yarn build) || echo "WARNING: banking build had issues"
            fi
            echo "${new}" > "${CADRO_STATE_DIR}/banking.sha"
        fi
    fi
}

# Frappe reads translations from compiled .mo files, not from .po files.
# Overlay the CADRO translation file (if shipped in the image) onto the
# erpnext app, then compile it. Safe to run on every start.
apply_cadro_locale() {
    local erpnext_locale="${FRAPPE_BENCH_PATH}/apps/erpnext/erpnext/locale"
    if [ -f "${CADRO_LOCALE_OVERLAY}" ] && [ -d "${erpnext_locale}" ]; then
        cp "${CADRO_LOCALE_OVERLAY}" "${erpnext_locale}/${CADRO_LANGUAGE}.po"
        echo "Applied CADRO ${CADRO_LANGUAGE}.po overlay to erpnext"
    fi
    # Smoke-test fixes for strings missing upstream (frappe core, unmarked erpnext text).
    if [ -f "${CADRO_LOCALE_PATCH}" ] && [ -f "${CADRO_LOCALE_MERGE}" ] && [ -f "${erpnext_locale}/${CADRO_LANGUAGE}.po" ]; then
        "${FRAPPE_BENCH_PATH}/env/bin/python" "${CADRO_LOCALE_MERGE}" \
            "${erpnext_locale}/${CADRO_LANGUAGE}.po" "${CADRO_LOCALE_PATCH}" || \
            echo "WARNING: could not merge CADRO translation patch"
    fi
    (cd "${FRAPPE_BENCH_PATH}" && \
        bench --site "${SITE_NAME}" compile-po-to-mo --locale "${CADRO_LANGUAGE}" --force) || \
        echo "WARNING: compile-po-to-mo failed; translations may be incomplete"
    (cd "${FRAPPE_BENCH_PATH}" && bench --site "${SITE_NAME}" clear-cache) || true
}

# Assets are built once during provisioning. The asset file watcher (`bench watch`) is a
# development tool and exhausted the 4 GB container limit after restarts, so it is dropped
# from the Procfile on every start.
strip_watch() {
    if [ -f "${FRAPPE_BENCH_PATH}/Procfile" ]; then
        sed -i '/^watch:/d' "${FRAPPE_BENCH_PATH}/Procfile"
    fi
}

# Only provision if no site exists yet
if [ -f "${FRAPPE_BENCH_PATH}/sites/${SITE_NAME}/site_config.json" ]; then
    echo "Site ${SITE_NAME} already provisioned, skipping to bench start..."
    cd "${FRAPPE_BENCH_PATH}"
    apply_cadro_code update
    apply_cadro_locale
    strip_watch
    exec "$@"
fi

# Fresh provision needed (the bench is a sub-directory of the volume mount).
if [ -d "${FRAPPE_BENCH_PATH}" ]; then
    echo "Removing stale bench at ${FRAPPE_BENCH_PATH} ..."
    rm -rf "${FRAPPE_BENCH_PATH}"
fi
echo "Provisioning bench at ${FRAPPE_BENCH_PATH} ..."

# Create and configure bench
# Use pre-cloned frappe to avoid network timeout
bench init --skip-assets --frappe-path /home/frappe/frappe --python "$(which python)" "${FRAPPE_BENCH_PATH}"
cd "${FRAPPE_BENCH_PATH}"

# bench init may leave sites/common_site_config.json as a directory on some
# volume mounts.  Remove it and create a proper file.
if [ -d sites/common_site_config.json ]; then
    rm -rf sites/common_site_config.json
fi
if [ ! -f sites/common_site_config.json ]; then
    echo '{}' > sites/common_site_config.json
fi

# Get apps at pinned commits (skip assets during get-app, build all together later)
bench get-app --skip-assets erpnext --branch develop
pin_app erpnext "${ERPNEXT_COMMIT}" || echo "WARNING: could not pin erpnext to ${ERPNEXT_COMMIT}; running upstream develop HEAD"
apply_cadro_code fresh

# payments is optional; gracefully skip on any failure
bench get-app --skip-assets payments --branch develop || true
(pin_app payments "${PAYMENTS_COMMIT}" 2>/dev/null) || true

# Build assets for all apps at once
bench build || {
    echo "WARNING: bench build had issues, trying to continue..."
}

# Create site (skip if exists)
if [ ! -f "${FRAPPE_BENCH_PATH}/sites/${SITE_NAME}/site_config.json" ]; then
    bench new-site "${SITE_NAME}" \
        --db-type mariadb \
        --db-host "${DB_HOST}" \
        --db-port "${DB_PORT}" \
        --db-root-password "${DB_PASSWORD}" \
        --admin-password "${ADMIN_PASSWORD}" \
        --mariadb-root-username root \
        --no-mariadb-socket
else
    echo "Site ${SITE_NAME} already exists, skipping creation."
fi

# Install apps on site
bench --site "${SITE_NAME}" install-app erpnext || {
    echo "WARNING: erpnext install-app had issues, trying to continue..."
}
bench --site "${SITE_NAME}" install-app payments 2>/dev/null || true

apply_cadro_locale

# Turkish locale defaults (System Settings + Administrator user)
set_single() {
    bench --site "${SITE_NAME}" execute frappe.db.set_single_value \
        --args "[\"System Settings\", \"$1\", \"$2\"]" || \
        echo "WARNING: could not set System Settings.$1"
}
bench --site "${SITE_NAME}" execute frappe.db.set_value \
    --args "[\"Language\", \"${CADRO_LANGUAGE}\", \"enabled\", 1]" || \
    echo "WARNING: could not enable language ${CADRO_LANGUAGE}"
set_single language "${CADRO_LANGUAGE}"
set_single country "${CADRO_COUNTRY}"
set_single time_zone "${CADRO_TIME_ZONE}"
set_single date_format "${CADRO_DATE_FORMAT}"
set_single number_format "${CADRO_NUMBER_FORMAT}"
set_single first_day_of_the_week Monday
bench --site "${SITE_NAME}" execute erpnext.regional.sync_system_defaults || \
    echo "WARNING: could not sync System Settings into global defaults"
bench --site "${SITE_NAME}" execute frappe.db.set_value \
    --args "[\"User\", \"Administrator\", \"language\", \"${CADRO_LANGUAGE}\"]" || \
    echo "WARNING: could not set Administrator language"
bench --site "${SITE_NAME}" clear-cache || true

bench set-config -g db_host "${DB_HOST}"
bench set-config -g db_port "${DB_PORT}"
bench set-config -g redis_cache "redis://redis-cache:6379"
bench set-config -g redis_queue "redis://redis-queue:6379"
bench set-config -g redis_socketio "redis://redis-socketio:6379"
bench set-config -g socketio_port 9000
bench set-config -g developer_mode 0
bench set-config -g server_script_enabled 1
bench set-config -g web_host "0.0.0.0"

echo "Bench provisioned successfully. Starting..."

# Patch Procfile to bind web to 0.0.0.0 for Docker port mapping
PROCFILE="${FRAPPE_BENCH_PATH}/Procfile"
if [ -f "${PROCFILE}" ] && grep -q 'web:' "${PROCFILE}"; then
    sed -i 's/\(web:.*\)/\1 --host 0.0.0.0/' "${PROCFILE}"
    echo "Patched Procfile web command with --host 0.0.0.0"
fi
strip_watch

exec "$@"