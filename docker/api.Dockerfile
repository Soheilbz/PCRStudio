# PCRStudio Linux x86_64 application images.
#
# One build graph produces three deliberately separate runtime artifacts:
#   api-runtime     interactive HTTP/scientific gateway
#   runner-runtime  durable PostgreSQL-backed scientific executor
#   migrate-runtime database migrator with no scientific Python/native stack
#
# API and runner both execute scientific operations today, so both inherit the
# exact qualified scientific runtime. The migrator does not, and therefore must
# not carry that attack surface or image weight merely for build convenience.

# ── Rust binaries ───────────────────────────────────────────────────────────
FROM rust:1.94-bookworm@sha256:6ae102bdbf528294bc79ad6e1fae682f6f7c2a6e6621506ba959f9685b308a55 AS rust-builder
ENV CARGO_NET_RETRY=5 \
    CARGO_HTTP_TIMEOUT=180 \
    CARGO_HTTP_LOW_SPEED_LIMIT=1 \
    CARGO_HTTP_MULTIPLEXING=false
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
RUN --network=host cargo build --locked --release -p pcr-server --bin pcr-server \
    && cargo build --locked --release -p pcr-runner --bin pcr-runner \
    && cargo build --locked --release -p pcr-server --bin pcr-migrate

# ── Reusable Python/glibc runtime assets ────────────────────────────────────
FROM python:3.12-slim-trixie@sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79 AS runtime-assets
ARG DEBIAN_SNAPSHOT=20260901T000000Z
WORKDIR /src
COPY docker/configure-debian-snapshot.sh /usr/local/bin/configure-debian-snapshot
RUN --network=host configure-debian-snapshot "$DEBIAN_SNAPSHOT" \
    && apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Worker + scientific toolchain ──────────────────────────────────────────
FROM runtime-assets AS science-builder
RUN --network=host configure-debian-snapshot "$DEBIAN_SNAPSHOT" \
    && apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/* /usr/local/bin/configure-debian-snapshot
RUN --network=host python -m venv /opt/uv \
    && /opt/uv/bin/python -m pip install --no-cache-dir uv==0.12.10
ENV PATH=/opt/uv/bin:${PATH}
COPY tools ./tools
COPY contracts/tools.toml ./contracts/tools.toml
COPY scripts/provision-tools.py scripts/toolchain_config.py ./scripts/
RUN --network=host UV_PROJECT_ENVIRONMENT=/opt/worker \
    uv sync --project tools --frozen --extra folding --no-dev --no-editable
RUN --network=host PCRSTUDIO_PROVISION_PREFIX=/opt/pcrstudio/tools \
    PCRSTUDIO_PROVISION_WORKER_PYTHON=/opt/worker/bin/python \
    python scripts/provision-tools.py \
    && rm -rf /opt/pcrstudio/tools/downloads /opt/pcrstudio/tools/primerpooler-build

# ── Minimal common runtime ──────────────────────────────────────────────────
# ── Package-manager-free runtime foundation ─────────────────────────────────
# The official Python slim image is retained as the build/provisioning source,
# but it carries Debian Essential packages that are outside the application
# runtime and currently have no security-fixed versions in Debian metadata.
# Start final images from the official BusyBox glibc image instead and copy
# only the glibc/CA runtime assets and the already-qualified application files.
# This removes the vulnerable package-manager/userland surface without hiding
# package metadata or weakening the scanner policy.
FROM busybox:1.37.0-glibc@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0 AS process-runtime-base
ARG PCRSTUDIO_BUILD_ID
LABEL org.pcrstudio.product="PCRStudio" \
      org.pcrstudio.lifecycle="managed" \
      org.pcrstudio.cache-policy="dedicated-builder-8GB"
RUN case "$PCRSTUDIO_BUILD_ID" in \
      (*[!0-9a-f]*|'') echo 'fatal: PCRSTUDIO_BUILD_ID must be lowercase hex' >&2; exit 64 ;; \
    esac \
    && [ "${#PCRSTUDIO_BUILD_ID}" -eq 64 ] \
    || (echo 'fatal: PCRSTUDIO_BUILD_ID must be a 64-character SHA-256 digest' >&2; exit 64)
LABEL org.pcrstudio.source-manifest.sha256="$PCRSTUDIO_BUILD_ID"
# BusyBox is the only final-stage userland. The Python/Debian builder supplies
# glibc and the CA bundle; no apt database, compiler, or package-manager state
# crosses the stage boundary.
COPY --from=runtime-assets /lib /lib
COPY --from=runtime-assets /usr/lib /usr/lib
COPY --from=runtime-assets /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
RUN addgroup -S -g 10001 pcr \
    && adduser -S -D -H -u 10001 -G pcr -s /bin/false pcr
ENV PCRSTUDIO_BUILD_ID=${PCRSTUDIO_BUILD_ID} \
    HOME=/tmp/pcrstudio-home \
    PATH=/opt/uv/bin:/opt/worker/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# ── Scientific runtime shared only by API and durable runner ───────────────
FROM process-runtime-base AS science-runtime-base
USER root
# BusyBox supplies the small POSIX command surface used by the entrypoint and
# MAFFT wrapper. Python's standard-library HTTP client is used by the API
# health probe; the glibc/native scientific dependencies are copied from the
# already-qualified builder without carrying its package database.
COPY --from=science-builder /usr/local /usr/local
COPY --from=science-builder /opt/uv /opt/uv
COPY --from=science-builder /opt/worker /opt/worker
COPY --from=science-builder /opt/pcrstudio/tools /opt/pcrstudio/tools
COPY contracts/tools.toml /opt/pcrstudio/contracts/tools.toml
COPY scripts/configure-specificity-database.py scripts/toolchain_config.py /opt/pcrstudio/scripts/
COPY scripts/container-scientific-smoke.py /opt/pcrstudio/scripts/container-scientific-smoke.py
COPY --chmod=0555 docker/api-entrypoint.sh /usr/local/bin/pcrstudio-entrypoint
ENV PCR_PYTHON=/opt/worker/bin/python \
    PCRSTUDIO_SCIENTIFIC_POLICY=strict \
    PCRSTUDIO_TOOLCHAIN_MODE=strict \
    PCRSTUDIO_EXTERNAL_VALIDATION=strict \
    MPLCONFIGDIR=/tmp/pcrstudio-matplotlib

# ── Interactive API/scientific gateway ─────────────────────────────────────
FROM science-runtime-base AS api-runtime
COPY --from=rust-builder /src/target/release/pcr-server /usr/local/bin/pcr-server
USER pcr
ENV PCR_BIND=0.0.0.0:8080 \
    RUST_LOG=pcr_server=info,tower_http=info
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=5); raise SystemExit(0 if 200 <= response.status < 400 else 1)"]
ENTRYPOINT ["/usr/local/bin/pcrstudio-entrypoint"]
CMD ["pcr-server"]

# ── Durable scientific runner ───────────────────────────────────────────────
FROM science-runtime-base AS runner-runtime
COPY --from=rust-builder /src/target/release/pcr-runner /usr/local/bin/pcr-runner
USER pcr
ENV RUST_LOG=pcr_runner=info,pcr_application=info
ENTRYPOINT ["/usr/local/bin/pcrstudio-entrypoint"]
CMD ["pcr-runner"]

# ── Database-only migrator ──────────────────────────────────────────────────
FROM process-runtime-base AS migrate-runtime
COPY --from=rust-builder /src/target/release/pcr-migrate /usr/local/bin/pcr-migrate
USER pcr
ENV RUST_LOG=pcr_migrate=info,pcr_storage=info
CMD ["pcr-migrate"]
