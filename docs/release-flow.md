# Release Flow

This document defines the branch, pull request, CI/CD, migration, seeder, rollback, and release coordination rules for the ecommerce frontend, backend, and deploy repositories.

The goal is to keep staging fast enough for validation while keeping production deliberate and controlled.

## Repository Branch Roles

The frontend and backend repositories use two long-lived branches:

```text
main
staging
```

The deploy repository has only one long-lived branch:

```text
main
```

Short-lived deploy Jira task branches merge into `main` through pull requests.
The deploy repository is the single source of truth for Docker Compose files,
Nginx reverse proxy files, deploy scripts, environment examples, and deployment
documentation.

## Evidence-First Release Preflight

Before answering or acting on a project-specific release request:

- Read the relevant workspace and repository `AGENTS.md` files and the release
  documentation before choosing a workflow.
- Inspect the current implementation, configuration, repository status, active
  branch, local branches, and remote references that are relevant to the task.
- Treat the current repository state as the primary evidence. Separate verified
  facts from unresolved assumptions and do not use an unverified assumption as
  the basis for a branch, merge, commit, push, or deployment operation.
- If the user interrupts, corrects, or asks for the instructions or situation
  to be reread, repeat this preflight against the current state before
  continuing.
- Execute every command below as a separate terminal invocation. Do not paste
  multiple Git commands joined by `&&`, `;`, command substitution, or a
  multiline shell block. Wait for each result before running the next command.

Before implementation starts in the frontend or backend repositories, confirm
that the Jira task identity and branch name are clear. The work type,
responsible initials, and Jira issue key are required to derive the branch name.
If any of them is missing or ambiguous, stop before editing code or creating a
branch, explain the expected branch format to the user, and request the missing
Jira information. Do not work directly on `main` or `staging`.

The main Jira task branch must be created or checked out before implementation
starts. Verify the active branch before the first code change and after every
branch switch. If the active branch is `main`, `staging`, or unrelated to the
Jira task, stop implementation until the correct task branch is active. The
matching `*-staging` branch may only be prepared after the main task branch
exists and contains the intended source changes.

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

Complete, validate, commit, and push the intended implementation in the main
Jira task branch, then wait for task-branch CI to pass. Only after that remote
checkpoint succeeds should staging preparation refresh the long-lived source
branches.

The local `staging` branch is the source of truth for task staging preparation.
`origin/staging` is only a local remote-tracking reference and is not a
substitute for updating the local branch. Never create or reset a task staging
branch directly from `origin/staging`.

A new task staging branch must be created while the completed main Jira task
branch is checked out. Immediately before `git switch -c <task>-staging`, run
`git branch --show-current` and require the output to exactly match `<task>`.
Never create the branch while `main`, `staging`, or another branch is checked
out.

Application integration merges must use refreshed local branch names. Update
local `main` and `staging` with `git pull --ff-only`, then merge `main`,
`staging`, or the local Jira task branch. Do not run:

```bash
git merge origin/main
git merge origin/staging
git merge origin/<task>
```

This restriction does not prohibit `git fetch`, `git pull --ff-only`, or
`git push`; it prevents remote-tracking references from becoming direct merge
sources for application integration.

Do not use these shortcuts for the normal staging flow:

```bash
git switch -c bug/jd-tok-7-staging origin/staging
git switch -C bug/jd-tok-7-staging origin/staging
git checkout -b bug/jd-tok-7-staging origin/staging
git checkout -B bug/jd-tok-7-staging origin/staging
```

```bash
git push -u origin bug/jd-tok-7

# Wait for task branch CI to pass.

git switch main
git pull --ff-only origin main

git switch staging
git pull --ff-only origin staging

git switch bug/jd-tok-7
git rev-parse HEAD
git merge --no-edit main
git rev-parse HEAD

# If HEAD changed, validate, push, and wait for task branch CI again.
# If HEAD did not change, do not push again.

git branch --show-current

git switch -c bug/jd-tok-7-staging
git merge --no-ff --no-edit staging

git push -u origin bug/jd-tok-7-staging

# Wait for task staging branch CI before merging its pull request.
```

