# Docker Staging And Production Deployment

This document defines the first Docker deployment direction for the ecommerce backend and its related frontend runtime.

The goal is to keep local development simple while making staging and production reproducible. Docker is used as a deployment foundation, not as a required local development workflow.

## Deployment Decision

The current deployment decision is:

```text
Local development:
Native development without Docker.

Staging:
Docker is required.

Production:
Docker is required.
```

Local development stays native because the current local setup already uses local HTTPS domains, local PostgreSQL, and editor tooling that works well without Docker. This avoids maintaining multiple local Docker variants for different operating systems, filesystem behavior, dependency mounting, and autocomplete needs.

Staging and production use Docker because those environments need repeatable runtime configuration, clear service boundaries, predictable deployment commands, persistent data volumes, and a safer path for future services such as websocket servers.

## Environment Topology

The first deployment topology uses one VM per environment:

```text
Staging:
1 VM for the full staging stack.

Production:
1 VM for the full production stack.
```

Each VM runs the required services through Docker Compose.

```text
staging VM
  reverse proxy
  frontend
  backend API
  PostgreSQL
  websocket server later

production VM
  reverse proxy
  frontend
  backend API
  PostgreSQL
  websocket server later
```

This keeps staging and production isolated while avoiding early VM fragmentation.

## Why One VM Per Environment For Now

The project should split infrastructure only when there is a real operational reason.

Running one VM per environment is the first deployment baseline because:

- Staging and production remain fully separated.
- Docker Compose can still keep services separated inside each VM.
- Deployment, backup, logging, and troubleshooting stay easier to understand.
- PostgreSQL can use a persistent Docker volume from the start.
- The setup can later evolve into separate data, queue worker, websocket, or app VMs without changing the application architecture.

Splitting every responsibility into its own VM too early would create extra firewall rules, deploy targets, OS maintenance, networking complexity, and troubleshooting overhead before the application actually needs it.

## Service Responsibilities

The deployment stack is expected to use these services.

### Reverse Proxy

The reverse proxy routes incoming traffic to the correct container. Containers
continue to serve HTTP behind the public HTTPS access layer, while Tailscale is
reserved for private VM administration by deployment automation.

Expected responsibilities:

- Serve internal HTTP traffic behind the public HTTPS access layer.
- Serve HTTPS for public staging and production domains when public access is added.
- Route frontend requests to the frontend container.
- Route API requests to the backend container.
- Route websocket requests to the websocket service when chat is implemented.

The selected reverse proxy for this deployment stack is Nginx.

The public API server allows request bodies up to `20m`. This limit must remain
aligned with the backend Nginx layer so valid multi-image product requests are
not rejected by the public proxy before reaching Laravel. Laravel still
enforces the actual file count, type, and per-file size rules.

The public Nginx configuration is rendered from an environment template. It
trusts forwarded client addresses only when the request comes from
`TRUSTED_EDGE_PROXY`, which is the managed Cloudflare Tunnel connector address.
After validating that source, Nginx resolves the single `CF-Connecting-IP`
value and replaces the outgoing chain with one normalized `X-Forwarded-For`
value. Direct LAN requests therefore keep their actual source address even when
they submit a forged Cloudflare or forwarded header.

Laravel receives requests through `backend-nginx` and uses
`TRUSTED_PROXIES=REMOTE_ADDR`. This trusts the immediate internal Nginx hop
without hard-coding a Docker container IP that can change after recreation.

### Frontend

The frontend service serves the built Vue application.

Staging and production should not use the Vite development server. The frontend image should build the Vue application and serve the generated static files.

Expected flow:

```text
npm ci
npm run build
serve dist
```

Frontend environment values that affect the bundle, such as the API URL, must be provided during the build or through a deliberate runtime configuration strategy.

### Backend API

The backend API service handles Laravel HTTP requests.

Expected responsibilities:

- Serve API endpoints.
- Read production or staging environment variables.
- Connect to PostgreSQL.
- Use persistent storage for files that must survive container restarts.

