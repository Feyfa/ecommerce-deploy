# Branching Strategy

This document defines the branch strategy used by the ecommerce repositories.

The frontend and backend are separate repositories, but both repositories should use the same branch roles and release flow. The goal is to let staging contain unfinished integration work without accidentally shipping that work to production.

## Branch Roles

### `main`

`main` is the production branch.

Only production-ready changes should enter this branch. Production deployments should come from `main` or from a release tag created from `main`.

### `develop-main`

`develop-main` is the production gate.

This branch receives production candidate changes before they are merged into `main`. It is a merge-check gate, not the normal starting point for new feature work.

### `staging`

`staging` is the staging deployment branch.

This branch represents the code deployed to the staging server. It should receive changes from `develop-staging` through the agreed staging deploy process.

### `develop-staging`

`develop-staging` is the staging gate.

This branch can contain features that are being tested in staging and are not ready for production yet. `develop-staging` must not be merged directly into `develop-main` or `main` unless every change inside it is intentionally ready for production.

### Jira task branches

`feature/*`, `story/*`, `bug/*`, and `task/*` are the main branches for planned
Jira work. Use `task/*` for general Jira tasks that are not classified as a
feature, story, or bug. Every branch must follow the shared Jira naming
convention defined in `release-flow.md`.

The main task branch is the source of truth for the work and the branch that
can later be merged into `develop-main` when the change is production-ready.

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

The staging task branch is used to resolve conflicts against
`develop-staging` and prepare the task for staging without changing the
production candidate branch.

Examples:

```text
feature/jd-tok-9-staging
story/ar-tok-8-staging
bug/jd-tok-7-staging
task/jd-tok-17-staging
```

Production must not merge from a `*-staging` Jira task branch.

### `hotfix/*`

`hotfix/*` is used for urgent production fixes.

Hotfix branches should start from `main` so urgent fixes start from the current production source of truth.

Example:

```text
hotfix/jd-tok-10
```

### `hotfix/*-staging`

`hotfix/*-staging` can be used when the same hotfix needs a staging integration branch because `develop-staging` has conflicts or staging-only changes.

If the hotfix can merge cleanly into `develop-staging`, this extra branch is not required.

## Jira Task Branch Flow

Every planned Jira task starts from `main`.

```text
main
  -> bug/jd-tok-7
  -> bug/jd-tok-7-staging
```

The main Jira task branch remains the source of truth.

The matching `*-staging` task branch is used only for staging integration.

### Source Branch Completion Rule

Before creating or updating a `*-staging` task branch, finish every intended
change in the main Jira task branch first, including application code, tests,
environment examples, build integration, affected documentation, and fixes
found during local review.

Commit and push those changes to the main Jira task branch before carrying them
into the staging integration branch. Do not create the staging branch merely
because the task is expected to go to staging later, and do not use the
`*-staging` branch as the primary workspace for unfinished task work.

When the task staging branch already exists, merge the latest main task branch
into it after every new source-branch change. Do not recreate the staging
branch and do not copy individual files manually.

Environment synchronization is mandatory but remains isolated by purpose:

- merge the latest `main` into the main Jira task branch before preparing
  either a staging release or a production candidate;
- merge the latest `staging` into the matching `*-staging` task branch when
  preparing staging;
- never merge `staging` into the main Jira task branch merely to prepare a
  staging release;
- never merge a main Jira task branch directly into `develop-staging` or
  `staging`.

Before continuing to either staging or production, sync the main Jira task
branch with the latest `main`:

```text
main
  -> bug/jd-tok-7
```

Before opening a staging PR, sync the staging integration branch with the latest `staging`:

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
  -> task staging branch merges into develop-staging
  -> develop-staging deploys or merges into staging
```

Conflict resolution for staging happens in the matching `*-staging` task
branch, not in `develop-staging` or `staging`.

If a PR from a task staging branch to `develop-staging` still conflicts after
normal sync with `staging`, merge the PR target branch `develop-staging` into
the task staging branch, resolve the conflict there, commit, and push the task
staging branch again.

## Production Flow

Use this flow when a Jira task is ready for production:

```text
merge latest main into the main Jira task branch
  -> resolve production conflicts in the main task branch
  -> main task branch merges into develop-main
  -> develop-main merges into main
  -> production deploys from main or a release tag from main
```

Production must use the main Jira task branch, not its `*-staging` branch.

If a PR from a main Jira task branch to `develop-main` still conflicts after
normal sync with `main`, merge the PR target branch `develop-main` into the
main task branch, resolve the conflict there, commit, and push the task branch
again.

## Fix Rules During Staging

When an additional bug is found during staging testing, the default rule is:

```text
Fix in the main Jira task branch first.
Then merge the main task branch into its task staging branch.
Then test again in staging.
```

This keeps the production candidate branch and the staging integration branch aligned.

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
main or develop-main
  -> hotfix/jd-tok-10
  -> develop-main
  -> main
  -> production deploy
```

This keeps hotfixes based on the current production source of truth.

After production is fixed, bring the hotfix back to staging:

```text
hotfix/jd-tok-10
  -> develop-staging
  -> staging
```

If `develop-staging` has conflicts, use a staging integration branch:

```text
hotfix/jd-tok-10
  -> hotfix/jd-tok-10-staging
  -> develop-staging
  -> staging
```

## Conflict Rules

Conflict resolution must happen before a protected branch receives the change.

Rules:

- Staging conflicts are resolved in Jira task `*-staging` branches or
  `hotfix/*-staging`.
- Production conflicts are resolved in main Jira task branches or `hotfix/*`.
- `develop-staging`, `staging`, `develop-main`, and `main` are not used as manual conflict resolution workspaces.
- PMs and reviewers should only merge branches that are clean and ready.
- If another pull request is merged first and a branch becomes conflicted, the developer who owns the branch updates it and resolves the conflict.
- Normal task sync uses `main` for the main Jira task branch and `staging` for
  its matching `*-staging` branch.
- If the PR still conflicts after normal sync, merge the PR target branch into
  the Jira task branch and resolve the conflict there.

## Release Safety Rules

Production release safety depends on keeping staging integration separate from production candidates.

Rules:

- Do not merge `develop-staging` directly into `develop-main` unless every change in `develop-staging` is intentionally production-ready.
- Do not merge `staging` into `main`.
- Do not merge any Jira task `*-staging` branch into `develop-main` or `main`.
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
bug/jd-tok-7-staging -> develop-staging -> staging
```

Production receives:

```text
bug/jd-tok-7 -> develop-main -> main
```

The staging branch exists to absorb staging conflicts. The main Jira task
branch remains the production candidate.
