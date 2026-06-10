#!/usr/bin/env sh
set -eu

mkdir -p ../backend/public/storage

docker compose \
  --env-file env/production/backend.env \
  --env-file env/production/frontend.env \
  -f compose/compose.production.yml \
  up -d --build