Record the main task branch commit before and after merging `main`. If the merge
changes HEAD, resolve conflicts, validate, push the new commit, and wait for its
CI result. If HEAD remains unchanged, the earlier successful CI result still
applies and no second push is needed. Resolve and validate staging conflicts in
the staging integration branch, push that branch, and wait for its CI before
the staging pull request may be merged.

If the staging integration branch already exists, do not recreate it. Refresh
the long-lived branches, merge `main` into the main Jira task branch, then carry
the task changes and the latest `staging` into the existing staging branch:

```bash
git push -u origin bug/jd-tok-7

# Wait for task branch CI to pass.

git switch main
git pull --ff-only origin main

git switch staging
git pull --ff-only origin staging

git switch bug/jd-tok-7
git rev-parse HEAD
git merge --no-edit main
git rev-parse HEAD

# If HEAD changed, validate, push, and wait for task branch CI again.
# If HEAD did not change, do not push again.

git switch bug/jd-tok-7-staging
git merge --no-edit bug/jd-tok-7
git merge --no-ff --no-edit staging

git push -u origin bug/jd-tok-7-staging

# Wait for task staging branch CI before merging its pull request.
```

Validate and push the refreshed main task branch only if merging `main` changed
its HEAD, and wait for that new CI result before switching to the existing task
staging branch. Validate and push the refreshed task staging branch, then wait
for its CI before the staging pull request may be merged.

This task-staging preparation flow applies to the frontend and backend
repositories. The deploy repository uses Jira task branches without matching
`*-staging` branches, as described in the Deploy Repository Flow section.

Normal sync before PR:

```text
main Jira task branch syncs with main
matching Jira task staging branch syncs with staging
```

Use merge for sync. Do not use rebase.

Production task sync example:

```bash
git switch main
git pull --ff-only origin main

git switch bug/jd-tok-7
git merge --no-edit main
```

Staging task sync example:

```bash
git switch staging
git pull --ff-only origin staging

git switch bug/jd-tok-7-staging
git merge --no-ff --no-edit staging
```

If the PR still conflicts after normal sync, resolve the conflict in the Jira task branch based on the PR target.

For a production PR conflict:

```text
main Jira task branch -> main
```

merge the target branch into the main Jira task branch:

```bash
git switch main
git pull --ff-only origin main

git switch bug/jd-tok-7
git merge --no-edit main
```

For a staging PR conflict:

```text
Jira task staging branch -> staging
```

merge the target branch into the Jira task staging branch:

```bash
git switch staging
git pull --ff-only origin staging

git switch bug/jd-tok-7-staging
git merge --no-ff --no-edit staging
```

Resolve conflicts in the Jira task branch, commit, push, and let the PR update. Do not resolve conflicts directly in `main` or `staging`.

## Merge Policy

Use merge for this workflow. Do not use rebase as part of the shared release flow.

This keeps the workflow easier to understand and avoids rewriting history that has already been shared.

When a local integration merge must create a merge commit, use
`git merge --no-ff --no-edit <local-branch>`. The `--no-edit` option keeps Git's
generated merge message, such as `Merge branch 'staging' into bug/jd-tok-7-staging`,
without requiring a custom message. For ordinary synchronization that may
fast-forward, use `git merge --no-edit <local-branch>` without `--no-ff`. Do not
pass `-m` to `git merge` in this workflow.

Do not merge:

```text
staging -> main
Jira task staging branch -> main
```

## Branch-To-Deploy Flow

Staging flow for frontend and backend:

```text
complete code, tests, environment examples, and affected docs in the main Jira task branch
  -> commit and push the main Jira task branch
  -> wait for main Jira task branch push CI
  -> merge latest main into the main Jira task branch
  -> if HEAD changed, validate, push, and wait for CI again
  -> merge the main Jira task branch into its task staging branch
  -> merge latest staging into the task staging branch
  -> validate and push the Jira task staging branch
  -> wait for Jira task staging branch push CI
  -> Jira task staging branch
  -> staging
  -> manual Deploy Staging workflow from the deploy repository
```

Production flow for frontend and backend:

```text
complete code, tests, environment examples, and affected docs in the main Jira task branch
  -> commit and push the main Jira task branch
  -> wait for main Jira task branch push CI
  -> merge latest main into the main Jira task branch
  -> if HEAD changed, validate, push, and wait for CI again
  -> main Jira task branch
  -> main
  -> manual Deploy Production workflow from the deploy repository
```

