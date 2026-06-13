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
