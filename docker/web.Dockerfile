# The Next.js interface.
FROM node:24-alpine@sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf AS base
# Docker build steps have no interactive terminal. Keep Corepack deterministic
# and non-interactive when it materialises the pnpm version pinned in
# package.json.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    COREPACK_DEFAULT_TO_LATEST=0
RUN corepack enable
WORKDIR /src

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json ./web/
RUN pnpm install --frozen-lockfile

FROM base AS builder
COPY --from=deps /src/node_modules ./node_modules
COPY --from=deps /src/web/node_modules ./web/node_modules
COPY . .

# Inlined into the bundle at build time, so it has to be the public origin the
# site will actually be served from — canonical URLs and the sitemap use it.
ARG NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL

# Next embeds the Server Actions encryption key in the production build. The
# key therefore must be stable across replicas/rebuilds, but it must not travel
# through ARG/ENV where image history or provenance can retain it. BuildKit
# exposes the deployment-owned file only to this RUN instruction.
#
# The API is not reachable during the image build. Pages that would have been
# pre-rendered fall back to rendering on first request and are cached from
# there, so the build does not depend on the core being up.
RUN --mount=type=secret,id=next_server_actions_key,required=true \
    NEXT_SERVER_ACTIONS_ENCRYPTION_KEY="$(cat /run/secrets/next_server_actions_key)" \
    node -e 'const k=process.env.NEXT_SERVER_ACTIONS_ENCRYPTION_KEY || ""; const b=Buffer.from(k, "base64"); if (![16,24,32].includes(b.length) || b.toString("base64") !== k) { throw new Error("NEXT_SERVER_ACTIONS_ENCRYPTION_KEY must be canonical base64 for 16/24/32 bytes"); }' \
    && NEXT_SERVER_ACTIONS_ENCRYPTION_KEY="$(cat /run/secrets/next_server_actions_key)" pnpm --filter web build

FROM base AS runtime
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup --system --gid 10001 nodejs \
    && adduser --system --uid 10001 nextjs

# `output: "standalone"` emits a server that carries only the modules it uses.
COPY --from=builder --chown=nextjs:nodejs /src/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /src/web/.next/static ./web/.next/static
COPY --from=builder --chown=nextjs:nodejs /src/web/public ./web/public

USER nextjs
EXPOSE 3000
CMD ["node", "web/server.js"]
