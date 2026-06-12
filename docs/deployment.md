# Ecommerce Deployment

This repository owns the deployment stack for the ecommerce frontend and backend.

The frontend and backend repositories build their own application images. This repository runs those images together with PostgreSQL and the Nginx reverse proxy.

Redis is intentionally not included in the first stack. It should be added later when the backend starts using Redis as the Laravel queue driver, cache driver, or realtime/websocket support service.

The Laravel scheduler is also intentionally not included in the first stack because the backend does not currently define active scheduled tasks. Add a separate scheduler service later when `app/Console/Kernel.php` contains real schedule entries.

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

Run migrations after the containers are up:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan migrate --force
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan db:seed --force
```

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

## Private VM Access With Tailscale

The first VM deployment can use Tailscale as the private access path for staging and personal production testing.

Tailscale runs on the VM host, not inside the application containers. Docker still runs the same reverse proxy, frontend, backend, and PostgreSQL services.

When using Tailscale, set the public-facing application URLs to the VM Tailscale IP or MagicDNS hostname after the VM joins the tailnet.

Example staging values:

```env
# env/staging/frontend.env
VITE_APP_BACKEND_BASE_URL=http://staging-vm:8081

# env/staging/backend.env
APP_URL=http://staging-vm:8081
FRONTEND_URL=http://staging-vm:8080
```

Use the full MagicDNS hostname or the Tailscale `100.x.x.x` IP if the short hostname does not resolve.

Tailscale access is private. Devices must be connected to the same tailnet before they can access the VM. Public domain and HTTPS setup can be added later when the application needs public access.

The first private production deployment follows the same port shape:

```text
Production frontend:
  http://production-vm:8080

Production backend:
  http://production-vm:8081
```

Replace `staging-vm` or `production-vm` with the real MagicDNS hostname or Tailscale IP on each VM.

Current private VM URLs:

```text
Staging frontend:
  http://ecommerce-staging.tail5028dc.ts.net:8080

Staging backend:
  http://ecommerce-staging.tail5028dc.ts.net:8081

Production frontend:
  http://ecommerce-production.tail5028dc.ts.net:8080

Production backend:
  http://ecommerce-production.tail5028dc.ts.net:8081
```

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

Both deploy scripts restart `reverse-proxy` after `docker compose up -d --build`. This refreshes the Nginx upstream container DNS after rebuilt frontend or backend containers are recreated and prevents stale upstream references from causing `502 Bad Gateway` responses after deploys.

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

### Deploy Staging

```bash
ssh ecommerce-staging

cd /opt/ecommerce/frontend
git pull origin main

cd /opt/ecommerce/backend
git pull origin main

cd /opt/ecommerce/deploy
git pull origin main

./scripts/deploy-staging.sh
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml ps
```

Run staging migrations when backend migrations changed:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan migrate --force
```

Run staging seeders only when the seed data is intentionally needed:

```bash
docker compose --env-file env/staging/backend.env --env-file env/staging/frontend.env -f compose/compose.staging.yml exec backend-php php artisan db:seed --force
```

### Deploy Production

```bash
ssh ecommerce-production

cd /opt/ecommerce/frontend
git pull origin main

cd /opt/ecommerce/backend
git pull origin main

cd /opt/ecommerce/deploy
git pull origin main

./scripts/deploy-production.sh
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env -f compose/compose.production.yml ps
```

Run production migrations when backend migrations changed:

```bash
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env -f compose/compose.production.yml exec backend-php php artisan migrate --force
```

Do not run production seeders on every deploy. Seed production only during initial setup or when the specific seeder is known to be idempotent and safe:

```bash
docker compose --env-file env/production/backend.env --env-file env/production/frontend.env -f compose/compose.production.yml exec backend-php php artisan db:seed --force
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

The first implementation uses HTTP so the Docker stack can be validated safely and accessed privately through Tailscale. HTTPS with Nginx-compatible certificates and Certbot should be added after the stack is stable on the VM and the application needs public domain access.
