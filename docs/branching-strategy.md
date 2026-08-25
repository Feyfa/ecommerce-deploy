# Branching Strategy

This document defines the branch strategy used by the frontend and backend
repositories.

The frontend and backend are separate repositories, but both repositories use the
same branch roles and release flow. The goal is to let staging contain unfinished
integration work without accidentally shipping that work to production.

The deploy repository is intentionally different: it uses only its long-lived
`main` branch and does not create a persistent `staging` or `*-staging` branch.
Its change and deployment procedure is defined in `release-flow.md`.

## Branch Roles

### `main`

`main` is the production branch.

Only production-ready changes should enter this branch. Production deployments
should come from `main` or from a release tag created from `main`.

### `staging`

`staging` is the staging deployment branch.

This branch represents the code deployed to the staging server. It can contain
features under staging validation that are not ready for production yet.

### Jira task branches

`feature/*`, `story/*`, `bug/*`, and `task/*` are the main branches for planned
Jira work. Use `task/*` for general Jira tasks that are not classified as a
feature, story, or bug. Every branch must follow the shared Jira naming
convention defined in `release-flow.md`.

The main task branch is the source of truth for the work and is merged directly
into `main` when the change is production-ready.

Examples:

```text
feature/jd-tok-9
story/ar-tok-8
bug/jd-tok-7
task/jd-tok-17
```

### Jira task staging branches

`feature/*-staging`, `story/*-staging`, `bug/*-staging`, and `task/*-staging`
are staging integration branches for planned Jira work.

The staging task branch isolates synchronization and conflict resolution against
`staging` from the production candidate branch. It merges directly into
`staging`; production must not merge from a `*-staging` Jira task branch.

Examples:

```text
feature/jd-tok-9-staging
story/ar-tok-8-staging
bug/jd-tok-7-staging
task/jd-tok-17-staging
```

### `hotfix/*`

`hotfix/*` is used for urgent production fixes.

Hotfix branches start from `main` so urgent fixes start from the current
production source of truth, then merge directly into `main`.

Example:

```text
hotfix/jd-tok-10
```

### `hotfix/*-staging`

`hotfix/*-staging` can be used when a hotfix also needs staging integration and
`staging` has conflicts or staging-only changes. It merges directly into
`staging`; it is not a production source branch.

## Jira Task Branch Preconditions

Before changing frontend or backend code, the Jira task identity must be clear.
The work type, responsible initials, Jira issue key, and expected branch name
must be known before implementation starts.

If any of these details are unclear, stop before editing code, creating a
branch, committing, pushing, or opening a pull request. Explain the expected
branch format to the user and ask for the missing Jira information. Do not
invent a Jira key or use `main` or `staging` as an implementation workspace.

The main Jira task branch is a required implementation prerequisite. It must be
created or checked out before the first code change. Verify that the active
branch is the expected task branch before implementation and after every branch
switch. If the active branch is `main`, `staging`, or unrelated to the Jira
task, stop implementation until the correct task branch is active.

## Jira Task Branch Flow

Every planned Jira task starts from `main`.

```text
main
  -> bug/jd-tok-7
  -> bug/jd-tok-7-staging
```

The main Jira task branch remains the source of truth. The matching
`*-staging` task branch is used only for staging integration.

### Source Branch Completion Rule

Before creating or updating a `*-staging` task branch, finish every intended
change in the main Jira task branch first, including application code, tests,
environment examples, build integration, affected documentation, and fixes
found during local review.

Commit and push those changes to the main Jira task branch before carrying them
into the staging integration branch. Do not create the staging branch merely
because the task is expected to go to staging later, and do not use the
`*-staging` branch as the primary workspace for unfinished task work.

If CI runs for main task branch pushes, wait for it to pass before creating or
refreshing the task staging branch. If no such CI exists, continue immediately
after the push; the push is a remote checkpoint, not a stopping point in the
staging preparation workflow.

When the task staging branch already exists, merge the latest main task branch
into it after every new source-branch change. Do not recreate the staging
branch and do not copy individual files manually.

Environment synchronization is mandatory but remains isolated by purpose:

- merge the latest `main` into the main Jira task branch before preparing
  either a staging release or a production candidate;
- merge the latest main Jira task branch and the latest `staging` into the
  matching `*-staging` task branch when preparing staging;
- never merge `staging` into the main Jira task branch merely to prepare a
  staging release;
- never merge a main Jira task branch directly into `staging`.

### Staging Branch Source Invariant

Before creating or refreshing a Jira task `*-staging` branch, update the local
`staging` branch with `git pull --ff-only origin staging`. The task staging
branch must be created from the completed main Jira task branch, then updated
by merging the refreshed local `staging` branch.