Do not open a staging PR directly from a main Jira task branch. The staging
integration branch is mandatory even when GitHub reports that the task branch can merge cleanly
into `staging`. Its purpose is not only conflict resolution; it also
keeps staging synchronization out of the production candidate branch.

Before creating or refreshing a Jira task staging branch, review whether the
latest task behavior requires documentation changes. Make required documentation
changes in the main Jira task branch, then merge the updated task branch into
its task staging branch. If no documentation is affected, do not create an empty or
unrelated documentation change merely for the release process.

`staging` is the branch that the staging deployment workflow pulls from.

`main` is the branch that the production deployment workflow pulls from.

## Task Content And QA Evidence Boundary

Every production-bound task must have the same reviewed task changes deployed
to staging and production, including all tracked code, tests, Markdown,
instructions, and configuration. After staging verification, any additional
tracked change must go through staging integration and deployment before
production. There is no documentation-only exception.

Staging may contain other tasks awaiting production. Compare content within the
released task's scope and attribute remaining differences to those pending
tasks, including overlapping changes in the same file. Preserve pending work;
never reset staging, merge staging into main, or ship unrelated unfinished work
to force whole-branch equality. Merge SHAs may differ while task content agrees.
An unexplained missing or changed task contribution blocks release completion.

Application `backend/docs/qa/` and `frontend/docs/qa/` contain local QA only.
Complete scenarios, expected results, actual local tests/review, and local
coverage limitations with the implementation before commit. Do not put
post-commit CI, PR, staging/production smoke, deployment, runtime health, source
revisions, or Jira status checklists/results into these tracked documents.
Keep that evidence in Jira, PRs, and GitHub Actions. These release checks still
run; do not create a new documentation commit merely to update their status.
Do not rewrite unrelated historical QA documents as part of a release.

Verify both the branch content and the source revisions activated on the VMs.
Deploy final image-packaged content to both environments, including Markdown.
The deploy repository remains main-only; verify the same released deploy
revision on both VMs. Record proof and pending-task exceptions outside Git QA.

## Deploy Repository Flow

The deploy repository has only one long-lived branch, `main`. Use short-lived
Jira task branches for deployment changes, but do not create a deploy `staging`
branch or deploy `*-staging` branches.

Before implementation, confirm the Jira work type, responsible initials, issue
key, and expected branch name. Create the task branch from the latest `main`:

```bash
git switch main
git pull --ff-only origin main

git switch -c task/jd-tok-38
```

After editing and local validation, commit and push the task branch, then wait
for its push-triggered Deploy CI to pass before opening or continuing a pull
request to `main`. Deploy CI runs again for the pull request, and both that check
and Release Branch Policy must pass before the pull request is merged. Required
reviewer approval remains zero so a maintainer can complete safe solo work,
while unresolved review conversations still block the merge.

The deploy branch policy accepts `feature/**`, `story/**`, `bug/**`, `task/**`,
and `hotfix/**` source branches. It rejects `main`, `staging`, and any
`*-staging` source branch.

Merging into `deploy/main` synchronizes repository files only. It does not
rebuild containers, restart services, run migrations, run seeders, or otherwise
apply a runtime change. Use the appropriate manual workflow when the change
must reach staging or production.

If the deploy repository changes only staging-specific files, pull `deploy/main` on staging and run the staging deploy only when needed. Production can pull for synchronization, but does not need a production deploy.

If the deploy repository changes only production-specific files, pull `deploy/main` on production and run the production deploy only when needed. Staging can pull for synchronization, but does not need a staging deploy.

If the deploy repository changes shared deployment behavior, validate it on staging first. Continue to production only after staging is safe.

## Commit And Staging Scope

Stage only the files that have been reviewed for the current task. Do not use `git add -A`, `git add .`, `git add --all`, or broad globs because those commands can include unrelated changes without making the approval scope obvious.

Use explicit file paths instead:

```bash
git add -- AGENTS.md README.md docs/release-flow.md
```

After staging, inspect the exact commit scope before creating the commit:

```bash
git diff --cached --name-status
git diff --cached --stat
git diff --cached
```

The same explicit-file rule applies to frontend, backend, and deploy repositories. It keeps the approval review aligned with the files that will be committed or pushed.

### Commit Message Execution

