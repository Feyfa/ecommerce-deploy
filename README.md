# ecommerce-deploy

Deployment stack for the ecommerce frontend and backend.

This repository owns Docker Compose, Nginx reverse proxy configuration, environment templates, deployment scripts, and deployment documentation.

Application image definitions stay in the application repositories:

```text
../frontend/docker/nginx/Dockerfile
../backend/docker/php/Dockerfile
```

## Documentation

- [Deployment Runbook](docs/deployment.md)
  Contains staging and production server commands, environment file notes, VM paths, deploy scripts, and operational checks.

- [Branching Strategy](docs/branching-strategy.md)
  Defines the shared frontend and backend branch roles, staging integration flow, production flow, hotfix flow, and conflict rules.

- [Docker Staging And Production Deployment](docs/docker-staging-production.md)
  Explains the Docker deployment architecture, VM topology, service responsibilities, environment strategy, and future scaling path.

- [Release Flow](docs/release-flow.md)
  Defines branch-to-deploy flow, pull request flow, CI/CD triggers, branch protection, migration and seeder policy, multi-repo coordination, health checks, rollback, naming convention, environment secrets, and CI test level.

## Branch Model

The application repositories use separate `main`, `staging`, and Jira task
branches. This deployment repository has one long-lived `main` branch and uses
short-lived Jira task branches for reviewed changes. It has no persistent
`staging` or `*-staging` branch.

Create deployment changes from the latest `deploy/main` in a branch such as
`task/jd-tok-38`, then push the branch and open a pull request to `main`.
Deploy CI and Release Branch Policy must pass before merge. Merging to `main`
only synchronizes repository files; it does not automatically deploy or restart
an environment. Use the matching manual GitHub Actions workflow when runtime
changes are required.

## Trusted Client IP Configuration

Set `TRUSTED_EDGE_PROXY` to the Cloudflare Tunnel connector source address and
keep `TRUSTED_PROXIES=REMOTE_ADDR`. The reverse proxy validates and normalizes
the client IP before Laravel reads it; trusting arbitrary forwarded headers in
application code is not supported.
