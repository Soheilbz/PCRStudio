ARG OFFICIAL_IMAGE_REGISTRY=public.ecr.aws/docker
FROM ${OFFICIAL_IMAGE_REGISTRY}/library/node:24.21.0-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS node
FROM ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv
FROM mcr.microsoft.com/playwright:v1.63.0-noble@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27 AS browsers
FROM ${OFFICIAL_IMAGE_REGISTRY}/library/python:3.13.16-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641 AS python-base
COPY --from=uv /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy
WORKDIR /build/backend
COPY backend/pyproject.toml backend/uv.lock ./

FROM python-base AS runtime-deps
RUN uv sync --frozen --no-dev --no-install-project

FROM python-base AS dev-deps
RUN uv sync --frozen --no-install-project

FROM node AS frontend-deps
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit

FROM frontend-deps AS frontend-build
COPY frontend/ ./
COPY ops/Caddyfile /build/Caddyfile.template
COPY ops/prepare_caddy.mjs /build/ops/prepare_caddy.mjs
RUN npm run build && node /build/ops/prepare_caddy.mjs build/client/index.html /build/Caddyfile.template /build/Caddyfile

FROM ${OFFICIAL_IMAGE_REGISTRY}/library/caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f AS edge
COPY --from=frontend-build /build/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /build/frontend/build/client /srv
RUN setcap -r /usr/bin/caddy && mkdir -p /config /data && chown -R 10001:10001 /config /data /srv
USER 10001:10001
EXPOSE 8080

FROM python-base AS api
COPY --from=runtime-deps /opt/venv /opt/venv
COPY backend/ /app/backend/
COPY ops/safe_gunicorn.py /app/backend/safe_gunicorn.py
WORKDIR /app/backend
ENV PATH=/opt/venv/bin:$PATH
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home app
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "/dev/null", "--error-logfile", "-", "--logger-class", "safe_gunicorn.SafeLogger"]

FROM python-base AS tools
ARG LOCAL_UID=1000
ARG LOCAL_GID=1000
COPY --from=dev-deps /opt/venv /opt/venv
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
ENV PATH=/opt/venv/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/opt/playwright UV_CACHE_DIR=/tmp/uv-cache HOME=/tmp/tools-home
COPY --from=frontend-deps /build/frontend /workspace/frontend
RUN cd /workspace/frontend && npx playwright install-deps chromium && \
    chown -R ${LOCAL_UID}:${LOCAL_GID} /workspace/frontend
COPY --from=browsers /ms-playwright/chromium_headless_shell-1243 /opt/playwright/chromium_headless_shell-1243
COPY --from=browsers /ms-playwright/ffmpeg-1011 /opt/playwright/ffmpeg-1011
RUN chmod -R a+rX /opt/playwright
WORKDIR /workspace
USER ${LOCAL_UID}:${LOCAL_GID}
CMD ["python", "/workspace/scripts/project_gate.py", "deep"]
