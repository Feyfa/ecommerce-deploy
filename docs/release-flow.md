# Release Flow

This document defines the branch, pull request, CI/CD, migration, seeder, rollback, and release coordination rules for the ecommerce frontend, backend, and deploy repositories.

The goal is to keep staging fast enough for validation while keeping production deliberate and controlled.

## Repository Branch Roles

The frontend and backend repositories use four long-lived branches:

```text
main
staging
develop-main
develop-staging
```

The deploy repository uses only:

```text
main
```

The deploy repository is the single source of truth for Docker Compose files, Nginx reverse proxy files, deploy scripts, environment examples, and deployment documentation.

## Jira Task Branch Creation And Sync

New Jira task branches start from `main`.

```text
main
  -> bug/jd-tok-7
```

Before implementation starts, check whether the task branch already exists
locally or on `origin`. Do not create a task branch from a stale local `main`.

If the task branch does not exist, first confirm that the working tree is safe,
update `main` with a fast-forward-only pull, and then create the task branch
locally:

```bash
git status

git switch main
git pull --ff-only origin main

git switch -c bug/jd-tok-7
```

Do not push merely because the local task branch has been created. Push after
the intended implementation has been committed and validated, or when the
branch is being prepared for the agreed staging or production flow.

If the task branch already exists locally, switch to it and inspect its status:

```bash
git switch bug/jd-tok-7
git status
```

If the task branch exists only on `origin`, fetch the latest remote references
and create a local tracking branch instead of creating another branch for the
same task:

```bash
git fetch origin
git switch --track origin/bug/jd-tok-7
git status
```

The staging integration branch is created from the main Jira task branch:

```text
bug/jd-tok-7
  -> bug/jd-tok-7-staging
```

Complete, validate, and commit the intended implementation in the main Jira task
branch before preparing its staging integration branch. If the staging branch
does not exist yet, update both long-lived source branches first:

```bash
git switch main
git pull --ff-only origin main

git switch staging
git pull --ff-only origin staging

git switch bug/jd-tok-7
git merge main

git switch -c bug/jd-tok-7-staging
git merge staging
```

Resolve and validate production-source conflicts in the main Jira task branch.
Resolve staging conflicts in the staging integration branch. Push both branches
only after their merges and relevant validation succeed.

If the staging integration branch already exists, do not recreate it. Refresh
the long-lived branches, merge `main` into the main Jira task branch, then carry
the task changes and the latest `staging` into the existing staging branch:

```bash
git switch main
git pull --ff-only origin main

git switch staging
git pull --ff-only origin staging

git switch bug/jd-tok-7
git merge main

git switch bug/jd-tok-7-staging
git merge bug/jd-tok-7
git merge staging
```

This task-branch preparation flow applies to the frontend and backend
repositories. It does not apply to the deploy repository, which uses only
`main` as described in the Deploy Repository Flow section.

Normal sync before PR:

```text
main Jira task branch syncs with main
matching Jira task staging branch syncs with staging
```

Use merge for sync. Do not use rebase.

Production task sync example:

```bash
git checkout main
git pull origin main

git checkout bug/jd-tok-7
git merge main
```

Staging task sync example:

```bash
git checkout staging
git pull origin staging

git checkout bug/jd-tok-7-staging
git merge staging
```

If the PR still conflicts after normal sync, resolve the conflict in the Jira task branch based on the PR target.

For a production PR conflict:

```text
main Jira task branch -> develop-main
```

merge the target branch into the main Jira task branch:

```bash
git checkout develop-main
git pull origin develop-main

git checkout bug/jd-tok-7
git merge develop-main
```

For a staging PR conflict:

```text
Jira task staging branch -> develop-staging
```

merge the target branch into the Jira task staging branch:

```bash
git checkout develop-staging
git pull origin develop-staging

git checkout bug/jd-tok-7-staging
git merge develop-staging
```

Resolve conflicts in the Jira task branch, commit, push, and let the PR update. Do not resolve conflicts directly in `main`, `staging`, `develop-main`, or `develop-staging`.

