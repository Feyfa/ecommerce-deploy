# Deployment Agent Instructions

## Repository Scope

This repository contains deployment configuration and operational workflows.

## Branch Model And Change Flow

The deployment repository has one long-lived branch, `main`, and uses Jira task
branches as short-lived review branches. Its flow does not use the application
task staging branch model.

- Do not create a deploy `staging` branch or deploy `*-staging` branches.
- Before changing deployment files, verify the Jira work type, responsible
  initials, issue key, and expected branch name.
- Create a new deploy task branch from the latest `main`, using the same
  `{work-type}/{initial}-{jira-key}` convention as the application repositories.
- Do not implement deployment changes directly on `main`.
- Push the deploy task branch and wait for its push-triggered Deploy CI to pass
  before opening or continuing its pull request to `main`.
- Wait for the pull request Deploy CI and Release Branch Policy checks to pass
  before merging the task branch into `main`.
- A merge to `main` synchronizes deployment configuration but does not deploy or
  restart the runtime automatically.
- Run the matching manual `Sync Deploy`, `Deploy`, `Migrate`, or `Seed` workflow
  when the change needs to reach an environment.
- Validate shared deployment behavior on staging before applying the same
  change to production.

## Working Branch End State And Release Completion

- After staging branch preparation, leave each participating application on its main Jira
  task branch after validating and pushing `*-staging`. Return deploy to its task branch
  after temporary inspection or refresh of `main`. Operations involving only long-lived
  branches finish on `main`.
- After each successful staging or production deployment and its health checks, confirm
  the working trees are safe to switch. Refresh local application `staging` and `main` and deploy
  `main` with `--ff-only`. Preserve local changes and task branches.
- While QA, fixes, or production promotion remain, finish on the main Jira task branch
  for each participating repo that has one. Use `main` when a repo has no task branch or
  the task's declared scope is complete. Production-bound completion requires production
  validation. Never force a switch, reset, or delete work to reach a checkout state.
- The runtime sources are application `staging` for staging, application `main` for
  production, and deploy `main` for workflows and VMs. Verify the final local checkout
  with `git branch --show-current` in every affected repo. Report failed pulls or checks.
- For a matching Jira issue, record release evidence. Move it to `Done` only after all
  required CI, merges, deployments, health checks, content checks, and local sync pass.
  Then rank it first in Done if a supported operation is available. Report a failed or
  unavailable ranking operation and leave opaque rank values to Jira.

## Project Documentation

Repository documentation is available in the `docs/` directory.

Before answering or acting on a deployment-specific request:

1. Identify the environments, services, and deployment flows related to the task.
2. Search for and read the relevant documentation in `docs/`. Do not read every document unless the task requires it.
3. Inspect the related configuration, scripts, dependencies, and workflows to verify that the documentation still reflects the current repository state.
4. Follow the architecture, patterns, and configuration style already used in this repository.
5. Preserve the existing writing and configuration style, including whitespace and formatting. Do not reformat or change style unless the task explicitly requests it or the change is required for correctness.
6. Update the relevant documentation when a change affects environment variables, containers, servers, pipelines, provisioning, release flows, rollback procedures, or the developer workflow.
7. Treat the current configuration and repository state as the primary evidence. Separate verified facts from unresolved assumptions and do not use unverified assumptions as the basis for a change or operational action.
8. If the user interrupts, corrects, or asks for the instructions or situation to be reread, stop and repeat this preflight against the current state before continuing.

Review the relevant documentation before modifying containers, server configuration, environment variables, pipelines, provisioning, branching strategy, release flows, or deployment procedures.

## Released Task Content Consistency

- Finish every tracked change for a production-bound task on its main Jira task branch.
  Integrate and deploy that task content to staging before production, including tests,
  Markdown, agent instructions, lockfiles, and configuration. Any tracked edit after
  staging verification goes through staging integration and deployment again.
- Compare task content and overlapping hunks across the application branches. Attribute
  other differences to pending tasks and preserve their staging changes. Merge SHAs may
  differ. Resolve any unclear loss or change in the released task before promotion.
  Never reset staging to main, merge staging into main, or promote pending work to
  force whole-branch equality.
- Verify the source revisions active on both servers as well as the branch content.
  If tracked content is packaged into an image, deploy the final image to both
  environments. For deploy changes, verify the same released deploy revision on both VMs.
- Record content comparisons, pending-task exceptions, active revisions, and health
  evidence in Jira, PRs, or Actions. Keep release completion pending until the required
  deployment and consistency checks are verified.

## Local QA Documentation Boundary

Keep application `frontend/docs/qa/` and `backend/docs/qa/` for local QA. Record scenarios,
expected results, actual tests or review, and local coverage limitations before commit.
Label pending local checks as local and preserve unrelated historical QA.

