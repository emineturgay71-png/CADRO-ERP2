#!/bin/bash
# ---------------------------------------------------------------------------
# Self-signed TLS certificate for staging (docker-compose.tls.yml).
#
# Writes cadro/certs/fullchain.pem and cadro/certs/privkey.pem (key mode 600) for the given
# host name; a browser will warn because no CA vouches for it. Production deployments use the
# CA-issued fullchain.pem/privkey.pem in the same place instead.
#
# Usage (from the repository root):  bash scripts/make_self_signed_cert.sh <host-name> [days]
# Existing files are never overwritten.
# ---------------------------------------------------------------------------

set -euo pipefail

HOST="${1:?Host name required}"
DAYS="${2:-90}"
OUT_DIR="${CADRO_CERT_DIR:-cadro/certs}"

if ! [[ "${HOST}" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$ ]]; then
    echo "ERROR: invalid host name: ${HOST}" >&2
    exit 1
fi
if ! [[ "${DAYS}" =~ ^[0-9]+$ ]] || [ "${DAYS}" -lt 1 ]; then
    echo "ERROR: days must be a positive integer" >&2
    exit 1
fi
if [ -e "${OUT_DIR}/fullchain.pem" ] || [ -e "${OUT_DIR}/privkey.pem" ]; then
    echo "ERROR: ${OUT_DIR} already holds a certificate; remove it first to replace it" >&2
    exit 1
fi

mkdir -p "${OUT_DIR}"
umask 077
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days "${DAYS}" \
    -keyout "${OUT_DIR}/privkey.pem" -out "${OUT_DIR}/fullchain.pem" \
    -subj "/CN=${HOST}" -addext "subjectAltName=DNS:${HOST}"
# nginx runs as root at start-up and reads the key then, but the mount is read-only for others.
chmod 644 "${OUT_DIR}/fullchain.pem"
chmod 600 "${OUT_DIR}/privkey.pem"
echo "Self-signed certificate for ${HOST} written to ${OUT_DIR} (valid ${DAYS} days)."