## Merge Policy

Use merge for this workflow. Do not use rebase as part of the shared release flow.

This keeps the workflow easier to understand and avoids rewriting history that has already been shared.

Do not merge:

```text
staging -> develop-main
develop-staging -> develop-main
staging -> main
develop-staging -> main
Jira task staging branch -> develop-main
Jira task staging branch -> main
```

## Branch-To-Deploy Flow

Staging flow for frontend and backend:

```text
complete code, tests, environment examples, and affected docs in the main Jira task branch
  -> merge latest main into the main Jira task branch
  -> resolve conflicts and validate the main Jira task branch
  -> commit and push the main Jira task branch
  -> merge the main Jira task branch into its task staging branch
  -> merge latest staging into the task staging branch
  -> Jira task staging branch
  -> develop-staging
  -> staging
  -> manual Deploy Staging workflow from the deploy repository
```

Production flow for frontend and backend:

```text
complete code, tests, environment examples, and affected docs in the main Jira task branch
  -> merge latest main into the main Jira task branch
  -> resolve conflicts and validate the main Jira task branch
  -> commit and push the main Jira task branch
  -> main Jira task branch
  -> develop-main
  -> main
  -> manual Deploy Production workflow from the deploy repository
```

Do not open a staging PR directly from a main Jira task branch. The staging
integration branch is mandatory even when GitHub reports that the task branch can merge cleanly
into `develop-staging`. Its purpose is not only conflict resolution; it also
keeps staging synchronization out of the production candidate branch.

Before creating or refreshing a Jira task staging branch, review whether the
latest task behavior requires documentation changes. Make required documentation
changes in the main Jira task branch, then merge the updated task branch into
its task staging branch. If no documentation is affected, do not create an empty or
unrelated documentation change merely for the release process.

`develop-staging` is the preparation and merge-check branch before `staging`. `staging` is the branch that the staging deployment workflow pulls from.

`develop-main` is the preparation and merge-check branch before `main`. `main` is the branch that the production deployment workflow pulls from.

After a staging release, `develop-staging` and `staging` should be at the same commit.

After a production release, `develop-main` and `main` should be at the same commit.

## Deploy Repository Flow

The deploy repository uses only `main`.

If the deploy repository changes only staging-specific files, pull `deploy/main` on staging and run the staging deploy only when needed. Production can pull for synchronization, but does not need a production deploy.

If the deploy repository changes only production-specific files, pull `deploy/main` on production and run the production deploy only when needed. Staging can pull for synchronization, but does not need a staging deploy.

If the deploy repository changes shared deployment behavior, validate it on staging first. Continue to production only after staging is safe.

## Pull Request Flow

A pull request is the controlled request to merge one branch into another branch in GitHub.

Pull requests are used for:

- code review;
- discussion;
- file diff review;
- CI checks;
- conflict checks;
- approval before merge.

CI runs on pull requests to validate code before it enters the target branch. Deployment is started manually from the deploy repository after the target branch is ready.

Staging PR flow:

```text
bug/jd-tok-7-staging
  -> PR to develop-staging
  -> CI runs
  -> PM review
  -> merge to develop-staging
  -> PR develop-staging to staging
  -> merge to staging
  -> run Deploy Staging manually from the deploy repository
```

Production PR flow:

```text
bug/jd-tok-7
  -> PR to develop-main
  -> CI runs
  -> PM review
  -> merge to develop-main
  -> PR develop-main to main
  -> final review or approval
  -> merge to main
  -> manual production deploy
```

Staging deploy is run manually from the deploy repository workflow after merge to `staging`. A future improvement can make this automatic after the process is stable.

Production deploy should use manual control or approval because it can affect real users, production data, payments, downtime, migrations, and seeders.

Merging to `main` means the code is production-ready. The actual production deploy can still wait for the correct approval and release window.

## CI And CD Triggers

Initial CI should run only on pull requests to protected branches:

```text
develop-staging
staging
develop-main
main
```

