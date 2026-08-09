# Deployment Agent Instructions

## Repository Scope

This repository contains deployment configuration and operational workflows.

## Branch Model And Change Flow

The deployment repository has one long-lived branch: `main`. The application
task-branch flow does not apply here.

- Do not create a deploy `staging` branch or persistent deploy `*-staging`
  branches.
- Make deployment repository changes on `main` and push them directly to
  `origin/main` after local validation.
- A push to `main` synchronizes deployment configuration but does not deploy or
  restart the runtime automatically.
- Run the matching manual `Sync Deploy`, `Deploy`, `Migrate`, or `Seed` workflow
  when the change needs to reach an environment.
- Validate shared deployment behavior on staging before applying the same
  change to production.

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

## Related Repositories

The project may include separate frontend and backend repositories. If a task affects another repository and that repository is available in the workspace, inspect its code and documentation as well. Do not assume that related repositories are always available or located at a specific path.

## Automation Documentation and Comments

Every named shell function or operational helper that is added or changed must have documentation that explains its purpose and contract. Documentation must be proportional to complexity and, when relevant, explain:

- inputs, environment variables, and required tools or credentials
- affected services, environments, files, or remote resources
- state changes, deployment side effects, and expected outputs
- safety constraints, failure handling, rollback behavior, and idempotency expectations
- relationships with workflows, containers, health checks, migrations, or release procedures

Anonymous shell snippets and simple callbacks do not require a documentation block unless they contain important behavior or a non-obvious contract. Keep documentation synchronized whenever parameters, environment requirements, side effects, or operational behavior change.

### Multi-step Logic

Shell functions, scripts, and multi-stage shell blocks in workflow files must use paired `step start/end` comments when they contain multiple distinct stages. Use the shell or YAML comment marker, number steps consistently, and keep each start marker paired with a matching end marker.

```bash
# --- step 1 - start - validate the target environment
# ...
# --- step 1 - end - validate the target environment

# --- step 2 - start - deploy and verify service health
# ...
# --- step 2 - end - deploy and verify service health
```

Do not add these markers to purely declarative YAML that has no embedded procedural logic. Use clear job and step names for declarative GitHub Actions structure, and do not add comments to every YAML, Compose, Nginx, or environment line when the configuration is already self-explanatory.

Add contextual comments when they explain operational intent, security boundaries, ordering dependencies, environment differences, failure recovery, compatibility requirements, or deployment risks. Avoid comments that merely repeat commands or configuration keys.

## Git and Commit Workflow

Execute one Git command per terminal invocation. Do not chain Git commands with
`&&`, `;`, command substitution, or a multiline shell block. Wait for each
result before running the next command, and run status or log checks as separate
commands.

Before proposing or creating a commit:

1. Confirm that Git operations are being performed in this repository.
2. Inspect the repository status and the actual diff, not only the changed file names.
3. Understand the behavior change, purpose, impact, and validation associated with the diff.
4. Keep unrelated changes out of the commit and never include changes from another repository.
5. Do not switch branches, create branches, commit, push, or open a pull request unless the user explicitly requests that action.

Use the staged diff as the primary commit scope when files are staged. Review `git diff --cached --stat` and `git diff --cached`, not only the changed file names. If nothing is staged and the user requests a message for working-tree changes, inspect the explicitly scoped actual diff and relevant untracked content and state when the prospective scope cannot yet be determined precisely.

When staging deployment changes, add only the explicitly reviewed files with exact paths. Use `git add -- <file>` for each intended file, or list several exact paths in one command. Never use `git add -A`, `git add .`, `git add --all`, or broad globs. After staging, inspect `git diff --cached --name-status`, `git diff --cached --stat`, and `git diff --cached` so the approval clearly shows which files will be committed and pushed to `deploy/main`.

### Commit Scope and Atomicity

A branch does not define a single commit scope. If a branch or working tree contains changes for multiple tasks, tickets, environments, or independently reviewable purposes, inspect and stage each scope separately and generate one commit message from that scope's staged diff. Changes for one task must not absorb an unrelated rollout, infrastructure fix, configuration update, workflow change, or documentation task merely because they exist on the same branch.

A detailed commit message is not a substitute for an atomic commit. Recommend separate commits when the available changes do not form one cohesive purpose. Keep changes together only when they implement one inseparable operational behavior or when splitting them would create an invalid or materially misleading intermediate state; describe that dependency when it is not obvious.

The commit message must describe only content included in its verified scope. Exclude unstaged changes outside that scope, changes from another repository, unfinished implementation, future plans, and claims inferred only from task names, documentation, or earlier conversation.

Use English with correct grammar for commit messages. Follow the Conventional Commits style already used by this repository, including an appropriate type and scope when applicable.

Inspect recent Git history when the established type, scope, or wording convention is unclear.

The summary must describe the actual high-level change and remain specific enough for code review, Git history, debugging, and revert operations. Do not write a summary based only on file names or claim behavior that is not supported by the diff.

