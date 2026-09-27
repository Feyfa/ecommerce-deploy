# Ecommerce Deployment

This repository owns the deployment stack for the ecommerce frontend and backend.

The manual Deploy workflows in this repository build frontend, backend PHP,
and backend Nginx images from the application repositories on GitHub-hosted
runners. They publish private images to GHCR, then the target VM pulls the
images and runs them with PostgreSQL, Redis, Meilisearch, the buyer-search
queue worker, Laravel Scheduler, and the Nginx reverse proxy.

Redis is an internal Laravel queue service. Meilisearch is an internal,
rebuildable buyer catalog projection protected by a required master key. The
`backend-worker` container uses the backend image and consumes the
`buyer-catalog-search` queue; inspect its logs with
`docker compose logs backend-worker`.

The `backend-scheduler` container uses the same image and runs
`php artisan schedule:work`. It publishes transactional outbox messages every
minute and prunes published history daily. Docker monitors both long-running
processes, so the VM does not run Supervisor or a manual application crontab.

## Repository Layout

Expected local or server layout:

```text
Ecommerce/
  frontend/
  backend/
  deploy/
```

The Compose files use immutable image digests recorded in each VM's ignored
`deploy/env/<environment>/images.env`. Application source checkouts are not
needed to start the stack.

## Local Stack Validation

Local development stays native without Docker. Validate Compose syntax locally
with the example env files; a real stack requires access to the private GHCR
images and a populated `images.env` from a successful deployment.

From the `deploy` folder:

```bash
MEILISEARCH_KEY=ci-key docker compose \
  --env-file env/staging/backend.env.example \
  --env-file env/staging/frontend.env.example \
  --env-file env/staging/images.env.example \
  -f compose/compose.staging.yml config --quiet
```

Local validation URLs:

```text
Frontend: http://localhost:8080
Backend:  http://localhost:8081
```

Run migrations and any required specific seeders after the containers are up:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan migrate --force
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan db:seed --class=PaymentListSeeder --force
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan outbox:status
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan buyer-search:reindex
```

`buyer-search:reindex` clears the derived buyer index and dispatches
synchronization jobs; it does not wait for the queue to drain. Keep this
controlled maintenance window open and verify completion before using the
catalog as a deployment signal:

The same reindex applies the Laravel-owned deterministic `id:asc` tie-breaker
and `pagination.maxTotalHits=10000`. Treat 10,000 as a browsing boundary rather
than a PostgreSQL product limit, and monitor buyer-search latency before any
future increase.

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml ps backend-worker backend-scheduler redis meilisearch
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan outbox:status
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan queue:monitor redis:buyer-catalog-search --max=1
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan queue:failed
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan tinker --execute="dump(app(\\Meilisearch\\Client::class)->index(config('buyer_product_search.index'))->stats());"
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml logs --tail=100 backend-worker
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml logs --tail=100 backend-scheduler
```

The outbox must have no overdue pending or terminal failed messages, the queue
must drain to zero, failed jobs must be resolved, index statistics must contain
the expected documents, and an authenticated buyer-catalog smoke test must
return expected cards and pagination. Use the equivalent production Compose
file and environment files only after this sequence passes on staging.

### First Transactional-Outbox Rollout

Perform the first outbox rollout on staging in a controlled maintenance window:

1. Before replacing the old backend, keep its worker running until the legacy
   `queue:monitor redis:search --max=1` reports `[0] OK` and inspect
   `queue:failed`.
2. Deploy the matching backend and deployment revisions so producers and the
   worker switch to `buyer-catalog-search` together. The new publisher exits
   safely while `outbox_messages` is not yet available.
3. Run `php artisan migrate --force`, then confirm `backend-scheduler` and
   `backend-worker` are running.
4. Run `php artisan outbox:status`, then execute
   `php artisan buyer-search:reindex` while the maintenance window remains open.
