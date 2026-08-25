# Ecommerce Deployment

This repository owns the deployment stack for the ecommerce frontend and backend.

The frontend and backend repositories build their own application images. This
repository runs those images together with PostgreSQL, Redis, Meilisearch, the
buyer-search queue worker, Laravel Scheduler, and the Nginx reverse proxy.

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

The Compose files in this repository build from the sibling `frontend` and `backend` folders.

## Local Stack Validation

Local development stays native without Docker. Docker is used locally only to validate the deployment stack.

From the `deploy` folder:

```bash
cp env/staging/backend.env.example env/staging/backend.env
cp env/staging/frontend.env.example env/staging/frontend.env
./scripts/deploy-staging.sh
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml ps
```

Local validation URLs:

```text
Frontend: http://localhost:8080
Backend:  http://localhost:8081
```

Run migrations and any required specific seeders after the containers are up:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan migrate --force
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan db:seed --class=PaymentListSeeder --force
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan outbox:status
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan buyer-search:reindex
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
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml ps backend-worker backend-scheduler redis meilisearch
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan outbox:status
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan queue:monitor redis:buyer-catalog-search --max=1
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan queue:failed
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan tinker --execute="dump(app(\\Meilisearch\\Client::class)->index(config('buyer_product_search.index'))->stats());"
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml logs --tail=100 backend-worker
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml logs --tail=100 backend-scheduler
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

Real env files are ignored by git. Copy the examples before deploying:

```bash
cp env/staging/backend.env.example env/staging/backend.env
cp env/staging/frontend.env.example env/staging/frontend.env
```

Production uses the same pattern under `env/production`.

`backend.env` is the clean server environment for Laravel and PostgreSQL. It must contain only variables that are intentionally used by staging or production.

`frontend.env` is the clean server environment for the frontend build and public HTTP port settings.

Set a real `APP_KEY` in each `backend.env` before starting staging or production. Do not leave it empty outside the committed `.example` files.

Set a distinct, high-entropy `MEILISEARCH_KEY` in each backend environment file.
It is shared only by internal Laravel containers and the internal Meilisearch
container; never put it in the frontend environment or commit a real key.

Keep `BUYER_PRODUCT_SEARCH_MAX_TOTAL_HITS=10000` aligned between the backend
revision and each deployment environment. Changing it has no effect until the
Laravel-owned index settings are applied through `buyer-search:reindex`.

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

Docker Compose passes the public Clerk values to the frontend build because
Vite compiles them into static assets. The Compose configuration fails early
when `VITE_CLERK_PUBLISHABLE_KEY` is missing, preventing a deployment with an
unusable authentication bundle. `CLERK_SECRET_KEY` is loaded only into the
backend PHP container through `backend.env`.

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

The deployment scripts are shared between local stack validation and real VM deployment.

```text
VM staging:
  ./scripts/deploy-staging.sh

VM production:
  ./scripts/deploy-production.sh

Local stack validation:
  ./scripts/deploy-staging.sh
  ./scripts/stop-staging.sh
```

`deploy-staging.sh` starts or updates the staging stack. It can be used locally to validate the Docker stack and on the staging VM to deploy the real staging environment.

`deploy-production.sh` starts or updates the production stack. There is no production stop script by default because stopping production should be a deliberate manual operation.

Both deploy scripts force recreate `backend-nginx` and `reverse-proxy` after `docker compose up -d --build`. This refreshes both Nginx upstream layers after rebuilt frontend or backend containers are recreated and prevents stale upstream references from causing `502 Bad Gateway` responses after deploys.

The API server in both public reverse-proxy templates sets
`client_max_body_size 20m`, matching the backend Nginx layer. Keep both layers
aligned whenever application upload limits change; otherwise the outer proxy
can return `413 Request Entity Too Large` before Laravel receives the request.

If a `502 Bad Gateway` response appears after a manual rebuild, force recreate the Nginx layer that owns the stale upstream reference:

```sh
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml up -d --force-recreate backend-nginx reverse-proxy
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env -f compose/compose.production.yml up -d --force-recreate backend-nginx reverse-proxy
```

Use `backend-nginx` for API or PHP-FPM upstream issues and `reverse-proxy` for public frontend or public API routing issues.

`stop-staging.sh` stops the staging stack and is mainly intended for local stack validation or an intentional staging stop.

## VM Manual Deployment Runbook

The staging and production VMs use the same server-side folder structure:

```text
/opt/ecommerce/
  frontend/
  backend/
  deploy/
```

