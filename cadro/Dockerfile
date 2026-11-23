# CADRO evaluation bench image
# Python 3.14 + Node 22 LTS + Frappe Bench
# Digest pinning and SBOM are required before production use.

ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim

ARG FRAPPE_USER=frappe
# The bench lives inside the persistent volume mounted at /home/frappe/cadro-data.
ARG FRAPPE_BENCH_PATH=/home/${FRAPPE_USER}/cadro-data/frappe-bench
ENV FRAPPE_BENCH_PATH=${FRAPPE_BENCH_PATH}

# System packages (mariadb-client provides the 'mariadb' CLI binary needed for site creation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential libmariadb-dev libcups2-dev pkgconf \
    redis-tools redis-server cron libssl-dev gnupg ca-certificates \
    mariadb-client file procps \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Shared libraries and fonts for Frappe's bundled headless Chromium (PDF print formats,
# bank statement PDF import). The list follows chromium's own deb.deps; the fonts cover
# Turkish glyphs in generated PDFs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig fonts-liberation fonts-dejavu-core \
    libasound2t64 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcairo2 \
    libdbus-1-3 libexpat1 libgbm1 libglib2.0-0 libnspr4 libnss3 libpango-1.0-0 \
    libudev1 libvulkan1 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxkbcommon0 libxrandr2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Node.js 24 (required by Frappe pinned commit)
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g yarn \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --home-dir /home/${FRAPPE_USER} --create-home --shell /bin/bash ${FRAPPE_USER}

USER ${FRAPPE_USER}
WORKDIR /home/${FRAPPE_USER}

# Mount point of the persistent bench volume; created here so the volume is owned by frappe.
# (bench init refuses an existing directory, so the bench is a sub-directory of the mount.)
RUN mkdir -p /home/${FRAPPE_USER}/cadro-data

# Install bench CLI and ensure it's on PATH
RUN pip install --user frappe-bench
ENV PATH="/home/${FRAPPE_USER}/.local/bin:${PATH}"

# Pre-clone Frappe to a normal (non-bare) repo so bench init can read it.
ARG FRAPPE_COMMIT=96c27e16ed5cfcfaf27d1db2f40c5c7acf871bbd
RUN git clone https://github.com/frappe/frappe.git /home/${FRAPPE_USER}/frappe \
    && git -C /home/${FRAPPE_USER}/frappe fetch origin "${FRAPPE_COMMIT}" \
    && git -C /home/${FRAPPE_USER}/frappe checkout "${FRAPPE_COMMIT}"

# The bench is provisioned at runtime by the entrypoint script.
COPY --chown=${FRAPPE_USER}:${FRAPPE_USER} cadro/entrypoint.sh /home/${FRAPPE_USER}/entrypoint.sh
RUN chmod +x /home/${FRAPPE_USER}/entrypoint.sh

COPY --chown=${FRAPPE_USER}:${FRAPPE_USER} cadro.baseline.json /home/${FRAPPE_USER}/cadro.baseline.json

# Container healthcheck (cadro/docker-compose.yml runs `python scripts/healthcheck.py`).
COPY --chown=${FRAPPE_USER}:${FRAPPE_USER} scripts/healthcheck.py /home/${FRAPPE_USER}/scripts/healthcheck.py
# CADRO's erpnext package (the repo is a fork of the pinned upstream commit). The entrypoint
# overlays it onto the upstream app after checking out the pinned commit, so the running
# code is exactly this repository, including erpnext/locale/tr.po.
COPY --chown=${FRAPPE_USER}:${FRAPPE_USER} erpnext/ /home/${FRAPPE_USER}/cadro-erpnext/erpnext/
COPY --chown=${FRAPPE_USER}:${FRAPPE_USER} banking/src/ /home/${FRAPPE_USER}/cadro-erpnext/banking/src/
# Translation patch for strings missing upstream (frappe core, unmarked erpnext text).
COPY --chown=${FRAPPE_USER}:${FRAPPE_USER} cadro/locale/frappe_tr_overlay.po cadro/locale/merge_po.py /home/${FRAPPE_USER}/cadro-locale/

ENTRYPOINT ["/home/frappe/entrypoint.sh"]
CMD ["bench", "start"]