`origin/staging` is a remote-tracking reference, not a replacement for the
local `staging` branch. Do not create or reset a task staging branch with
`git switch -c/-C <task>-staging origin/staging` or
`git checkout -b/-B <task>-staging origin/staging`. If the task staging branch
already exists, switch to it and update it; do not recreate or reset it.

A new task staging branch must be created while the completed main Jira task
branch is checked out. Immediately before creating it, run
`git branch --show-current` and require the output to exactly match the main
task branch name. Never create the branch while `main`, `staging`, or another
branch is checked out.

Application integration merges must use refreshed local branches. Update local
`main` and `staging` with `git pull --ff-only` first, then merge the local
`main`, `staging`, or Jira task branch name. Do not use `origin/main`,
`origin/staging`, or `origin/<task>` as direct `git merge` sources. This does
not prohibit using remote references for `git fetch`, `git pull --ff-only`, or
`git push`.

Before continuing to either staging or production, sync the main Jira task
branch with the latest `main`:

```text
main
  -> bug/jd-tok-7
```

Before opening a staging PR, sync the staging integration branch with the
latest `staging`:

```text
staging
  -> bug/jd-tok-7-staging
```

All sync operations use merge, not rebase.

## Staging Flow

Use this flow when a Jira task needs to be tested in staging:

```text
merge latest main into the main Jira task branch
  -> resolve source-branch conflicts and validate the main task branch
  -> create or update the matching task staging branch
  -> merge latest staging into the task staging branch
  -> resolve staging conflicts in the task staging branch
  -> task staging branch merges directly into staging
  -> manual staging deployment
```

Conflict resolution for staging happens in the matching `*-staging` task
branch, not in `staging`.

If a PR from a task staging branch to `staging` still conflicts after normal
sync with `staging`, merge the PR target branch `staging` into the task staging
branch, resolve the conflict there, commit, and push the task staging branch
again.

## Production Flow

Use this flow when a Jira task is ready for production:

```text
merge latest main into the main Jira task branch
  -> resolve production conflicts in the main task branch
  -> main task branch merges directly into main
  -> production deploys from main or a release tag from main
```

Production must use the main Jira task branch, not its `*-staging` branch.

If a PR from a main Jira task branch to `main` still conflicts after normal
sync with `main`, merge the PR target branch `main` into the main task branch,
resolve the conflict there, commit, and push the task branch again.

## Fix Rules During Staging

When an additional bug is found during staging testing, the default rule is:

```text
Fix in the main Jira task branch first.
Then merge the main Jira task branch into its task staging branch.
Then test again in staging.
```

This keeps the production candidate branch and the staging integration branch
aligned.

If a fix is made directly in a task staging branch because it is a
conflict-specific staging fix, the developer must review whether the fix is
also needed in the main Jira task branch.

Documentation follows the same rule as code. If a behavior change makes
existing documentation incomplete or inaccurate, update the documentation in
the main Jira task branch first, commit it, and then merge the task branch into
its task staging branch. Leave documentation unchanged only when review
confirms that it still describes the implementation accurately.

## Hotfix Flow

Use this flow for urgent production fixes:

```text
main
  -> hotfix/jd-tok-10
  -> main
  -> production deploy
```

This keeps hotfixes based on the current production source of truth.

After production is fixed, bring the hotfix back to staging:

```text
hotfix/jd-tok-10
  -> hotfix/jd-tok-10-staging
  -> staging
```

When the hotfix can merge cleanly into `staging` without bringing staging-only
history into the production hotfix branch, the staging integration branch is
not required.

## Conflict Rules

Conflict resolution must happen before a protected branch receives the change.

Rules:

- Staging conflicts are resolved in Jira task `*-staging` branches or
  `hotfix/*-staging`.
- Production conflicts are resolved in main Jira task branches or `hotfix/*`.
- `staging` and `main` are not used as manual conflict resolution workspaces.
- PMs and reviewers should only merge branches that are clean and ready.
- If another pull request is merged first and a branch becomes conflicted, the
  developer who owns the branch updates it and resolves the conflict.
- Normal task sync uses `main` for the main Jira task branch and `staging` for
  its matching `*-staging` branch.
- If the PR still conflicts after normal sync, merge the PR target branch into
  the Jira task branch and resolve the conflict there.

## Release Safety Rules

Production release safety depends on keeping staging integration separate from
production candidates.

Rules:

- Do not merge `staging` into `main`.
- Do not merge any Jira task `*-staging` branch into `main`.
- Do not ship unfinished staging-only tasks to production.
- Production deploys should come from `main` or a release tag from `main`.

## Practical Summary

Normal Jira task:

```text
bug/jd-tok-7
bug/jd-tok-7-staging
```

Staging receives:

```text
bug/jd-tok-7-staging -> staging
```

Production receives:

```text
bug/jd-tok-7 -> main
```

The staging branch exists to absorb staging conflicts. The main Jira task
branch remains the production candidate.