The Compose files in `/opt/ecommerce/deploy` build from the sibling `/opt/ecommerce/frontend` and `/opt/ecommerce/backend` repositories. Pushing to GitHub does not update a VM by itself; pull the changed repositories on the VM before running the deploy script.

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

These workflows replace the manual SSH runbook with a GitHub "Run workflow" button. They connect the GitHub-hosted runner to the private tailnet with Tailscale, SSH into the target VM, pull the correct application branches, pull the deploy repository, run the deployment script, print Docker Compose status, and run local health checks for frontend and backend.

`Sync Deploy Staging` and `Sync Deploy Production` only pull `/opt/ecommerce/deploy` from `origin/main`, set the local branch upstream if needed, and print the latest synced commit. They do not pull frontend or backend, run Docker Compose, restart services, migrate, or seed.

`Migrate Staging` and `Migrate Production` do not pull code again. They run `php artisan migrate --force` against the backend container created by the latest successful deploy in the matching environment.

`Seed Staging` and `Seed Production` do not pull code again. They require a `seeder_class` input, validate that the requested class exists in `backend/database/seeders`, and run `php artisan db:seed --class=... --force` against the backend container created by the latest successful deploy.

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
6. Confirm the Docker Compose status step completed for deploy workflows.
7. Confirm both local VM health checks completed for deploy workflows.
8. Open the staging or production frontend and backend URLs from a browser when the release includes code changes.
```

Workflow selection rule:

```text
Sync Deploy ...:
  update only the deploy repository on the target VM

Deploy ...:
  update frontend, backend, and deploy repositories and apply runtime changes

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
- This workflow updates frontend, backend, and deploy repositories on the staging VM and then applies the deployment.

`Deploy Production`

- Use this when frontend, backend, or deploy changes must be applied to the production runtime.
- This workflow updates frontend, backend, and deploy repositories on the production VM and then applies the deployment.

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

```bash
ssh ecommerce-staging

cd /opt/ecommerce/frontend
git fetch origin
git checkout staging
git pull --ff-only origin staging

cd /opt/ecommerce/backend
git fetch origin
git checkout staging
git pull --ff-only origin staging

cd /opt/ecommerce/deploy
git pull --ff-only origin main

./scripts/deploy-staging.sh
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml ps
```

Run staging migrations when backend migrations changed:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan migrate --force
```

Run staging seeders only when the seed data is intentionally needed:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan db:seed --class=PaymentListSeeder --force
```

### Deploy Production

```bash
ssh ecommerce-production

cd /opt/ecommerce/frontend
git fetch origin
git checkout main
git pull --ff-only origin main

cd /opt/ecommerce/backend
git fetch origin
git checkout main
git pull --ff-only origin main

cd /opt/ecommerce/deploy
git pull --ff-only origin main

./scripts/deploy-production.sh
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env -f compose/compose.production.yml ps
```

Run production migrations when backend migrations changed:

```bash
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env -f compose/compose.production.yml exec backend-php php artisan migrate --force
```

Do not run production seeders on every deploy. Seed production only during initial setup or when the specific seeder is known to be idempotent and safe:

```bash
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env -f compose/compose.production.yml exec backend-php php artisan db:seed --class=PaymentListSeeder --force
```

### Deployment Scope

If only the frontend changed, pull `/opt/ecommerce/frontend` and then run the relevant deploy script from `/opt/ecommerce/deploy`.

If only the backend changed, pull `/opt/ecommerce/backend` and then run the relevant deploy script from `/opt/ecommerce/deploy`.

If deployment configuration, scripts, Nginx config, or env examples changed, pull `/opt/ecommerce/deploy` before running the relevant deploy script.

## VM SSH Deploy Keys

Staging and production use separate GitHub deploy keys. Production follows one read-only deploy key per repository:

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

Each public key should be registered as a read-only deploy key on its matching GitHub repository. Do not enable write access for VM deploy keys unless the VM must push commits.

## Staging Commands

```bash
./scripts/deploy-staging.sh
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml logs -f
./scripts/stop-staging.sh
```

## Production Commands

```bash
./scripts/deploy-production.sh
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env -f compose/compose.production.yml logs -f
```

Production requires real values for `APP_KEY`, `DB_PASSWORD`, and `POSTGRES_PASSWORD`. `DB_*` and `POSTGRES_*` database values must point to the same database.

## HTTPS

The Docker stack keeps HTTP internally so it can be validated safely through Tailscale and behind a public access layer. Public HTTPS should be terminated by Cloudflare Tunnel, a VPS reverse proxy, or Nginx-compatible certificates if the server has a real public IP and deliberate port forwarding.