Every commit must read its message from standard input with `git commit -F -`
and a quoted `'EOF'` heredoc delimiter. This applies to subject-only commits,
multi-line commit messages, and amendments that replace a commit message. Do
not use `git commit -m` or multiple `-m` arguments.

```bash
git commit -F - <<'EOF'
docs(workflow): describe the verified change
EOF
```

Use real newlines inside the heredoc. After every commit, run
`git log -1 --format=full` as a separate command and verify the stored message,
including its line breaks, validation claims, and trailers.

## Pull Request Flow

### Pull Request Titles

Use the actual Jira key at the start of every task PR title:

- Application to staging: `[TOK-X-staging] <description>`.
- Application to main: `[TOK-X] <description>`.
- Deploy task to main: `[TOK-X] <description>`.

Use the same concise description for paired application PRs. Do not add `PR-`,
change branch conventions, or change commit-message rules. Push-triggered
Actions may still display commit subjects rather than a PR title.

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
  -> PR to staging
  -> CI runs
  -> PM review
  -> merge to staging
  -> run Deploy Staging manually from the deploy repository
```

Production PR flow:

```text
bug/jd-tok-7
  -> PR to main
  -> CI runs
  -> PM review
  -> merge to main
  -> manual production deploy
```

Staging deploy is run manually from the deploy repository workflow after merge to `staging`. A future improvement can make this automatic after the process is stable.

Production deploy should use manual control or approval because it can affect real users, production data, payments, downtime, migrations, and seeders.

Merging to `main` means the code is production-ready. The actual production deploy can still wait for the correct approval and release window.

## Efficient CI And Deployment Monitoring

Use the GitHub CLI for Actions and the connected GitHub integration for PRs,
following the repository tool-selection rules. Monitoring does not authorize
merge, retry, dispatch, production promotion, or a permission bypass.

Record the repository, run ID, workflow/event, source SHA, and attempt when
discovering a run. For a queued or running run, start one watcher and keep its
execution session instead of repeatedly asking the model to sleep and inspect
the same status. The CLI performs the polling; the model handles decisions and
final verification. This reduces redundant interaction, not required evidence,
and does not guarantee a particular usage saving.

Replace the placeholders below with the actual repository, run ID, and Jira
key. Keep the temporary log outside the repository and unique to the task/run:

```bash
gh run watch RUN_ID \
    --repo OWNER/REPO \
    --exit-status \
    --compact \
    --interval 30 \
    > /private/tmp/tok-X-watch-RUN_ID.log 2>&1
```

Resume that command session with waits of at most 60 seconds so user updates
remain timely. Do not restart the watcher at each tool yield, run a competing
status loop, or feed every refresh into model context. Read a small relevant
tail only when needed; provide concise updates from known state without
inventing progress. Routine waiting does not require a subagent.

An interrupted watcher, timeout, unsupported CLI/authentication method, unclear
result, failure indication, or user status request can justify an additional
status read. Explain the reason, check the run once, and resume one watcher
when possible. If watching is unavailable, use bounded compact CLI polling;
do not silently change tools or restart the deployment. A monitor error or
timeout is not proof that the remote workflow failed or was cancelled.

After the watcher ends, confirm terminal status, conclusion, source SHA, and
attempt with a compact read before continuing:

```bash
gh run view RUN_ID --repo OWNER/REPO \
    --json status,conclusion,headSha,attempt