5. Wait for the outbox and queue to drain, resolve failures, inspect both
   container logs, and smoke-test authenticated buyer search.
6. Prove outage recovery by stopping Redis, updating a product and performing a
   checkout, confirming pending outbox messages, restoring Redis, and observing
   the messages become `published` after the worker updates Meilisearch.

Do not repeat the production rollout until the complete staging sequence has
passed. PostgreSQL remains authoritative while Meilisearch temporarily lags.

Stop the local validation stack:

```bash
./scripts/stop-staging.sh
```

Use `down -v` only when the local Docker PostgreSQL data can be deleted.

## Environment Files

Real env files are ignored by git. Copy the runtime examples before deploying:

```bash
cp env/staging/backend.env.example env/staging/backend.env
cp env/staging/frontend.env.example env/staging/frontend.env
```

Production uses the same pattern under `env/production`.

`images.env` is created by the first successful Deploy workflow. It records
the exact GHCR digests and source commits currently active on the VM.
`images.previous.env` records the preceding successful image set. Both files
are ignored by Git; the matching `.example` files exist for Compose validation.
Do not copy an image example into the real VM as an active release.

The three GHCR packages are private. The deploy workflow publishes them with
its `GITHUB_TOKEN` and passes the same short-lived token to `docker login` on
the VM through SSH stdin. The VM uses a temporary Docker credential directory
for the pull and removes it afterward; no long-lived GHCR token is needed in
`backend.env` or `frontend.env`. Check that the packages are linked to the
deploy repository before the first rollout if those package names already
exist under the GitHub account.

Before the first image rollout, check free space with `df -h /` and
`docker system df` on the target VM. Retain the previous deploy revision and
local application images until the new stack has passed its health checks.
Review unused build cache separately if image pulls need more space; the
deployment script does not prune Docker data automatically.

`backend.env` is the clean server environment for Laravel and PostgreSQL. It must contain only variables that are intentionally used by staging or production.

`frontend.env` remains on the target VM and supplies eight public `VITE_*`
values to its GitHub Actions build, plus the VM's public HTTP port settings.
The workflow reads only these build keys through SSH. Changing a `VITE_*`
value requires another manual Deploy run, even when the code commit is unchanged.

Set a real `APP_KEY` in each `backend.env` before starting staging or production. Do not leave it empty outside the committed `.example` files.

Set a distinct, high-entropy `MEILISEARCH_KEY` in each backend environment file.
It is shared only by internal Laravel containers and the internal Meilisearch
container; never put it in the frontend environment or commit a real key.

Keep `BUYER_PRODUCT_SEARCH_MAX_TOTAL_HITS=10000` aligned between the backend
revision and each deployment environment. Changing it has no effect until the
Laravel-owned index settings are applied through `buyer-search:reindex`.

Keep `BUYER_PRODUCT_SEARCH_PER_PAGE=50` aligned with the backend default. The
frontend sends this value explicitly, while the environment value controls
clients that omit `per_page`; changing it does not require a Meilisearch reindex.

Seller pagination separately uses `SELLER_PRODUCT_PER_PAGE=50` as its fallback
and `SELLER_PRODUCT_MAX_PER_PAGE=50` to validate requested batch sizes. The
frontend sends 50 explicitly, so keep the maximum at least 50 for that build.
The backend normalizes the configured maximum to at least 1 and the default
to 1 through the maximum. Requests above the maximum return HTTP 422.
These settings affect database batch sizes, not total catalog visibility;
they require no migration or Meilisearch reindex. Apply environment changes
through the normal backend rollout so Laravel loads the updated configuration.

Transactional outbox limits are exposed as `OUTBOX_*` values in each backend
environment example. Their defaults provide 20 publish attempts, 100 messages
per batch, 10 batches per minute, a five-minute stale-claim window, retry
backoff from 60 seconds to six hours, and seven-day published retention. Change
them only with corresponding backend capacity and recovery validation.

The public reverse proxy and Laravel trusted-proxy boundary use values from
`backend.env`:

```env
TRUSTED_EDGE_PROXY=192.168.1.202
TRUSTED_PROXIES=REMOTE_ADDR
```

`TRUSTED_EDGE_PROXY` must be the managed Cloudflare Tunnel connector source
address as observed by the environment's reverse proxy. Nginx accepts
`CF-Connecting-IP` only from that source and forwards it as one normalized
`X-Forwarded-For` client address. Laravel then trusts only the `backend-nginx`
peer directly connected to PHP-FPM through `REMOTE_ADDR`.

If the tunnel connector moves, update `TRUSTED_EDGE_PROXY` before deployment.
Do not replace it with an unrestricted LAN range: a trusted LAN client could
otherwise forge security audit IP data. Direct local or Tailscale health checks
without a forwarded header continue to use their actual connection address.

Clerk requires environment-specific frontend and backend credentials:

```env
# frontend.env - public values compiled into the Vite bundle
VITE_CLERK_PUBLISHABLE_KEY=<environment-publishable-key>
VITE_CLERK_SIGN_IN_URL=/login
VITE_CLERK_SIGN_UP_URL=/register

# backend.env - private runtime value
CLERK_SECRET_KEY=<environment-secret-key>
```

Use keys from the matching Clerk production instance for each environment.
Never place `CLERK_SECRET_KEY` in `frontend.env`, expose it through a `VITE_`
variable, or commit a real Clerk key to Git.

The Deploy workflow validates all eight `VITE_*` build values before building
the frontend image because Vite compiles them into static assets. Docker
Compose does not rebuild or configure the frontend bundle on the VM.
`CLERK_SECRET_KEY` is loaded only into the backend PHP container through
`backend.env`.

Geoapify uses separate browser and server-side keys:

```env
# frontend.env - keep this group below Clerk configuration
VITE_GEOAPIFY_API_KEY=<environment-browser-key>

# backend.env - private runtime value used for authoritative reverse geocoding
GEOAPIFY_API_KEY=<environment-server-key>
GEOAPIFY_API_URL=https://api.geoapify.com/v1/geocode
GEOAPIFY_TIMEOUT=8
```

Restrict browser keys to `https://staging.tokshop.click` and
`https://tokshop.click`; changing one requires rebuilding the frontend image.
The backend key is loaded at runtime and should use server/IP restrictions when
available. Do not reuse the local-development browser key or expose the backend
key through a `VITE_` variable.

## Private VM Administration With Tailscale

Tailscale is the private administration path from GitHub Actions to the staging
and production VMs. It runs on each VM host, not inside the frontend, backend,
PostgreSQL, or reverse proxy containers.

The Tailscale MagicDNS hostnames are SSH targets for deployment automation.
They are not the public application URLs. The exact hostnames and required
GitHub secrets are documented under GitHub Actions Manual Deployment.

## Public Domain Access

The public application domain for this deployment is `tokshop.click`. Users,
browser smoke tests, and public health checks should use these URLs instead of
the private Tailscale SSH hostnames.

Staging public URLs:

```text
Frontend:
  https://staging.tokshop.click

Backend:
  https://staging-api.tokshop.click
```

Production public URLs:

```text
Frontend:
  https://tokshop.click

Backend:
  https://api.tokshop.click
```

If the Proxmox home server is behind CGNAT, use Cloudflare Tunnel or another external reverse proxy path instead of direct router port forwarding. The tunnel can terminate public HTTPS and forward requests to the existing VM HTTP ports.

## Script Usage

The manual Deploy workflows invoke the deployment scripts on their target VMs
after publishing image digests. The scripts require three immutable image
references and the matching frontend/backend source commits as arguments.
They receive a short-lived GHCR token on stdin for private image pulls.