Record post-commit CI, push, PR, merge, smoke tests, deployment, runtime health, image or
source revisions, and Jira completion in Jira, PRs, or Actions. These release checks
remain required.

## Manual QA Guidance And Evidence Reuse

- Map affected behavior and regression risks to pass criteria. Review existing tests,
  screenshots, and logs first. Track each scenario's evidence and status with its
  environment and relevant revision when known.
- Group related checks into a short sequence with the exact action, expected result,
  and minimum capture. Say which open scenarios each result proves and request only
  the evidence still missing.
- Reuse proof for the same behavior, environment, and relevant task content. Repeat only
  the checks affected by unclear evidence, a failure, a relevant change, or stale
  evidence. Explain the reason for the repeat.
- Match conclusions to what was observed. A screenshot of a refreshed cart can prove
  the visible quantity, selection, and total together. An HTTP 200 alone cannot prove
  business behavior. Required deployed manual checks still need deployed evidence.
- Follow the agreed QA scope. Obtain authorization before opening a browser,
  making real payments, or taking destructive or other state-changing actions while
  guiding QA. Stop asking for checks once required scenarios are proven, and report any
  remaining coverage limitations.

## Incremental Change Batches

Make file changes incrementally around one clear objective or behavior at a
time so that a human reviewer can understand the purpose and scope of each
batch.

- Do not combine independent objectives into one batch of edits.
- Before each batch, explain its objective, the files expected to change, and
  why each file belongs to that objective.
- Use the smallest practical file batch that keeps the implementation
  consistent and allows meaningful validation.
- When an objective requires only one file, edit and validate that file before
  proceeding to another independent objective.
- Multiple files may be changed together only when they implement or verify
  one shared contract or inseparable behavior. Explain that relationship before
  editing them.
- After each batch, inspect the actual diff and report the files changed, the
  resulting behavior, and the validation performed before starting another
  independent objective.
- Do not implement an entire multi-objective task first and explain all changes
  only after the full task is complete.
- If the required scope expands beyond the announced batch, explain the new
  file and reason before editing it.

## Related Repositories

The project may include separate frontend and backend repositories. If a task affects another repository and that repository is available in the workspace, inspect its code and documentation as well. Do not assume that related repositories are always available or located at a specific path.

## Automation Documentation and Comments

Document the purpose and contract of new or changed named shell functions and
operational helpers. Describe relevant inputs, environment variables, tools or
credential requirements, affected services, side effects, and expected results.
Document operational constraints, failure behavior, rollback, and idempotency when
they matter. Keep the description aligned with workflow and runtime behavior.

Document anonymous snippets when they perform important work or have a non-obvious
contract. Use contextual comments for verified security, ordering, compatibility, and
recovery requirements.

### Multi-step Logic

Use paired `# --- step N - <stage name> - start ---` and
`# --- step N - <stage name> - end ---` for logic with distinct stages. Use them in
scripts, functions, and procedural shell blocks in workflow YAML. Group related
statements under one concrete stage and explain the reason below its start marker.
Separate stages with a blank line. Place the closing marker before any `return` that
ends its stage and leave a blank line between them. A single-stage function gets a
short intent comment.

Use job and step names for declarative YAML. Use ordinary comments in declarative
configuration when there is a constraint the reader needs to know.

## Command And Approval Readability

Use one command per terminal invocation and wait for each Git or SSH command to finish.
Use the tool's working-directory option. Break long commands into one option or path per
line and keep complex logic in a small, reviewable script. Explain a temporary script
before running it.

Keep approval requests explicit about reads and writes. Explain what a destructive
action or remote write will do and why, then run it on its own. Never join operations
with shell separators, command substitution, or a multiline block.

## Git and Commit Workflow

Before proposing or creating a commit, confirm this repo and inspect its Git status.

Review the staged diff as the commit scope. If asked for a message from the working
tree before staging, inspect the scoped diff and relevant untracked files. Report any
uncertainty about the prospective scope. Switch or create branches, commit, push, or
open a PR only on explicit request.

Stage exact reviewed paths with `git add -- <path>`. For several paths, use one Git
command with continuations and one path per line. Avoid broad globs and whole-tree
staging. Check `git diff --cached --name-status`, `git diff --cached --stat`, and
`git diff --cached` as separate commands before committing.

### Commit Scope and Atomicity

Keep each commit within one repository and one reviewable purpose. Put related code,
tests, and docs together when they deliver the same behavior. Split independent changes
even if they share a branch. Describe inseparable changes when the dependency matters.

### Commit Message Structure

