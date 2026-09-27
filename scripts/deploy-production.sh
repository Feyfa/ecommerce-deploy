#!/usr/bin/env sh
set -eu

exec sh scripts/deploy-image-release.sh production "$@"
