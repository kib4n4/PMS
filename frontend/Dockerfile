# frontend/Dockerfile
#
# Production build — three stages so the final image ships only the
# pruned `.next/standalone` output and static assets, not the full
# node_modules/devDependencies tree used to build it.

# ---- deps: install exactly what package-lock.json pins ----
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- builder: production build ----
FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# BACKEND_API_URL is read at request time (in app/api/*/route.ts handlers),
# not baked in at build time, so no build-arg is needed here.
RUN npm run build

# ---- runner: minimal production image ----
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN useradd -m nextjs
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD node -e "fetch('http://localhost:3000/').then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
