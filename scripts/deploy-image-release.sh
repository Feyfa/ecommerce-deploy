#!/usr/bin/env sh
set -eu

# Deploy the three application images selected by a manual Actions workflow.
# Arguments: environment, frontend digest, backend PHP digest, backend Nginx
# digest, frontend source SHA, and backend source SHA. When GHCR_USER is set,
# stdin must contain a short-lived GHCR token. The last healthy image manifest
# remains active until the candidate passes both HTTP checks.
# Requires Python 3 and flock on the VM. Retention protects active/previous
# manifests, candidates and all containers; only historical project digests can
# be removed. Hold the checkout-local lock throughout deployment and retention.

# --- step 1 - start - validate immutable image and source references
if [ "$#" -ne 6 ]; then
  echo "Usage: $0 staging|production FRONTEND_IMAGE BACKEND_IMAGE BACKEND_NGINX_IMAGE FRONTEND_SHA BACKEND_SHA" >&2
  exit 2
fi

environment=$1
frontend_image=$2
backend_image=$3
backend_nginx_image=$4
frontend_sha=$5
backend_sha=$6

case "$environment" in
  staging|production) ;;
  *) echo "Unsupported environment: $environment" >&2; exit 2 ;;
esac

printf '%s\n' "$frontend_image" | grep -Eq '^ghcr\.io/feyfa/ecommerce-frontend@sha256:[0-9a-f]{64}$'
printf '%s\n' "$backend_image" | grep -Eq '^ghcr\.io/feyfa/ecommerce-backend-php@sha256:[0-9a-f]{64}$'
printf '%s\n' "$backend_nginx_image" | grep -Eq '^ghcr\.io/feyfa/ecommerce-backend-nginx@sha256:[0-9a-f]{64}$'
printf '%s\n' "$frontend_sha" | grep -Eq '^[0-9a-f]{40}$'
printf '%s\n' "$backend_sha" | grep -Eq '^[0-9a-f]{40}$'
# --- step 1 - end - validate immutable image and source references

# --- step 2 - start - lock the deployment and ensure safe pull capacity
# Serialize manual and workflow deployments on this VM, not only Actions runs.
# The ignored tmp directory is inside the trusted deploy checkout. Append-open
# avoids truncation; never remove the lock file while another process may use it.
mkdir -p tmp
exec 9>>tmp/image-release.lock
if ! flock -n 9; then
  echo "Another image deployment holds the VM lock; no deployment started" >&2
  exit 1
fi

# Check capacity before even allocating a candidate manifest or pulling images.
# A preflight failure leaves the active stack and its manifests unchanged.
python3 scripts/manage-image-retention.py "$environment" ensure-space \
  --lock-fd 9 --candidate "$frontend_image" "$backend_image" "$backend_nginx_image"
# --- step 2 - end - lock the deployment and ensure safe pull capacity

manifest_dir="env/$environment"
current_manifest="$manifest_dir/images.env"
previous_manifest="$manifest_dir/images.previous.env"
candidate_manifest=$(mktemp "$manifest_dir/images.candidate.XXXXXX")
docker_config=

# Remove only temporary credentials and an unpromoted candidate manifest.
# A successful candidate is moved to images.env before this handler runs.
cleanup() {
  if [ -n "$docker_config" ]; then
    rm -rf -- "$docker_config"
  fi
  if [ -f "$candidate_manifest" ]; then
    rm -f -- "$candidate_manifest"
  fi
}
trap cleanup EXIT HUP INT TERM

# Run Docker Compose with the target VM runtime files and one image manifest.
# The first argument is the manifest; remaining arguments are Compose commands.
compose() {
  manifest=$1
  shift
  docker compose \
    --env-file "$manifest_dir/backend.env" \
    --env-file "$manifest_dir/frontend.env" \
    --env-file "$manifest" \
    -f "compose/compose.$environment.yml" \
    "$@"
}

