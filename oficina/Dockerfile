# syntax=docker/dockerfile:1
# Oficina de Barrio AI: build the static PWA, then hand it to Caddy in /srv.
# The production Caddyfile (reverse proxy to Django, headers) lives elsewhere.
# Build context: the repository root (the PWA imports compartido/, shared with the native app):
#   docker build -f oficina/Dockerfile .
# The root .dockerignore keeps the context to oficina/ and compartido/.

FROM node:24-alpine AS build
WORKDIR /app/oficina
COPY oficina/package.json oficina/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY compartido/ /app/compartido/
COPY oficina/ ./
RUN npm run build

FROM caddy:2
COPY --from=build /app/oficina/dist /srv