```text
VM staging:
  ./scripts/deploy-staging.sh FRONTEND_IMAGE BACKEND_IMAGE BACKEND_NGINX_IMAGE FRONTEND_SHA BACKEND_SHA

VM production:
  ./scripts/deploy-production.sh FRONTEND_IMAGE BACKEND_IMAGE BACKEND_NGINX_IMAGE FRONTEND_SHA BACKEND_SHA
```

The scripts pull the selected GHCR images, start the stack without building on
the VM, force recreate `backend-nginx` and `reverse-proxy` to refresh upstream
DNS, check both published HTTP ports, and require every Compose service to be
running. They promote `images.env` only after the checks pass. If a candidate
fails and a previous successful manifest
exists, they reactivate its image digests. The first image deployment has no
previous manifest; retain the previous deploy revision and local images until
that first deployment has passed. Database migrations are separate and are not
reverted by an image rollback.

The API server in both public reverse-proxy templates sets
`client_max_body_size 20m`, matching the backend Nginx layer. Keep both layers
aligned whenever application upload limits change; otherwise the outer proxy
can return `413 Request Entity Too Large` before Laravel receives the request.

If a `502 Bad Gateway` response appears after a deploy, force recreate the Nginx layer that owns the stale upstream reference:

```sh
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml up -d --force-recreate backend-nginx reverse-proxy
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env --env-file env/production/images.env -f compose/compose.production.yml up -d --force-recreate backend-nginx reverse-proxy
```

Use `backend-nginx` for API or PHP-FPM upstream issues and `reverse-proxy` for public frontend or public API routing issues.

`stop-staging.sh` stops the staging stack intentionally and requires an active
`env/staging/images.env`.

## VM Manual Deployment Runbook

The staging and production VMs use the same server-side folder structure:

```text
/opt/ecommerce/
  frontend/
  backend/
  deploy/
```

The application repositories may remain checked out for historical reference,
but deployment does not pull or build them on the VM. Run the appropriate
manual Deploy workflow to build and publish their selected branch commits.

## GitHub Actions Manual Deployment

The deploy repository also provides manual GitHub Actions workflows:

```text
Deploy Staging
Deploy Production
Sync Deploy Staging
Sync Deploy Production
Migrate Staging
Migrate Production
Seed Staging
Seed Production
```

The existing Deploy Staging and Deploy Production buttons check out the target
application branches on a GitHub-hosted runner. Through Tailscale and SSH they
read that VM's `frontend.env`, build and publish the three private GHCR images,
sync the deploy repository on the VM, and run the image-pulling deploy script.
The script prints Compose status and checks frontend and backend HTTP responses.

`Sync Deploy Staging` and `Sync Deploy Production` only pull `/opt/ecommerce/deploy` from `origin/main`, set the local branch upstream if needed, and print the latest synced commit. They do not pull frontend or backend, run Docker Compose, restart services, migrate, or seed.

`Migrate Staging` and `Migrate Production` do not pull code again. They run `php artisan migrate --force` against the backend container created by the latest successful deploy in the matching environment.

`Seed Staging` and `Seed Production` do not pull code again. They require a
`seeder_class` input, validate it against the running backend image, and run
`php artisan db:seed --class=... --force` in that container.

Operational branch targets:

```text
Deploy Staging:
  frontend origin/staging
  backend origin/staging
  deploy origin/main

Deploy Production:
  frontend origin/main
  backend origin/main
  deploy origin/main

Sync Deploy Staging:
  deploy origin/main only

Sync Deploy Production:
  deploy origin/main only
```

Database workflow targets:

```text
Migrate Staging:
  deploy existing staging containers only

Migrate Production:
  deploy existing production containers only

Seed Staging:
  deploy existing staging containers only

Seed Production:
  deploy existing production containers only
```

The workflows are intentionally manual at this stage. Merging to `staging` or `main` prepares the code for deployment, but the deployment starts only when a release owner opens the deploy repository Actions page and runs the matching workflow.

Manual workflow steps:

