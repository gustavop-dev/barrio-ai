# syntax=docker/dockerfile:1
# Oficina de Barrio AI: build the static PWA, then hand it to Caddy in /srv.
# The production Caddyfile (reverse proxy to Django, headers) lives elsewhere.

FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM caddy:2
COPY --from=build /app/dist /srv
