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
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
RUN cargo build --locked --release -p pcr-server --bin pcr-server \
    && cargo build --locked --release -p pcr-runner --bin pcr-runner \
    && cargo build --locked --release -p pcr-server --bin pcr-migrate

# ── Worker + scientific toolchain ──────────────────────────────────────────
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS science-builder
WORKDIR /src
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/uv \
    && /opt/uv/bin/python -m pip install --no-cache-dir uv==0.12.10
ENV PATH=/opt/uv/bin:${PATH}
COPY tools ./tools
COPY contracts/tools.toml ./contracts/tools.toml
COPY scripts/provision-tools.py scripts/toolchain_config.py ./scripts/
RUN UV_PROJECT_ENVIRONMENT=/opt/worker \
    uv sync --project tools --frozen --extra folding --no-dev --no-editable
RUN PCRSTUDIO_PROVISION_PREFIX=/opt/pcrstudio/tools \
    PCRSTUDIO_PROVISION_WORKER_PYTHON=/opt/worker/bin/python \
    python scripts/provision-tools.py \
    && rm -rf /opt/pcrstudio/tools/downloads /opt/pcrstudio/tools/primerpooler-build

# ── Minimal common runtime ──────────────────────────────────────────────────
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS process-runtime-base
ARG PCRSTUDIO_BUILD_ID
RUN case "$PCRSTUDIO_BUILD_ID" in \
      (*[!0-9a-f]*|'') echo 'fatal: PCRSTUDIO_BUILD_ID must be lowercase hex' >&2; exit 64 ;; \
    esac \
    && [ "${#PCRSTUDIO_BUILD_ID}" -eq 64 ] \
    || (echo 'fatal: PCRSTUDIO_BUILD_ID must be a 64-character SHA-256 digest' >&2; exit 64)
LABEL org.pcrstudio.source-manifest.sha256="$PCRSTUDIO_BUILD_ID"
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 pcr \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin pcr
ENV PCRSTUDIO_BUILD_ID=${PCRSTUDIO_BUILD_ID} \
    HOME=/tmp/pcrstudio-home

# ── Scientific runtime shared only by API and durable runner ───────────────
FROM process-runtime-base AS science-runtime-base
USER root
# curl is used by the API health probe. MAFFT's portable wrapper expects common
# POSIX text utilities; libgomp is used by scientific wheels/native binaries.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
       bash coreutils curl gawk grep libgomp1 procps sed \
    && rm -rf /var/lib/apt/lists/*
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
    CMD curl --fail --silent http://127.0.0.1:8080/ready || exit 1
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
