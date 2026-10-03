#!/usr/bin/env sh
set -eu

# Exercise image activation and rollback without a Docker daemon or VM.
# Temporary Compose and curl stand-ins record which immutable manifest the
# deployment script used. No real registry or application container is touched.

# --- step 1 - start - prepare an isolated fake Docker environment
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
test_root=$(mktemp -d)
trap 'rm -rf -- "$test_root"' EXIT HUP INT TERM
mkdir -p "$test_root/bin" "$test_root/env/staging"
mkdir -p "$test_root/scripts"
touch "$test_root/env/staging/backend.env" "$test_root/env/staging/frontend.env"

# Substitute only the retention boundary; helper safety is tested separately.
cat > "$test_root/scripts/manage-image-retention.py" <<'EOF'
import os
import fcntl
from pathlib import Path
import sys

mode = sys.argv[2]
assert os.fstat(9).st_ino == Path("tmp/image-release.lock").stat().st_ino
fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
with Path(os.environ["DOCKER_LOG"]).open("a") as log:
    log.write(f"retention {mode}\n")
if mode == "ensure-space" and os.environ.get("FAIL_SPACE") == "1":
    raise SystemExit(1)
if mode == "cleanup" and os.environ.get("FAIL_RETENTION") == "1":
    raise SystemExit(1)
EOF

# Use the same flock semantics on macOS, where the Linux CLI is unavailable.
cat > "$test_root/bin/flock" <<'EOF'
#!/usr/bin/env python3
import fcntl
import os
import sys

if os.environ.get("FAIL_LOCK") == "1":
    raise SystemExit(1)
try:
    fcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit(1)
EOF
chmod +x "$test_root/bin/flock"

cat > "$test_root/bin/docker" <<'EOF'
#!/usr/bin/env sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
if [ "$1" = login ]; then
  cat > /dev/null
  exit 0
fi
case "$*" in
  *' port reverse-proxy 8080') echo '0.0.0.0:8080'; exit 0 ;;
  *' port reverse-proxy 8081') echo '0.0.0.0:8081'; exit 0 ;;
  *' ps --services --status running')
    printf '%s\n' reverse-proxy frontend backend-nginx backend-php \
      backend-worker backend-scheduler postgres redis meilisearch
    exit 0 ;;
esac
if [ "${FAIL_CANDIDATE:-0}" = 1 ]; then
  case "$*" in
    *images.candidate*' up '*) exit 42 ;;
  esac
fi
EOF
chmod +x "$test_root/bin/docker"

cat > "$test_root/bin/curl" <<'EOF'
#!/usr/bin/env sh
exit 0
EOF
chmod +x "$test_root/bin/curl"

digest=$(printf '%064d' 0)
source_sha=$(printf '%040d' 0)
frontend_image="ghcr.io/feyfa/ecommerce-frontend@sha256:$digest"
backend_image="ghcr.io/feyfa/ecommerce-backend-php@sha256:$digest"
backend_nginx_image="ghcr.io/feyfa/ecommerce-backend-nginx@sha256:$digest"
export DOCKER_LOG="$test_root/docker.log"
# --- step 1 - end - prepare an isolated fake Docker environment

# --- step 2 - start - verify a healthy first release activates its manifest
(
  cd "$test_root"
  PATH="$test_root/bin:$PATH" GHCR_USER=feyfa \
    sh "$repo_root/scripts/deploy-image-release.sh" staging \
      "$frontend_image" "$backend_image" "$backend_nginx_image" \
      "$source_sha" "$source_sha" <<'EOF'
temporary-test-token
EOF
)
test -f "$test_root/env/staging/images.env"
grep -q "^FRONTEND_IMAGE=$frontend_image$" "$test_root/env/staging/images.env"
grep -q '^login ghcr.io --username feyfa --password-stdin$' "$DOCKER_LOG"
test "$(head -n 1 "$DOCKER_LOG")" = 'retention ensure-space'
test "$(tail -n 1 "$DOCKER_LOG")" = 'retention cleanup'
cp "$test_root/env/staging/images.env" "$test_root/healthy.env"
# --- step 2 - end - verify a healthy first release activates its manifest

# --- step 3 - start - verify a failed candidate reactivates the healthy set
if (
  cd "$test_root"
  PATH="$test_root/bin:$PATH" FAIL_CANDIDATE=1 \
    sh "$repo_root/scripts/deploy-image-release.sh" staging \
      "$frontend_image" "$backend_image" "$backend_nginx_image" \
      "$source_sha" "$source_sha"
); then
  echo 'A failed candidate unexpectedly succeeded' >&2
  exit 1
fi

cmp "$test_root/healthy.env" "$test_root/env/staging/images.env"
grep -q 'images.env.* up -d --no-build' "$DOCKER_LOG"
if grep -q -- '--build' "$DOCKER_LOG"; then
  echo 'The VM must not build application images' >&2
  exit 1
fi
echo 'Image release activation and rollback checks passed'
# --- step 3 - end - verify a failed candidate reactivates the healthy set

# --- step 4 - start - reject low capacity and concurrent deployment before pull
for failure in FAIL_SPACE FAIL_LOCK; do
  : > "$DOCKER_LOG"
  if (
    cd "$test_root"
    env PATH="$test_root/bin:$PATH" "$failure=1" \
      sh "$repo_root/scripts/deploy-image-release.sh" staging \
        "$frontend_image" "$backend_image" "$backend_nginx_image" \
        "$source_sha" "$source_sha"
  ); then
    echo 'A failed preflight unexpectedly started deployment' >&2
    exit 1
  fi
  cmp "$test_root/healthy.env" "$test_root/env/staging/images.env"
  if grep -q '^compose ' "$DOCKER_LOG"; then
    echo 'Preflight failure must not pull or activate images' >&2
    exit 1
  fi
done
# --- step 4 - end - reject low capacity and concurrent deployment before pull

# --- step 5 - start - preserve a healthy release when final retention fails
: > "$DOCKER_LOG"
(
  cd "$test_root"
  PATH="$test_root/bin:$PATH" FAIL_RETENTION=1 \
    sh "$repo_root/scripts/deploy-image-release.sh" staging \
      "$frontend_image" "$backend_image" "$backend_nginx_image" \
      "$source_sha" "$source_sha"
) > "$test_root/retention-warning.log"
grep -q '::warning::Release is healthy' "$test_root/retention-warning.log"
cmp "$test_root/healthy.env" "$test_root/env/staging/images.env"
cmp "$test_root/healthy.env" "$test_root/env/staging/images.previous.env"
if grep -q 'images.env.* up -d' "$DOCKER_LOG"; then
  echo 'Retention failure must not rollback a healthy release' >&2
  exit 1
fi
echo 'Capacity, locking and post-release retention checks passed'
# --- step 5 - end - preserve a healthy release when final retention fails