```text
1. Open GitHub Actions in the deploy repository.
2. Select the workflow that matches the release action.
3. Click Run workflow.
4. Fill the `seeder_class` input when running a seed workflow.
5. Wait until the workflow status is Success.
6. Confirm all three image digests were published and Compose status was printed.
7. Confirm both local VM health checks completed for deploy workflows.
8. Open the staging or production frontend and backend URLs from a browser when the release includes code changes.
```

Workflow selection rule:

```text
Sync Deploy ...:
  update only the deploy repository on the target VM

Deploy ...:
  build application branches in Actions, pull images on the VM, and apply runtime changes

Migrate ...:
  run Laravel migrations on the existing deployed backend container

Seed ...:
  run a specific Laravel seeder on the existing deployed backend container
```

## Workflow SOP

Use the workflows with the following daily operating rules.

`Sync Deploy Staging`

- Use this when only the `deploy` repository changed and staging should receive the latest deploy repository files without applying runtime changes.
- Do not use this to pull frontend or backend code.
- Do not use this to rebuild containers, restart services, run migrations, or run seeders.

`Sync Deploy Production`

- Use this when only the `deploy` repository changed and production should receive the latest deploy repository files without applying runtime changes.
- Do not use this to pull frontend or backend code.
- Do not use this to rebuild containers, restart services, run migrations, or run seeders.

`Deploy Staging`

- Use this when frontend, backend, or deploy changes must be applied to the staging runtime.
- This workflow builds from application `staging` branches and updates only the deploy checkout on the staging VM.

`Deploy Production`

- Use this when frontend, backend, or deploy changes must be applied to the production runtime.
- This workflow builds from application `main` branches and updates only the deploy checkout on the production VM.

`Migrate Staging`

- Use this after `Deploy Staging` when the release contains backend migration changes.
- Do not use this as a code sync workflow.

`Migrate Production`

- Use this after `Deploy Production` when the release contains backend migration changes.
- Do not use this as a code sync workflow.

`Seed Staging`

- Use this after deploy when staging needs a specific seeder to run.
- Always provide the required `seeder_class` input.
- Do not use a global `db:seed` workflow pattern for staging.

`Seed Production`

- Use this only when production needs a specific seeder that is known to be safe to run.
- Always provide the required `seeder_class` input.
- Do not use a global `db:seed` workflow pattern for production.

Quick decision guide:

- If only the `deploy` repository changed and no runtime apply is needed yet, use `Sync Deploy ...`.
- If frontend or backend changed and the application must be updated on the server, use `Deploy ...`.
- If backend migrations changed, use `Deploy ...` and then `Migrate ...`.
- If specific seed data is needed, use `Deploy ...` when code changed and then run `Seed ...` with the required `seeder_class`.

Safe release order:

- Staging: `Sync Deploy Staging` when needed, `Deploy Staging`, `Migrate Staging` when needed, `Seed Staging` when needed, then QA.
- Production: `Sync Deploy Production` when needed, `Deploy Production`, `Migrate Production` when needed, `Seed Production` when needed, then smoke test.

Expected workflow health checks:

```text
http://localhost:8080
http://localhost:8081
```

These health checks run from inside the target VM through SSH, so `localhost` means the staging or production VM, not the GitHub-hosted runner.

Required repository secrets:

```text
TS_AUTHKEY

STAGING_SSH_HOST
STAGING_SSH_USER
STAGING_SSH_PRIVATE_KEY

PRODUCTION_SSH_HOST
PRODUCTION_SSH_USER
PRODUCTION_SSH_PRIVATE_KEY
```

`TS_AUTHKEY` is a reusable ephemeral Tailscale auth key. It lets the temporary GitHub Actions runner join the private tailnet during deployment and disappear again after the workflow finishes.

Recommended values:

```text
STAGING_SSH_HOST=ecommerce-staging.tail5028dc.ts.net
STAGING_SSH_USER=jidan

PRODUCTION_SSH_HOST=ecommerce-production.tail5028dc.ts.net
PRODUCTION_SSH_USER=jidan
```