Use imperative mood for the summary when it matches the repository convention. Choose the type and scope from the operational purpose rather than a directory name. For a complex change, follow the summary with a concise context or motivation paragraph that explains the problem, purpose, or high-level approach without repeating the summary.

Use a commit body when additional context is useful. The body may explain behavior, motivation, system impact, technical constraints, API or compatibility changes, configuration, environment variables, deployment considerations, or regressions being prevented. Do not use a body that merely repeats the summary.

Match commit-message detail to the staged scope:

- A small, single-purpose change may use only a precise summary.
- A medium change should normally include a short context paragraph and the main related operational behaviors.
- A complex or cross-cutting change must include a summary, concise context, and a body grouped by behavior or subsystem. Represent every major area included in the commit instead of compressing several container, environment, workflow, rollout, or rollback changes into a generic bullet.

For complex deployment commits, group details using headings derived from the actual diff, such as containers, environment configuration, CI/CD workflows, rollout sequencing, service dependencies, migrations, health checks, rollback, compatibility, security, or documentation. Explain environment differences, ordering constraints, manual steps, failure recovery, runtime variables, and operational risks when relevant. Group by behavior rather than listing every YAML, shell, Compose, Nginx, or environment file.

Mention a file name only when its identity has operational or reviewer significance, such as a specific workflow, environment template, reverse-proxy configuration, or migration-related deployment file. Never include secret or credential values in a commit message.

### Commit Message Structure

Use this structure as an adaptive framework for medium and complex commits:

```text
<type>(<scope>): <summary>

<optional context or motivation paragraph>

<deployment behavior or subsystem group>:
- <major operational change>
- <major operational change>

<another relevant behavior or subsystem group>:
- <major operational change>

<optional technical or impact sections>

Validation:
- <actual automated check or manual operational verification>

Limitations:
- <verified limitation or unvalidated area>

<optional breaking-change and issue footers>

<optional attribution trailers>
```

Do not apply this framework rigidly. Omit empty or irrelevant sections, derive group names from the actual diff, and allow a small single-purpose commit to contain only a precise summary.

Use conditional sections such as `Technical details:`, `Configuration:`, `Deployment:`, `Compatibility:`, `Security:`, `Documentation:`, `Validation:`, and `Limitations:` only when the staged change supports them. Do not add empty or ceremonial sections. Use them to explain source-of-truth decisions, environment variables and defaults, rollout or rollback requirements, service compatibility windows, security boundaries, substantive documentation changes, verified checks, or important unvalidated areas when relevant.

Add a `Validation:` section only when the listed checks were actually executed. State the exact relevant commands or checks, do not claim that a full suite passed when only part of it ran, and report limitations honestly.

Distinguish automated checks from manual staging or production-like verification. Do not present a failed command, an unavailable health check, or an inferred result as successful validation. Add `Limitations:` when an important environment, external service, credential-dependent flow, production-only behavior, rollback path, risk, assumption, or intentionally excluded scope remains unverified; do not add the section ceremonially.

Use a `BREAKING CHANGE:` footer only when the commit introduces a genuinely non-backward-compatible operational contract or behavior. Explain the previous contract, the new contract, and any action consumers or operators must take; do not use the footer merely to emphasize a large change.

Add exactly one Codex co-author trailer only when Codex materially analyzed, wrote, or changed content included in the commit. Do not add it merely because Codex generated or refined the commit message. When the active model and reasoning effort are verified by authoritative session metadata, use `Co-authored-by: Codex (<model>, <reasoning effort>) <noreply@openai.com>`; when only the model is verified, omit the reasoning effort. Never infer or guess either value. If the metadata is unavailable or ambiguous, use `Co-authored-by: Codex <noreply@openai.com>`.

Preserve other valid trailers and do not add a duplicate Codex trailer. Separate trailers from preceding content with a blank line, do not format them as bullets, and place the Codex trailer at the end of the commit message after the body, conditional sections, `BREAKING CHANGE:` footer, and issue references.

Before presenting or creating the commit message, verify that the repository and staged scope are correct, every major operational subsystem in scope is represented, each claim is supported by the diff or executed validation, English grammar is sound, no empty section remains, relevant limitations are disclosed, and footers and trailers are correctly ordered.

For multi-line commit messages, use real newline characters. Do not place literal `\n` sequences inside `git commit -m` arguments. Prefer `git commit -F -` with a heredoc or another method that preserves the intended line breaks.

Hard-wrap commit-message prose at 72 characters per line. Keep the subject at
72 characters or fewer. Do not wrap commands, URLs, paths, hashes, code
identifiers, or trailers because their exact text must remain easy to copy.

After creating a commit, run:

```bash
git log -1 --format=full
```

Verify that the commit is in the correct repository, the summary and body are accurate, sections and bullet points have the intended line breaks, no literal `\n` text was stored, and validation claims match checks that were actually run. If the message is malformed and the commit has not been pushed, correct it when doing so is safe.

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
