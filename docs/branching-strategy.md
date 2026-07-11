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

### `feature/*`

`feature/*` is the main branch for a feature.

This branch is the source of truth for the feature and the branch that can later be merged into `develop-main` when the feature is production-ready.

Example:

```text
feature/seller-buyer-chat
```

### `feature/*-staging`

`feature/*-staging` is the staging integration branch for a feature.

This branch is used to resolve conflicts against `develop-staging` and prepare the feature for staging without changing the production candidate branch.

Example:

```text
feature/seller-buyer-chat-staging
```

Production must not merge from `feature/*-staging`.

### `hotfix/*`

`hotfix/*` is used for urgent production fixes.

Hotfix branches should start from `main` so urgent fixes start from the current production source of truth.

Example:

```text
hotfix/fix-login-error
```

### `hotfix/*-staging`

`hotfix/*-staging` can be used when the same hotfix needs a staging integration branch because `develop-staging` has conflicts or staging-only changes.

If the hotfix can merge cleanly into `develop-staging`, this extra branch is not required.

## Feature Branch Flow

Every feature starts from `main`.

```text
main
  -> feature/name
  -> feature/name-staging
```

`feature/name` remains the source of truth.

`feature/name-staging` is used only for staging integration.

### Source Branch Completion Rule

Before creating or updating `feature/name-staging`, finish every intended
feature change in `feature/name` first, including application code, tests,
environment examples, build integration, affected documentation, and fixes
found during local review.

Commit and push those changes to `feature/name` before carrying them into the
staging integration branch. Do not create the staging branch merely because the
feature is expected to go to staging later, and do not use
`feature/name-staging` as the primary workspace for unfinished feature work.

When `feature/name-staging` already exists, merge the latest `feature/name`
into it after every new source-branch change. Do not recreate the staging branch
and do not copy individual files manually.

Environment synchronization is mandatory but remains isolated by purpose:

- merge the latest `main` into `feature/name` before preparing either a staging
  release or a production candidate;
- merge the latest `staging` into `feature/name-staging` when preparing staging;
- never merge `staging` into `feature/name` merely to prepare a staging release;
- never merge `feature/name` directly into `develop-staging` or `staging`.

Before continuing to either staging or production, sync the source feature
branch with the latest `main`:

```text
main
  -> feature/name
```

Before opening a staging PR, sync the staging integration branch with the latest `staging`:

```text
staging
  -> feature/name-staging
```

All sync operations use merge, not rebase.

## Staging Flow

Use this flow when a feature needs to be tested in staging:

```text
merge latest main into feature/name
  -> resolve source-branch conflicts and validate feature/name
  -> feature/name-staging
  -> merge latest staging into feature/name-staging
  -> resolve staging conflicts in feature/name-staging
  -> feature/name-staging merges into develop-staging
  -> develop-staging deploys or merges into staging
```

Conflict resolution for staging happens in `feature/name-staging`, not in `develop-staging` or `staging`.

If a PR from `feature/name-staging` to `develop-staging` still conflicts after normal sync with `staging`, merge the PR target branch `develop-staging` into `feature/name-staging`, resolve the conflict there, commit, and push the feature staging branch again.

## Production Flow

Use this flow when a feature is ready for production:

```text
merge latest main into feature/name
  -> resolve production conflicts in feature/name
  -> feature/name merges into develop-main
  -> develop-main merges into main
  -> production deploys from main or a release tag from main
```

Production must use `feature/name`, not `feature/name-staging`.

If a PR from `feature/name` to `develop-main` still conflicts after normal sync with `main`, merge the PR target branch `develop-main` into `feature/name`, resolve the conflict there, commit, and push the feature branch again.

## Fix Rules During Staging

When a bug is found during staging testing, the default rule is:

```text
Fix in feature/name first.
Then merge feature/name into feature/name-staging.
Then test again in staging.
```

This keeps the production candidate branch and the staging integration branch aligned.

If a fix is made directly in `feature/name-staging` because it is a conflict-specific staging fix, the developer must review whether the fix is also needed in `feature/name`.

Documentation follows the same rule as code. If a behavior change makes
existing documentation incomplete or inaccurate, update the documentation in
`feature/name` first, commit it, and then merge the feature branch into
`feature/name-staging`. Leave documentation unchanged only when review confirms
that it still describes the implementation accurately.

## Hotfix Flow

Use this flow for urgent production fixes:

```text
main or develop-main
  -> hotfix/name
  -> develop-main
  -> main
  -> production deploy
```

This keeps hotfixes based on the current production source of truth.

After production is fixed, bring the hotfix back to staging:

```text
hotfix/name
  -> develop-staging
  -> staging
```

If `develop-staging` has conflicts, use a staging integration branch:

```text
hotfix/name
  -> hotfix/name-staging
  -> develop-staging
  -> staging
```

## Conflict Rules

Conflict resolution must happen before a protected branch receives the change.

Rules:

- Staging conflicts are resolved in `feature/*-staging` or `hotfix/*-staging`.
- Production conflicts are resolved in `feature/*` or `hotfix/*`.
- `develop-staging`, `staging`, `develop-main`, and `main` are not used as manual conflict resolution workspaces.
- PMs and reviewers should only merge branches that are clean and ready.
- If another pull request is merged first and a branch becomes conflicted, the developer who owns the branch updates it and resolves the conflict.
- Normal feature sync uses `main` for `feature/*` and `staging` for `feature/*-staging`.
- If the PR still conflicts after normal sync, merge the PR target branch into the feature branch and resolve the conflict there.

## Release Safety Rules

Production release safety depends on keeping staging integration separate from production candidates.

Rules:

- Do not merge `develop-staging` directly into `develop-main` unless every change in `develop-staging` is intentionally production-ready.
- Do not merge `staging` into `main`.
- Do not merge `feature/*-staging` into `develop-main` or `main`.
- Do not ship unfinished staging-only features to production.
- Production deploys should come from `main` or a release tag from `main`.

## Practical Summary

Normal feature:

```text
feature/name
feature/name-staging
```

Staging receives:

```text
feature/name-staging -> develop-staging -> staging
```

Production receives:

```text
feature/name -> develop-main -> main
```

The staging branch exists to absorb staging conflicts. The main feature branch remains the production candidate.
