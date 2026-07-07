#!/usr/bin/env sh
set -eu

mkdir -p ../backend/public/storage

docker compose \
  --env-file env/production/backend.env \
  --env-file env/production/frontend.env \
  -f compose/compose.production.yml \
  up -d --build

# Force recreate Nginx layers so stale upstream DNS is resolved after rebuilds.
docker compose \
  --env-file env/production/backend.env \
  --env-file env/production/frontend.env \
  -f compose/compose.production.yml \
  up -d --force-recreate backend-nginx reverse-proxy
