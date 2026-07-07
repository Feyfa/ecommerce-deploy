#!/usr/bin/env sh
set -eu

mkdir -p ../backend/public/storage

docker compose \
  --env-file env/staging/backend.env \
  --env-file env/staging/frontend.env \
  -f compose/compose.staging.yml \
  up -d --build

# Force recreate Nginx layers so stale upstream DNS is resolved after rebuilds.
docker compose \
  --env-file env/staging/backend.env \
  --env-file env/staging/frontend.env \
  -f compose/compose.staging.yml \
  up -d --force-recreate backend-nginx reverse-proxy
