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

## Feature Branch Creation And Sync

New feature branches start from `main`.

```text
main
  -> feature/JD-TASK-1-account-security
```

The staging integration branch is created from the main feature branch:

```text
feature/JD-TASK-1-account-security
  -> feature/JD-TASK-1-account-security-staging
```

Normal sync before PR:

```text
feature/* syncs with main
feature/*-staging syncs with staging
```

Use merge for sync. Do not use rebase.

Production feature sync example:

```bash
git checkout main
git pull origin main

git checkout feature/JD-TASK-1-account-security
git merge main
```

Staging feature sync example:

```bash
git checkout staging
git pull origin staging

git checkout feature/JD-TASK-1-account-security-staging
git merge staging
```

If the PR still conflicts after normal sync, resolve the conflict in the feature branch based on the PR target.

For a production PR conflict:

```text
feature/* -> develop-main
```

merge the target branch into the feature branch:

```bash
git checkout develop-main
git pull origin develop-main

git checkout feature/JD-TASK-1-account-security
git merge develop-main
```

For a staging PR conflict:

```text
feature/*-staging -> develop-staging
```

merge the target branch into the feature staging branch:

```bash
git checkout develop-staging
git pull origin develop-staging

git checkout feature/JD-TASK-1-account-security-staging
git merge develop-staging
```

Resolve conflicts in the feature branch, commit, push, and let the PR update. Do not resolve conflicts directly in `main`, `staging`, `develop-main`, or `develop-staging`.

## Merge Policy

Use merge for this workflow. Do not use rebase as part of the shared release flow.

This keeps the workflow easier to understand and avoids rewriting history that has already been shared.

Do not merge:

```text
staging -> develop-main
develop-staging -> develop-main
staging -> main
develop-staging -> main
feature/*-staging -> develop-main
feature/*-staging -> main
```

## Branch-To-Deploy Flow

Staging flow for frontend and backend:

```text
feature/*-staging
  -> develop-staging
  -> staging
  -> CI/CD deploy to the staging VM
```

Production flow for frontend and backend:

```text
feature/*
  -> develop-main
  -> main
  -> CI/CD deploy to the production VM
```

`develop-staging` is the preparation and merge-check branch before `staging`. `staging` is the branch that triggers staging deployment.

`develop-main` is the preparation and merge-check branch before `main`. `main` is the branch that is used for production deployment.

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

CI runs on pull requests to validate code before it enters the target branch. CD runs after a deploy branch changes, such as `staging` or `main`.

Staging PR flow:

```text
feature/JD-TASK-1-account-security-staging
  -> PR to develop-staging
  -> CI runs
  -> PM review
  -> merge to develop-staging
  -> PR develop-staging to staging
  -> merge to staging
  -> CD deploys staging
```

Production PR flow:

```text
feature/JD-TASK-1-account-security
  -> PR to develop-main
  -> CI runs
  -> PM review
  -> merge to develop-main
  -> PR develop-main to main
  -> final review or approval
  -> merge to main
  -> manual production deploy
```

Staging deploy can be run manually from the deploy repository workflow after merge to `staging`. A future improvement can make this automatic after the process is stable.

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

At this initial stage, a normal push to `feature/**` or `hotfix/**` does not run CI. CI runs when a PR is created or updated, before the PM merges it.

Staging CD trigger:

```text
push or merge to staging
```

After `staging` changes, staging CD runs automatically. GitHub Actions enters the staging VM, pulls the required repositories, runs the staging deploy script, runs staging migrations, and performs health checks.

Production CD should not fully auto-deploy from a push to `main` at the initial stage.

Recommended initial production flow:

```text
develop-main -> main
```

The merge to `main` makes the code production-ready. Production deploy does not run until the PM or release owner starts the manual production workflow.

A more mature future option is to auto-trigger the production workflow when `main` changes, but stop at a GitHub Environment approval gate before the deploy job runs.

Initial manual deployment workflows live in the deploy repository:

```text
.github/workflows/deploy-staging.yml
.github/workflows/deploy-production.yml
```

The staging workflow pulls frontend and backend from `origin/staging`, pulls deploy from `origin/main`, runs `./scripts/deploy-staging.sh`, prints Docker Compose status, and checks `http://localhost:8080` and `http://localhost:8081` on the VM.

The production workflow pulls frontend and backend from `origin/main`, pulls deploy from `origin/main`, runs `./scripts/deploy-production.sh`, prints Docker Compose status, and checks `http://localhost:8080` and `http://localhost:8081` on the VM.

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
- `staging`: after merge, staging CD runs automatically.

Developers and PMs do not push directly to `main`, `staging`, `develop-main`, or `develop-staging`.

Developers push to:

```text
feature/**
feature/**-staging
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
auto deploy
auto migrate
always skip seeder
```

Production deploy:

```text
manual deploy workflow
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
CD staging auto deploys and migrates
manual seeder workflow for staging
QA test
```

Production flow when seed data is required:

```text
merge to main
manual production deploy
manual seeder workflow for production
smoke test
```

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
curl -f http://ecommerce-staging.tail5028dc.ts.net:8080
curl -f http://ecommerce-production.tail5028dc.ts.net:8080
```

Backend should expose a lightweight endpoint:

```text
GET /api/health
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
curl -f http://ecommerce-staging.tail5028dc.ts.net:8081/api/health
curl -f http://ecommerce-production.tail5028dc.ts.net:8081/api/health
```

## Naming Convention

Branch names should use the task key from Trello or another task manager.

Feature branch:

```text
feature/{initial}-{task-key}-{short-description}
```

Feature staging branch:

```text
feature/{initial}-{task-key}-{short-description}-staging
```

Hotfix branch:

```text
hotfix/{initial}-{task-key}-{short-description}
```

Hotfix staging branch:

```text
hotfix/{initial}-{task-key}-{short-description}-staging
```

Examples:

```text
feature/JD-TASK-1-account-security
feature/JD-TASK-1-account-security-staging
hotfix/JD-TASK-2-login-error
hotfix/JD-TASK-2-login-error-staging
```

Use a short description so branch names stay readable when the task list grows.

For full-stack features, use the same branch name in frontend and backend so the work is easy to coordinate.

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
TAILSCALE_AUTHKEY
SSH_HOST
SSH_USER
SSH_PRIVATE_KEY
```

Staging host:

```text
ecommerce-staging.tail5028dc.ts.net
```

Production host:

```text
ecommerce-production.tail5028dc.ts.net
```

`SSH_USER` is the Linux user used for deployment, such as `jidan` or preferably a dedicated `deploy` user.

`SSH_PRIVATE_KEY` is the CI/CD-specific private key used to log in to the VM. Add the matching public key to `~/.ssh/authorized_keys` on the target VM.

`TAILSCALE_AUTHKEY` allows the GitHub Actions runner to enter the tailnet and access the VM Tailscale hostnames.

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