Use clear English and a Conventional Commits subject `<type>(<scope>): <summary>`.
Choose type and scope from the staged behavior. Use an imperative summary and limit the
whole subject to 72 characters. Wrap body prose at 72 characters and preserve commands,
URLs, paths, hashes, identifiers, and trailers. Reserve subject-only messages for
trivial changes.

Describe the motivation, changed behavior, and material decisions from the staged diff.
Group the body by behavior. Add API, migration, configuration, or release details when
relevant. Use `Validation:` for checks actually run, with their commands and results.
Include material gaps in `Limitations:` and keep credentials out of the message.
Use a `BREAKING CHANGE:` footer only for a breaking contract and explain the impact
and action consumers or operators need to take.

For deploy changes, describe affected environment settings, rollout order, dependencies,
health checks, rollback, and operational constraints when relevant.

Use exactly one Codex co-author trailer when Codex materially contributed to the
staged content. Use `Co-authored-by: Codex (<model>, <reasoning effort>) <noreply@openai.com>`
when both details are verified. Omit the effort if only the model is verified. Use
`Co-authored-by: Codex <noreply@openai.com>` when metadata is unavailable or ambiguous.
Preserve valid trailers and place the Codex trailer last, after the body, footers, and
issue references, with a blank line before the trailer block.

### Commit Message Execution

Use the Ecommerce runbook's heredoc rule for commit input, including subject-only
messages and amendments that replace the message. Pass real newlines through a quoted
`'EOF'` delimiter with `git commit -F -`.

```bash
git commit -F - <<'EOF'
docs(workflow): describe the verified change
EOF
```

After committing, run `git log -1 --format=full` separately. Verify the repo, saved
message, line breaks, claims, and trailers.

## GitHub Tool Selection

Identify the repository and whether the operation is a pull request or GitHub Actions.
Use the tool specified for that operation.

### GitHub CLI Authentication Checks

Use standalone, read-only `gh auth status` when CLI authentication needs verification.
On the affected macOS host, a sandboxed check can miss the host keyring. Use the host
check directly when needed and the approval flow supports it. Explain that it is
read-only and scope any reusable approval to `["gh", "auth", "status"]`.

Report an unavailable host check and distinguish authentication failures from network
or environment errors. A sandbox-only failure leaves host auth unverified. Confirm the
active account, scopes, and required repo permissions. Keep tokens out of output and
documentation. Leave login state and settings alone during the check, and apply the usual
approvals to other commands.

### GitHub Pull Requests

Use `[TOK-X-staging] <description>` for application staging PRs and
`[TOK-X] <description>` for main PRs. Use the actual Jira key and the same description
for paired PRs. Deploy PRs target `main`.

Use the connected GitHub integration first. If unavailable or unsuccessful, explain
the limitation and use `gh pr`. Use `gh api` when a standard subcommand cannot perform
the operation. Browser interaction requires an explicit request.

Before a PR write, confirm the repo, PR number when applicable, and source and target
branches. For deploy PR writes, verify the GitHub account and repository permissions.
Verify the result through the integration or the stated fallback.

### GitHub Actions

Use the GitHub CLI for Actions. Run manual workflows with `gh workflow run` and
inspect runs with `gh run list`, `gh run view`, or `gh run watch`.
Before an operation that changes remote state, verify the GitHub account and its
repository and workflow permissions. If `gh` is unavailable or authentication fails,
report the limitation and stop the affected operation.
Keep deploy Actions in the CLI. Browser extensions and automation remain excluded.

### CI And Deployment Monitoring

- Discover a run with `gh run list` and record its repo, run ID, workflow/event, source SHA,
  and attempt. For a queued or running run, prefer one watcher.
  `gh run watch <run-id> --repo <owner/repo> --exit-status --compact --interval 30`
- Keep the watcher in one resumable session with waits of at most 60 seconds. Use a
  task/run-specific log outside the repo when practical. Read a small relevant tail and
  give updates from known state. Leave polling to the healthy watcher.
- Recheck on discovery, final confirmation, interruption, ambiguous results, failure,
  or a user status request. On a disconnected or unsupported watcher, check the run
  once and resume one watcher if possible. Use bounded, compact CLI polling as the fallback.
- Confirm terminal status, conclusion, source SHA, and attempt with `gh run view`.
  A watcher exit or timeout does not establish the remote result or justify a retry.
  On failure inspect `gh run view <run-id> --log-failed` for the error and rollback or
  health evidence. On success read the logs needed for active revisions, images, and
  service/HTTP health.
- Reuse valid evidence for unchanged content and the same verification context.
  Keep push and PR CI separate. Record post-commit evidence in Jira, PRs, or Actions.
  Monitoring grants no permission to merge, retry, dispatch, or promote a release.
- Use subagents only with explicit authorization for distinct work.

See `docs/release-flow.md` for release monitoring examples when available.