The backend image should install production dependencies and avoid development-only packages at runtime.

### PostgreSQL

PostgreSQL stores application data.

Expected responsibilities:

- Use a persistent Docker volume.
- Use separate database names, users, passwords, and volumes for staging and production.
- Never expose the database publicly unless there is a deliberate and secured operational reason.

Database backup and restore instructions should be added before production is considered ready for real use.

### Transactional Outbox, Redis Queue, And Meilisearch

Redis and Meilisearch are internal Docker services for the buyer product search
feature. Redis persists its append-only data in a named volume and provides the
Laravel queue connection. Meilisearch persists its rebuildable index in a
separate named volume and requires `MEILISEARCH_KEY` in the backend environment.

The backend environment sets `BUYER_PRODUCT_SEARCH_MAX_TOTAL_HITS=10000`.
Laravel applies that Meilisearch pagination boundary together with the final
`id:asc` ranking tie-breaker during reindex. The limit controls how deeply one
broad result set may be browsed; it does not cap PostgreSQL products. Measure
search latency and resource usage before raising it.

Business mutations commit their synchronization intent to PostgreSQL
`outbox_messages`. `backend-scheduler` publishes due messages to Redis, and
`backend-worker` applies them to Meilisearch. This lets `backend-php` depend only
on healthy PostgreSQL: Redis or Meilisearch downtime must not prevent product,
company, Clerk, or checkout mutations from committing.

`backend-worker` uses the same backend image as the API, waits for PostgreSQL,
Redis, and Meilisearch, and processes only the `buyer-catalog-search` queue
with explicit retry, backoff, and timeout settings. Neither Redis nor
Meilisearch publishes a host port; use `docker compose logs backend-worker`
and `docker compose ps` for operational inspection.

The backend environment sets `REDIS_QUEUE_RETRY_AFTER=180`, which must remain
longer than the longest application job timeout. The current longest search job
timeout is 120 seconds. Review both values together whenever queue job timeouts
change so Redis cannot deliver the same job to another worker too early.

After a first deployment or a recovery, run `php artisan buyer-search:reindex`
inside `backend-php`. The command applies Laravel-owned index settings and
queues the complete PostgreSQL catalog. Meilisearch snapshots or backups are
helpful for recovery speed, but PostgreSQL plus this command remains the source
of recovery truth.

The command clears the derived index before dispatching jobs, so the buyer
catalog can be temporarily empty. A successful command exit only proves that
jobs were dispatched. Before ending the maintenance or recovery window:

1. Confirm `backend-worker`, `backend-scheduler`, Redis, and Meilisearch are healthy in
   `docker compose ps`.
2. Run `php artisan outbox:status` in `backend-php` and resolve overdue pending
   or terminal failed publisher messages.
3. Run
   `php artisan queue:monitor redis:buyer-catalog-search --max=1` in
   `backend-php` until it reports `[0] OK`.
4. Run `php artisan queue:failed` and resolve every search synchronization
   failure before retrying it.
5. Inspect the configured Meilisearch index statistics and confirm eligible
   product documents exist.
6. Perform an authenticated buyer-catalog smoke test, including a keyword or
   filter and a response with `page`, `per_page`, and `has_more`.

