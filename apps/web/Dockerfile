# ---- Dependencies ----
ARG IMAGE_REGISTRY=
FROM ${IMAGE_REGISTRY}node:20-alpine AS deps
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Enable pnpm with the configured npm registry
RUN npm config set registry "${NPM_REGISTRY}" && \
    corepack enable && corepack prepare pnpm@9.12.0 --activate

# Copy workspace root files (including lockfile for frozen install)
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml turbo.json .npmrc ./
COPY apps/web/package.json apps/web/

# Install dependencies (hoisted mode via .npmrc)
RUN pnpm install --frozen-lockfile

# ---- Builder ----
FROM ${IMAGE_REGISTRY}node:20-alpine AS builder
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm config set registry "${NPM_REGISTRY}" && \
    corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml turbo.json .npmrc ./
COPY apps/web ./apps/web

# Build
RUN pnpm --filter web build

# ---- Runner ----
FROM ${IMAGE_REGISTRY}node:20-alpine AS runner
RUN apk add --no-cache wget
WORKDIR /app

ENV NODE_ENV=production

# Copy standalone output (includes server.js + minimal node_modules)
COPY --from=builder /app/apps/web/.next/standalone ./
# Copy static assets and public dir (not included in standalone)
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "apps/web/server.js"]
