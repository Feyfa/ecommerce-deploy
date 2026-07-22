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

## GitHub Pull Requests

When the user asks to inspect, create, open, update, review, merge, or otherwise
operate a pull request, use the GitHub CLI (`gh`). Prefer the dedicated `gh pr`
commands and use `gh api` only when the required operation is not available
through a standard `gh` subcommand. Do not use connected GitHub integrations,
the Chrome extension, browser plugins, or browser automation for pull request
operations unless the user explicitly requests browser-based interaction.

Before performing a pull request operation, verify that `gh` is authenticated
with the correct GitHub account and has sufficient repository permissions.
Confirm the repository, pull request number, source branch, and target branch
before any operation that changes remote state. After a create, update, ready,
close, reopen, or merge operation, verify the resulting pull request state with
`gh pr view`.

## GitHub Actions

When the user asks to inspect, run, dispatch, monitor, rerun, or otherwise
operate a GitHub Actions workflow in this deployment repository, use the
GitHub CLI (`gh`). Do not use the Chrome extension, browser plugins, or browser
automation for GitHub Actions operations.

Before dispatching a workflow, verify that `gh` is authenticated with the
correct GitHub account and has sufficient repository and workflow permissions.
Use `gh workflow run` to dispatch manual workflows and use `gh run list`,
`gh run view`, or `gh run watch` to inspect and monitor their results. Report
the final workflow status and relevant failed step or health-check output when
the workflow does not succeed.
