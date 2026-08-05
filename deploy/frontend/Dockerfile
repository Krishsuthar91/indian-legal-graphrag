# ---------------------------------------------------------------------------
# Production frontend image for the Explaintool React dashboard.
#
# Multi-stage build:
#   stage 1 - build ui/dist with Node + TypeScript + Vite
#   stage 2 - nginx:alpine serving the static bundle + reverse-proxying /api
# ---------------------------------------------------------------------------

# ---------- Stage 1: build ---------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /build

COPY ui/package.json ui/package-lock.json ./
RUN npm ci

COPY ui/ ./
RUN npm run build

# ---------- Stage 2: serve ----------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Static-file-only nginx config (the edge nginx reverse-proxies traffic here).
COPY deploy/nginx/nginx-frontend.conf /etc/nginx/nginx.conf

# Static frontend bundle.
COPY --from=build /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO /dev/null http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
