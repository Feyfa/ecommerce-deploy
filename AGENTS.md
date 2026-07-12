# Deployment Agent Instructions

## Repository Scope

This repository contains deployment configuration and operational workflows.

## Project Documentation

Repository documentation is available in the `docs/` directory.

Before changing deployment configuration or automation:

1. Identify the environments, services, and deployment flows related to the task.
2. Search for and read the relevant documentation in `docs/`. Do not read every document unless the task requires it.
3. Inspect the related configuration, scripts, dependencies, and workflows to verify that the documentation still reflects the current repository state.
4. Follow the architecture, patterns, and configuration style already used in this repository.
5. Update the relevant documentation when a change affects environment variables, containers, servers, pipelines, provisioning, release flows, rollback procedures, or the developer workflow.

Review the relevant documentation before modifying containers, server configuration, environment variables, pipelines, provisioning, branching strategy, release flows, or deployment procedures.

## Related Repositories

The project may include separate frontend and backend repositories. If a task affects another repository and that repository is available in the workspace, inspect its code and documentation as well. Do not assume that related repositories are always available or located at a specific path.
