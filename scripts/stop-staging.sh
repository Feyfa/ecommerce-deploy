#!/usr/bin/env sh
set -eu

docker compose \
  --env-file env/staging/backend.env \
  --env-file env/staging/frontend.env \
  --env-file env/staging/images.env \
  -f compose/compose.staging.yml \
  down