```

On failure, begin with `gh run view RUN_ID --repo OWNER/REPO --log-failed` and
inspect the relevant error and rollback/health evidence. On success, read only
the log sections needed for active source revisions, immutable images, and
service/HTTP health. Download large logs to temporary files when appropriate;
do not dump full build logs into the conversation by default.

Reuse evidence only for unchanged content and the same verification context.
Required push CI and PR CI remain separate gates; a changed commit or target,
new attempt, stale evidence, or concrete regression risk can require new checks.
Keep task-content parity, actual deployed revisions, runtime health, local
synchronization and final branch checks, Jira evidence, and production approval
intact. Record post-commit results in Jira/PR/Actions, not local QA Markdown.

## CI And CD Triggers

Application CI runs when a pull request targets a protected branch:

```text
staging
main
```

Application CI also runs when `feature/**`, `story/**`, `bug/**`, `task/**`, or
`hotfix/**` is pushed. These patterns include matching `*-staging` branches.
Push CI provides the task-branch checkpoint, while pull request CI validates the
same checks against the current protected target before merge. Release Branch
Policy remains pull-request-only because it validates the PR source-to-target
mapping.

Deploy CI uses the same five push patterns for deploy Jira task branches and
runs again when a pull request targets deploy `main`. Deploy has no task staging
branch. Its Release Branch Policy remains pull-request-only because that check
requires pull request source and target branch context.

Staging deploy trigger:

```text
manual Deploy Staging workflow
```

After `staging` changes, a release owner starts the manual Deploy Staging workflow from the deploy repository. GitHub Actions enters the staging VM, pulls the required repositories, runs the staging deploy script, prints Docker Compose status, and performs health checks.

Production deploy should not fully auto-deploy from a push to `main` at the initial stage.

Recommended initial production flow:

```text
main Jira task branch -> main
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

The staging workflow checks out frontend and backend `staging` on the
GitHub-hosted runner, reads the staging VM's frontend build configuration over
SSH, publishes private GHCR images, and pulls their exact digests on the VM.
The production workflow does the same with application `main` and the
production VM's configuration. Both workflows sync deploy `main` on the target
VM, print Docker Compose status, and check the frontend and backend HTTP ports.
The VM no longer builds application images or pulls application source branches.

The manual deploy sync workflows connect to the correct VM, pull only the `deploy` repository from `origin/main`, and print the latest synced commit without rebuilding containers or applying runtime changes.

The manual migration workflows connect to the correct VM and run `php artisan migrate --force` against the already-running backend container from the latest deploy.

The manual seeder workflows connect to the correct VM, require a `seeder_class` input, validate that the requested seeder class exists in `backend/database/seeders`, and then run `php artisan db:seed --class=... --force`.

## Post-Deployment Local Sync And Jira Completion

After every required staging or production deployment workflow and its health
checks succeed, refresh the local long-lived branches before reporting that
deployment stage complete. First confirm that each working tree is safe to
switch. Preserve local changes and task branches; never force a switch, reset
a branch, or delete work to reach an end state.

In each affected frontend and backend repository, run every command as a
separate terminal invocation:

```bash
git switch staging
git pull --ff-only origin staging
git switch main
git pull --ff-only origin main
```

Refresh both application branches after either staging or production; choose
the final local checkout separately based on the task's stage:

| Task stage | Final local application branch |
| --- | --- |
| Staging succeeded; task still needs QA, fixes, or production promotion | The participating repository's main Jira task branch, not `*-staging` |
| Production deployment and all required validation succeeded | `main` |
| Task completed its declared scope, including a declared staging-only scope | `main` |
| Repository has no branch for the task | `main`; do not create a task branch merely for checkout |

For an active task after staging, switch back to its main task branch after
the pulls. For example, if that branch is `task/jd-tok-17`, run:

```bash
git switch task/jd-tok-17
```

Use the actual task branch, not the example name. Keep QA fixes on that branch
and integrate them through its matching `*-staging` branch as usual. Merging a
production PR into `main` does not establish production completion.

The deploy repository has no `staging` branch. Refresh it separately:

```bash
git switch main
git pull --ff-only origin main
```

If deploy has a branch for the still-active task after staging, return to that
deploy task branch too. Otherwise, or after production validation or declared
task completion, leave deploy on `main`. Deploy still has no `staging` or
`*-staging` branch.

These rules govern local working copies. Deployment sources remain application
`staging` for staging, application `main` for production, and deploy `main` for
workflows and VMs; the local checkout does not select the deployed revision.

After the final checkout, verify every affected repository separately:

```bash
git branch --show-current
git status --short --branch
```

If a required pull or branch check fails, report the failure and do not claim
that post-deployment synchronization completed. A production-bound task remains
active after staging, with its local task branch ready for continued QA.

When a Jira issue exists and matches the released work, move it to `Done` only
after every deployment required by the task scope and its validation have
succeeded and released task content consistency is verified on both servers.
A production-bound task remains open after staging and completes
after production; a task whose declared final scope is staging may complete
after the verified staging deployment.

Before the transition, record concise evidence that identifies the relevant
pull requests, workflow runs, health or runtime checks, migration or seeder
outcomes when applicable, and any material limitation. Keep the issue in its
current status when any required CI, merge, deployment, health check, or local
synchronization remains incomplete or failed.

After transitioning the issue to `Done`, place it at the top of the Done column
when the available Jira integration exposes a supported ranking operation.
Ranking is best effort and is not a completion gate. If ranking is unavailable
or fails, keep the verified `Done` status and report the limitation; do not guess
or directly overwrite an opaque Jira rank value.

## Branch Protection Rules

Branch protection decides whether a branch can receive a push or merge when conditions such as CI success and review have not been met.

CI trigger decides when CI runs. Branch protection decides whether the CI result is required before merge.

Without branch protection, a PR can still be merged even when CI fails. With branch protection, GitHub blocks the merge until required CI checks pass.

Frontend and backend protected branches:

```text
main
staging
```

Rules for all protected frontend and backend branches:

- no direct push;
- changes must enter through PR;
- CI and `Release Branch Policy` must pass;
- review is recommended but is not required by the current branch protection.

Additional behavior:

- `main`: production deploy remains manual or approval-controlled.
- `staging`: after merge, staging deploy is run manually from the deploy repository.

Developers and PMs do not push directly to `main` or `staging`.

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

The deploy repository protects `main` with required pull requests, Deploy CI,
and Release Branch Policy. It does not require approving reviews, but unresolved
review conversations block merge. A merge still does not start a runtime
deployment. Use the manual deployment workflow and the staging-first validation
rule for shared deployment behavior.

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

The shared image deployment script checks capacity before pulling candidates
and performs scoped image retention after a healthy activation. If capacity is
low, it first removes only safe historical project digests and measures again;
it refuses to deploy if the 3 GiB / 10,000 free-inode floor is still unmet.
Active and previous manifests, candidates, and every container image remain
protected. See `deployment.md` for the full policy and read-only dry-run.

The VM checkout lock covers the entire deployment and retention operation.
Do not bypass it with a second manual deployment or direct cleanup. A failed
candidate keeps the existing recovery flow. A post-activation retention warning
does not roll back healthy services, but it must be inspected before release
completion or Jira Done. Record capacity, removed/protected digest evidence and
any warning disposition in Jira/PR/Actions, not application local QA documents.

The primary rollback method is `git revert`, not `git reset` or force push.

For an unhealthy image activation, the deploy script immediately tries the
last successful GHCR digests recorded in `env/<environment>/images.env`.
The previous successful set is also retained as `images.previous.env` after a
successful replacement. The first image-based deploy has no saved digest
rollback; keep the previous deploy revision and local images until cutover is
verified. Image rollback does not undo a database migration. A permanent
source-code rollback still follows the protected-branch `git revert` flow below.

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

Frontend, backend, and deploy protected branches must be changed through their
documented pull request flows. The deploy repository does not use a staging
integration branch, but its changes still enter `main` from a Jira task branch.

For production rollback, create a hotfix or rollback branch from `main`.

For staging rollback, create a hotfix or rollback branch from `staging`.

Revert commits must still pass CI because revert can conflict, fail builds, fail tests, or be incompatible with migrations or data that already ran.

Code rollback does not always rollback the database. Risky migrations must have a rollback plan before production deploy.

Current baseline:

```text
revert commit
merge through PR
deploy again
```

## CI Test Level

CI test level defines which automatic checks run for task branch pushes and
must also pass before a pull request can be merged.

Initial frontend CI:

```bash
npm ci
npm run format:check
npm run test:unit
npm run build
```

Frontend CI verifies that dependencies can be installed cleanly, the code can build, imports are not broken, and syntax or build errors are caught.
It also enforces the configured source formatting and unit test suite.

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
composer install --no-interaction --prefer-dist --no-progress
cp .env.example .env.testing
php artisan key:generate --env=testing --force
php artisan migrate --env=testing --force
php artisan test
```

The CI PostgreSQL service is temporary and only exists during the GitHub Actions job. It is not the local, staging, or production database.

Branch protection requires the frontend and backend CI jobs to pass before their
pull requests can be merged.

Deploy CI validates deployment shell syntax and both Docker Compose
configurations for task branch pushes and pull requests to deploy `main`. These
checks render configuration only and do not deploy, restart, migrate, or seed an
environment.
