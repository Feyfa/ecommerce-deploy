# ecommerce-deploy

Deployment stack for the ecommerce frontend and backend.

This repository owns Docker Compose, Nginx reverse proxy configuration, environment templates, deployment scripts, and deployment documentation.

Application image definitions stay in the application repositories:

```text
../frontend/docker/nginx/Dockerfile
../backend/docker/php/Dockerfile
```

Start with [docs/deployment.md](docs/deployment.md).