`STAGING_SSH_PRIVATE_KEY` and `PRODUCTION_SSH_PRIVATE_KEY` must contain private keys whose public keys are allowed in the matching VM user's `~/.ssh/authorized_keys`.

Use GitHub Environments for additional protection:

```text
staging
production
```

The production environment should require manual approval before the job can run.

### Deploy Staging

Run **Deploy Staging** from the deploy repository's GitHub Actions page. After
it succeeds, inspect the selected image digests on the staging VM:

```bash
ssh ecommerce-staging
cd /opt/ecommerce/deploy
cat env/staging/images.env
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml ps
```

Run staging migrations when backend migrations changed:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan migrate --force
```

Run staging seeders only when the seed data is intentionally needed:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml exec backend-php php artisan db:seed --class=PaymentListSeeder --force
```

### Deploy Production

After staging validation and production release approval, run **Deploy
Production** from the deploy repository's GitHub Actions page. Inspect the
production image digests after it succeeds:

```bash
ssh ecommerce-production
cd /opt/ecommerce/deploy
cat env/production/images.env
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env --env-file env/production/images.env -f compose/compose.production.yml ps
```

Run production migrations when backend migrations changed:

```bash
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env --env-file env/production/images.env -f compose/compose.production.yml exec backend-php php artisan migrate --force
```

Do not run production seeders on every deploy. Seed production only during initial setup or when the specific seeder is known to be idempotent and safe:

```bash
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env --env-file env/production/images.env -f compose/compose.production.yml exec backend-php php artisan db:seed --class=PaymentListSeeder --force
```

### Deployment Scope

Each manual Deploy run builds the current frontend and backend branch commits
for its environment, even if only one application changed. The VM pulls only
the resulting image digests; it no longer pulls application source code.
`Sync Deploy ...` still updates only deploy configuration without changing the
running containers.

## VM SSH Deploy Keys

Staging and production use separate GitHub Actions SSH keys for VM access. The
VM's deploy-repository read-only key remains necessary to sync `deploy/main`;
application repository deploy keys are no longer used by the Deploy workflows.
An existing production VM may still have the historical keys shown below.

```text
~/.ssh/ecommerce_production_frontend_deploy
~/.ssh/ecommerce_production_backend_deploy
~/.ssh/ecommerce_production_deploy_repo
```

The production SSH config maps those keys to separate GitHub host aliases:

```sshconfig
Host github-production-frontend
  HostName github.com
  User git
  IdentityFile ~/.ssh/ecommerce_production_frontend_deploy
  IdentitiesOnly yes

Host github-production-backend
  HostName github.com
  User git
  IdentityFile ~/.ssh/ecommerce_production_backend_deploy
  IdentitiesOnly yes

Host github-production-deploy
  HostName github.com
  User git
  IdentityFile ~/.ssh/ecommerce_production_deploy_repo
  IdentitiesOnly yes
```

Only the deploy-repository public key needs read access for this image-based
workflow. Historical application keys can be retired after the first staging
and production image deployments are verified. Do not enable write access for
VM deploy keys unless the VM must push commits.

## Staging Commands

```bash
cat env/staging/images.env
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env --env-file env/staging/images.env -f compose/compose.staging.yml logs -f
./scripts/stop-staging.sh
```

## Production Commands

```bash
cat env/production/images.env
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env --env-file env/production/images.env -f compose/compose.production.yml logs -f
```

Production requires real values for `APP_KEY`, `DB_PASSWORD`, and `POSTGRES_PASSWORD`. `DB_*` and `POSTGRES_*` database values must point to the same database.

## HTTPS

The Docker stack keeps HTTP internally so it can be validated safely through Tailscale and behind a public access layer. Public HTTPS should be terminated by Cloudflare Tunnel, a VPS reverse proxy, or Nginx-compatible certificates if the server has a real public IP and deliberate port forwarding.