At this initial stage, a normal push to `feature/**`, `story/**`, `bug/**`,
`task/**`, or `hotfix/**` does not run CI. CI runs when a PR is created or
updated, before the PM merges it.

Staging deploy trigger:

```text
manual Deploy Staging workflow
```

After `staging` changes, a release owner starts the manual Deploy Staging workflow from the deploy repository. GitHub Actions enters the staging VM, pulls the required repositories, runs the staging deploy script, prints Docker Compose status, and performs health checks.

Production deploy should not fully auto-deploy from a push to `main` at the initial stage.

Recommended initial production flow:

```text
develop-main -> main
```

The merge to `main` makes the code production-ready. Production deploy does not run until the PM or release owner starts the manual Deploy Production workflow.

A more mature future option is to auto-trigger the production workflow when `main` changes, but stop at a GitHub Environment approval gate before the deploy job runs.

Manual deployment workflows live in the deploy repository:

```text
.github/workflows/deploy-staging.yml
.github/workflows/deploy-production.yml
.github/workflows/sync-deploy-staging.yml
.github/workflows/sync-deploy-production.yml
.github/workflows/migrate-staging.yml
.github/workflows/migrate-production.yml
.github/workflows/seed-staging.yml
.github/workflows/seed-production.yml
```

The staging workflow pulls frontend and backend from `origin/staging`, pulls deploy from `origin/main`, runs `./scripts/deploy-staging.sh`, prints Docker Compose status, and checks `http://localhost:8080` and `http://localhost:8081` on the VM.

The production workflow pulls frontend and backend from `origin/main`, pulls deploy from `origin/main`, runs `./scripts/deploy-production.sh`, prints Docker Compose status, and checks `http://localhost:8080` and `http://localhost:8081` on the VM.

The manual deploy sync workflows connect to the correct VM, pull only the `deploy` repository from `origin/main`, and print the latest synced commit without rebuilding containers or applying runtime changes.

The manual migration workflows connect to the correct VM and run `php artisan migrate --force` against the already-running backend container from the latest deploy.

The manual seeder workflows connect to the correct VM, require a `seeder_class` input, validate that the requested seeder class exists in `backend/database/seeders`, and then run `php artisan db:seed --class=... --force`.

## Branch Protection Rules

Branch protection decides whether a branch can receive a push or merge when conditions such as CI success and review have not been met.

CI trigger decides when CI runs. Branch protection decides whether the CI result is required before merge.

Without branch protection, a PR can still be merged even when CI fails. With branch protection, GitHub blocks the merge until required CI checks pass.

Frontend and backend protected branches:

```text
main
staging
develop-main
develop-staging
```

Rules for all protected frontend and backend branches:

- no direct push;
- changes must enter through PR;
- CI must pass;
- review or approval is required.

Additional behavior:

- `main`: production deploy remains manual or approval-controlled.
- `staging`: after merge, staging deploy is run manually from the deploy repository.

Developers and PMs do not push directly to `main`, `staging`, `develop-main`, or `develop-staging`.

Developers push to:

```text
feature/**
feature/**-staging
story/**
story/**-staging
bug/**
bug/**-staging
task/**
task/**-staging
hotfix/**
hotfix/**-staging
```

Then they open PRs to the correct target branch.

The deploy repository has only `main`. `deploy/main` should also be protected:

- no direct push;
- PR required;
- review required;
- documentation or CI checks can be added later.

## Migration And Seeder Policy

Migration and seeder behavior must be treated differently.

Migrations are tracked by Laravel in the `migrations` table. Seeders do not have automatic tracking.

Staging deploy:

```text
manual Deploy Staging workflow
migration runs only when selected or approved
always skip seeder
```

Production deploy:

```text
manual Deploy Production workflow
migration runs only when selected or approved
always skip seeder
```

Seeders for staging and production always run through a separate manual workflow. Seeders never run automatically as part of deploy.

Manual seeder workflow inputs:

```text
environment: staging or production
seeder_class: PaymentListSeeder
```

Run only a specific seeder class:

```bash
php artisan db:seed --class=PaymentListSeeder --force
```

Do not run this general command in staging or production:

```bash
php artisan db:seed --force
```

If seed data changes, deploy the code first, then run the manual seeder workflow for the required environment.

Staging flow when seed data is required:

```text
merge to staging
manual Deploy Staging workflow
manual Migrate Staging workflow when required
manual Seed Staging workflow
QA test
```

Production flow when seed data is required:

```text
merge to main
manual Deploy Production workflow
manual Migrate Production workflow when required
manual Seed Production workflow
smoke test
```

If only the deploy repository itself changed and the change does not need an immediate runtime apply, use the matching `Sync Deploy` workflow to update `/opt/ecommerce/deploy` on the target VM without touching frontend, backend, or running containers.

## Multi-Repo Coordination

The project is split into separate repositories:

```text
frontend
backend
deploy
```

Because of this, releases must be coordinated when one feature touches more than one repository.

If only frontend changes, deploy frontend only. Backend does not need to deploy.

If only backend changes, deploy backend only. Frontend does not need to deploy.

If deploy changes, apply it according to the files that changed, as described in the deploy repository flow.

If a full-stack feature touches frontend and backend, the deployment does not need to happen in the exact same second. It must happen in a controlled release window.

Full-stack deployment order:

```text
backend first
run migration if needed
health check backend
frontend after backend is safe
health check frontend
```

Backend goes first because frontend usually depends on backend endpoints or response fields. If frontend deploys first while the backend is not ready, frontend can fail.

Backend changes should be backward-compatible so the old frontend remains safe while the new frontend has not deployed yet.

If a backend change is breaking, split it into smaller releases:

```text
add compatibility first
update frontend
remove old behavior after everything is safe
```

## Health Checks

After deploy, CI/CD must run health checks to ensure frontend and backend can be reached.

Initial frontend health check:

```bash
curl -f https://staging.tokshop.click
curl -f https://tokshop.click
```

Backend exposes a lightweight endpoint at the API root:

```text
GET /
```

Initial backend response:

```json
{"status":"ok"}
```

A more informative response can include service and timestamp:

```json
{"status":"ok","service":"backend","timestamp":"2026-06-14T10:00:00+07:00"}
```

At the initial stage, the endpoint only needs to confirm that Laravel is alive.

Later, it can include a database check:

```json
{"status":"ok","database":"ok"}
```

Keep health checks lightweight because CI/CD and monitoring can call them often.

Backend health check examples:

```bash
curl -f https://staging-api.tokshop.click/
curl -f https://api.tokshop.click/
```

## Naming Convention

Branch names must use the Jira work type, the initials of the person doing the
work, and the Jira issue key. Use lowercase for the entire branch name, while
the issue remains uppercase in Jira itself.

Main Jira task branch:

```text
{work-type}/{initial}-{jira-key}
```

Jira task staging branch:

```text
{work-type}/{initial}-{jira-key}-staging
```

Supported Jira work type prefixes:

```text
feature
story
bug
task
```

Examples:

```text
feature/jd-tok-9
story/ar-tok-8
bug/jd-tok-7
bug/jd-tok-7-staging
task/jd-tok-17
task/jd-tok-17-staging
```

The initials identify the person responsible for the implementation. For
example, `jd` represents Jidan. The Jira issue key is normalized to lowercase,
so Jira issue `TOK-7` becomes `tok-7` in the branch name. Do not append a short
description because Jira remains the source of truth for the task title and
details.

`hotfix/*` remains reserved for urgent production fixes and uses the same
initials and Jira key structure:

```text
hotfix/{initial}-{jira-key}
hotfix/{initial}-{jira-key}-staging
hotfix/jd-tok-10
```

For full-stack tasks, use the same branch name in frontend and backend so the
work is easy to coordinate.

## Environment Secrets And VM Access

The CD access direction is:

```text
GitHub Actions -> VM
```