Concrete staging Compose commands are maintained in
[Deployment](deployment.md#local-stack-validation). Apply the equivalent
production commands only after staging verification succeeds.

### Laravel Scheduler

Each environment runs exactly one `backend-scheduler` service using the backend
image and this command:

```text
php artisan schedule:work
```

It depends only on healthy PostgreSQL, mounts the shared backend log volume,
uses `restart: unless-stopped`, and receives a graceful stop period. It runs the
outbox publisher every minute with overlap protection and prunes published
outbox history daily at 02:00 WIB. Laravel derives this schedule from the
application timezone `Asia/Jakarta`, independently of the host or container
operating-system timezone.

Docker is the process monitor for both scheduler and worker. Do not install
Supervisor inside the containers and do not add a VM crontab for Laravel
Scheduler. Keep these as separate one-process containers so their health,
restart, logs, and scaling remain independent.

### Websocket Server

The websocket service is planned for the future seller-buyer chat feature.

Expected direction:

```text
Laravel Reverb or another documented Laravel-compatible websocket runtime.
```

The websocket service should run separately from the backend API service because websocket connections are long-running and have different scaling and deployment behavior.

## Public Domain Plan

One VM can serve multiple domains or subdomains when the application is ready for public DNS and HTTPS. DNS records can point multiple hostnames to the same VM IP address, and the reverse proxy decides which container receives each request.

The first public domain target uses `tokshop.click`. When the home server is behind CGNAT, public HTTPS traffic should be terminated by Cloudflare Tunnel or another external reverse proxy path. The Docker stack can keep serving HTTP on ports `8080` and `8081` behind that public access layer.

Staging domains:

```text
staging.tokshop.click
staging-api.tokshop.click
staging-ws.tokshop.click
```

Production domains:

```text
tokshop.click
api.tokshop.click
ws.tokshop.click
```

The websocket domain is reserved for the future chat feature. It does not need to be active until the websocket service exists.

Subdomains are preferred over path-based routing because they keep frontend, API, and websocket routing clearer for CORS, auth callbacks, and future realtime configuration.

## Private VM Administration With Tailscale

Because the staging and production VMs may run from a home Proxmox environment,
GitHub Actions can use Tailscale for private SSH administration without exposing
the SSH service through public DNS or router port forwarding.

Tailscale runs on the VM host. It does not need to run inside the frontend, backend, PostgreSQL, or reverse proxy containers.

The Docker stack can keep using HTTP internally while access stays private inside the tailnet.

Example staging URLs:

```text
Frontend: http://staging-vm:8080
Backend:  http://staging-vm:8081
```

Example private production URLs:

```text
Frontend: http://production-vm:8080
Backend:  http://production-vm:8081
```

The deploy env files must continue to use the public TokShop application URLs:

```env
VITE_APP_BACKEND_BASE_URL=https://staging-api.tokshop.click
APP_URL=https://staging-api.tokshop.click
FRONTEND_URL=https://staging.tokshop.click
```

Users open the application through the public `tokshop.click` hostnames. The
private Tailscale connection remains limited to GitHub Actions and VM
administration.

## Environment File Strategy

Local native `.env` files should not be reused for staging or production.

Staging and production need their own environment files:

```text
deploy/env/staging/backend.env
deploy/env/staging/frontend.env
deploy/env/production/backend.env
deploy/env/production/frontend.env
```

Only examples should be committed:

```text
deploy/env/staging/backend.env.example
deploy/env/staging/frontend.env.example
deploy/env/production/backend.env.example
deploy/env/production/frontend.env.example
```

Real environment files must contain secrets and must stay outside git.

Set a real `APP_KEY` in each `backend.env` before starting the stack. Do not leave `APP_KEY` empty on staging or production.

Important backend values include:

```text
APP_ENV
APP_DEBUG
APP_URL
FRONTEND_URL
TRUSTED_EDGE_PROXY
TRUSTED_PROXIES
DB_CONNECTION
DB_HOST
DB_PORT
DB_DATABASE
DB_USERNAME
DB_PASSWORD
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
CACHE_DRIVER
QUEUE_CONNECTION
SESSION_DRIVER
CLERK_SECRET_KEY
CLERK_FEATURE_PASSKEY
CLERK_FEATURE_TOTP
GEOAPIFY_API_KEY
GEOAPIFY_API_URL
GEOAPIFY_TIMEOUT
```

`TRUSTED_EDGE_PROXY` accepts one IP address or CIDR owned by the deployment and
must match the source address observed by the public reverse proxy for the
Cloudflare Tunnel connector. `TRUSTED_PROXIES` should remain `REMOTE_ADDR` in
the current two-layer Nginx architecture. Do not add a whole LAN subnet unless
every host in that subnet is intentionally allowed to supply client-IP headers.

Important frontend values include:

```text
VITE_APP_BACKEND_BASE_URL
VITE_SYMLINK_FOLDER
VITE_CLERK_PUBLISHABLE_KEY
VITE_CLERK_SIGN_IN_URL
VITE_CLERK_SIGN_UP_URL
VITE_FEATURE_CLERK_PASSKEY
VITE_FEATURE_CLERK_TOTP
VITE_GEOAPIFY_API_KEY
FRONTEND_HTTP_PORT
BACKEND_HTTP_PORT
```

Passkey and TOTP capability flags are intentionally disabled in the committed
staging and production examples. The frontend values are Docker build
arguments, so changing them requires rebuilding the frontend image. The backend
values are runtime configuration and keep the Security summary aligned with the
frontend capability state.

`VITE_GEOAPIFY_API_KEY` is a public browser key compiled after the Clerk group
in each frontend env file. Use a different origin-restricted key for staging
and production; never commit the real values.

`GEOAPIFY_API_KEY` is a separate backend runtime key used to reverse-geocode
and validate every new or updated pinpoint before it is saved. Keep it out of
frontend env files and apply server/IP restrictions when available. If provider
verification is unavailable, address writes fail closed instead of accepting
unverified text.

Clerk settings must be separated between staging and production. The frontend
publishable key and auth route values are passed into the Vite build as Docker
build arguments because they are compiled into the static bundle. The Clerk
secret key is read only by the backend container at runtime and must never be
exposed through a `VITE_` variable or stored in the frontend image.

Real Clerk keys belong only in the ignored environment files on the matching
VM. Staging and production must use keys from their respective Clerk production
instances.

Websocket and production payment settings must also remain separated when they
are added later.

## Docker Compose Strategy

Docker Compose should be split by environment:

```text
compose.staging.yml
compose.production.yml
```

The files can share the same service shape, but they should not share secrets, volume names, database names, or public domains.

Expected staging differences:

- `APP_ENV=staging`
- staging domains
- staging database credentials
- staging Docker volumes
- staging mail/payment credentials or sandbox providers
- debug settings appropriate for staging only

Expected production differences:

- `APP_ENV=production`
- production domains
- production database credentials
- production Docker volumes
- production mail/payment credentials
- `APP_DEBUG=false`
- stricter restart and operational rules

## Deployment Flow

The intended workflow is:

```text
1. Develop locally using the native local setup.
2. Commit changes in the correct repository.
3. Push changes.
4. Build Docker images for staging.
5. Deploy images to the staging VM with Docker Compose.
6. Test staging.
7. Create or select a production release.
8. Deploy production with Docker Compose.
```

Production should deploy from a deliberate release or selected commit. It should not automatically receive every feature that happens to be present in staging.

This avoids the problem where an unfinished feature remains in staging and accidentally ships to production.

## Production Safety Rules

Production deployment must follow these rules:

- Do not commit real secrets.
- Do not reuse staging credentials in production.
- Do not run production with `APP_DEBUG=true`.
- Do not use temporary database volumes for production data.
- Do not expose PostgreSQL publicly by default.
- Do not deploy unfinished staging-only features to production.
- Run migrations deliberately and verify whether the migration is safe for current production data.
- Prepare database backup and restore commands before treating production as real.

Production should pull or use known images/releases instead of relying on undocumented manual edits on the server.

## Future Scaling Path

The first topology can be expanded when there is a real need.

Possible future steps:

- Move PostgreSQL to a dedicated data VM when database resource usage, data safety, or backup needs become more serious.
- Scale Redis, scheduler publishing, and queue workers only when observed backlog or throughput requires it.
- Move the websocket server to a dedicated VM when realtime connection count grows or websocket deploys need to be isolated from API deploys.
- Serve frontend assets through CDN or static hosting when static traffic grows or frontend releases need a separate delivery path.
- Add multiple backend API instances behind a load balancer when HTTP traffic requires horizontal scaling.

The project should evolve toward these steps gradually. Infrastructure should be split because of bottlenecks, operational risk, or scaling needs, not just because a larger topology looks more advanced.