# Verify that both published application ports answer HTTP successfully.
# Resolve host ports from Compose so non-default VM port settings are respected.
verify_health() {
  manifest=$1
  for container_port in 8080 8081; do
    published=$(compose "$manifest" port reverse-proxy "$container_port") || return 1
    host_port=${published##*:}
    healthy=false
    for attempt in 1 2 3 4 5; do
      if curl --fail --silent --show-error --max-time 10 "http://localhost:$host_port" > /dev/null; then
        healthy=true
        break
      fi
      sleep 3
    done
    if [ "$healthy" != true ]; then
      echo "Health check failed on port $host_port" >&2
      return 1
    fi
  done
}

# Require every service in the stack to be running before recording a release
# as healthy; the two HTTP checks alone do not cover workers or databases.
verify_services() {
  manifest=$1
  running=$(compose "$manifest" ps --services --status running) || return 1
  for service in reverse-proxy frontend backend-nginx backend-php backend-worker backend-scheduler postgres redis meilisearch; do
    if ! printf '%s\n' "$running" | grep -Fxq "$service"; then
      echo "Service is not running: $service" >&2
      return 1
    fi
  done
}

# Reactivate the last healthy image set after a candidate fails. A first image
# deploy has no saved manifest, so it leaves recovery to the prior deploy code.
restore_active() {
  if [ ! -f "$current_manifest" ]; then
    echo "First image deployment has no previous image manifest; use the previous deploy revision for recovery" >&2
    return 1
  fi

  echo "Restoring the last healthy image manifest" >&2
  if compose "$current_manifest" up -d --no-build \
    && compose "$current_manifest" up -d --no-build --force-recreate backend-nginx reverse-proxy \
    && verify_health "$current_manifest" \
    && verify_services "$current_manifest"; then
    return 0
  fi

  echo "Rollback also failed; inspect the VM before another deploy" >&2
  return 1
}

# --- step 3 - start - prepare the candidate and temporary registry credentials
chmod 600 "$candidate_manifest"
printf 'FRONTEND_IMAGE=%s\nBACKEND_IMAGE=%s\nBACKEND_NGINX_IMAGE=%s\nFRONTEND_SOURCE_SHA=%s\nBACKEND_SOURCE_SHA=%s\n' \
  "$frontend_image" "$backend_image" "$backend_nginx_image" "$frontend_sha" "$backend_sha" \
  > "$candidate_manifest"

if [ -n "${GHCR_USER:-}" ]; then
  docker_config=$(mktemp -d)
  chmod 700 "$docker_config"
  export DOCKER_CONFIG="$docker_config"
  docker login ghcr.io --username "$GHCR_USER" --password-stdin
fi
# --- step 3 - end - prepare the candidate and temporary registry credentials

# --- step 4 - start - pull and activate the candidate without building on the VM
if compose "$candidate_manifest" pull frontend backend-php backend-nginx \
  && compose "$candidate_manifest" up -d --no-build \
  && compose "$candidate_manifest" up -d --no-build --force-recreate backend-nginx reverse-proxy \
  && verify_health "$candidate_manifest" \
  && verify_services "$candidate_manifest" \
  && compose "$candidate_manifest" ps; then
  if [ -f "$current_manifest" ] && ! cp "$current_manifest" "$previous_manifest"; then
    echo "Could not preserve the last healthy image manifest" >&2
    restore_active || true
    exit 1
  fi
  if ! mv "$candidate_manifest" "$current_manifest"; then
    echo "Could not activate the new image manifest" >&2
    restore_active || true
    exit 1
  fi
  echo "Activated $environment images from frontend $frontend_sha and backend $backend_sha"

  # Retention failure cannot undo a healthy release or remove its rollback set.
  # Surface an Actions warning so release verification does not miss the debt.
  if ! python3 scripts/manage-image-retention.py "$environment" cleanup \
    --lock-fd 9 --candidate "$frontend_image" "$backend_image" "$backend_nginx_image"; then
    echo "::warning::Release is healthy, but image retention failed; inspect the VM before closing the release"
  fi
else
  echo "Candidate $environment deployment failed" >&2
  restore_active || true
  exit 1
fi
# --- step 4 - end - pull and activate the candidate without building on the VM