GitHub Actions enters the VM to run deploy commands.

The existing deploy key direction on the VM is:

```text
VM -> GitHub
```

The VM uses that key to pull repositories from GitHub.

Because the staging and production VMs are private Tailscale hosts, the GitHub Actions runner must temporarily join the tailnet before it can SSH to the VMs.

Chosen access model:

```text
GitHub Actions joins Tailscale temporarily
GitHub Actions SSHs to ecommerce-staging.tail5028dc.ts.net or ecommerce-production.tail5028dc.ts.net
GitHub Actions runs deploy commands
```

Secrets are stored in GitHub, not in repository code.

GitHub location:

```text
Repository -> Settings -> Secrets and variables -> Actions
```

Use GitHub Environments:

```text
staging
production
```

Each environment stores:

```text
TS_AUTHKEY

STAGING_SSH_HOST
STAGING_SSH_USER
STAGING_SSH_PRIVATE_KEY

PRODUCTION_SSH_HOST
PRODUCTION_SSH_USER
PRODUCTION_SSH_PRIVATE_KEY
```

Staging host:

```text
ecommerce-staging.tail5028dc.ts.net
```

Production host:

```text
ecommerce-production.tail5028dc.ts.net
```

`STAGING_SSH_USER` and `PRODUCTION_SSH_USER` are the Linux users used for deployment, such as `jidan` or preferably dedicated `deploy` users.

`STAGING_SSH_PRIVATE_KEY` and `PRODUCTION_SSH_PRIVATE_KEY` are the CI/CD-specific private keys used to log in to the VMs. Add each matching public key to `~/.ssh/authorized_keys` on the target VM.

`TS_AUTHKEY` allows the GitHub Actions runner to enter the tailnet and access the VM Tailscale hostnames.

The production GitHub Environment should require reviewer approval before the production deploy job runs.

Do not use a personal SSH private key if possible. Prefer a dedicated CI/CD key. Staging and production should use different keys when possible.

## Rollback Policy

The primary rollback method is `git revert`, not `git reset` or force push.

`git revert` creates a new commit that cancels a problematic commit while keeping history intact.

Do not use these commands on shared or protected branches:

```bash
git reset --hard
git push --force
```

Rollback follows the normal workflow:

```text
create rollback or hotfix branch
run git revert
push branch
open PR
CI runs
review or approval
merge
CD redeploys
```

There is no direct injection into GitHub and no direct change to protected branches without PR.

For production rollback, create a hotfix or rollback branch from `main` or `develop-main`, depending on the emergency.

For staging rollback, create a hotfix or rollback branch from `staging` or `develop-staging`, depending on the situation.

Revert commits must still pass CI because revert can conflict, fail builds, fail tests, or be incompatible with migrations or data that already ran.

Code rollback does not always rollback the database. Risky migrations must have a rollback plan before production deploy.

Current baseline:

```text
revert commit
merge through PR
deploy again
```

## CI Test Level

CI test level defines which automatic checks must run before a PR can be merged.

Initial frontend CI:

```bash
npm ci
npm run build
```

Frontend CI verifies that dependencies can be installed cleanly, the code can build, imports are not broken, and syntax or build errors are caught.

Frontend unit tests and lint are not required at the initial stage if the project is not ready for them. They can be added later.

Initial backend CI:

```text
composer install
PostgreSQL 16 service
testing environment
testing APP_KEY
testing migrations
php artisan test
```

Backend CI uses temporary PostgreSQL in GitHub Actions to stay close to staging and production behavior and catch PostgreSQL migration or query errors.

Backend CI commands:

```bash
composer install --no-interaction --prefer-dist --optimize-autoloader
cp .env.example .env.testing
php artisan key:generate --env=testing
php artisan migrate --env=testing --force
php artisan test
```

The CI PostgreSQL service is temporary and only exists during the GitHub Actions job. It is not the local, staging, or production database.

Branch protection can later require `frontend-ci` and `backend-ci` to pass before PRs can be merged.
