---
name: atomic-commits
description: Use this skill on any coding task in a git repository — consult it whenever writing, editing, refactoring, or fixing code so its commit rules apply. The skill governs commit cadence: one commit per independent, verifiable change (not per file edit, not per save). Commits happen locally as soon as the change passes verification, before moving on to the next change. Do NOT push to remote; commits stay local.
---

# Atomic Local Commits

Every independent, verifiable change must become its own local git commit before moving on. Do not batch multiple changes into one commit, and do not push.

## What counts as one commit

One commit = one change that can be described in a single sentence, verified on its own, and reverted on its own.

- Bug fix → one commit.
- New function or endpoint → one commit (with its tests).
- Refactor → separate commit from any behavior change. Refactor first, feature after.
- Formatting / rename-only changes → their own commit, never mixed with logic changes.
- Dependency bump → its own commit.

If a change is too large to verify in one step, split it into smaller commits that each leave the repo in a working state (builds, tests pass).

## When to commit

After each independent change, in this order:

1. Run the project's verification commands (see "Verification" below). All must pass.
2. `git status` — confirm the staged set matches the intended change. No stray files.
3. `git add <specific paths>` — never `git add -A` or `git add .` unless every modified file belongs to this one change.
4. `git diff --cached` — sanity-check what's about to be committed.
5. `git commit -m "<message>"` using the format below.

Do not accumulate multiple completed changes before committing. Commit as soon as the change is verified.

## Pre-commit checks (must all pass)

Run these before every `git commit`. If any fails, do not commit — fix it or revert.

```bash
# Build
<fill in: e.g. npm run build / cargo build / go build ./...>
# Tests
<fill in: e.g. npm test / pytest / cargo test>
# Lint
<fill in: e.g. npm run lint / ruff check . / golangci-lint run>
# Type check (if applicable)
<fill in: e.g. tsc --noEmit / mypy .>
```

If a check is slow, run the narrowest version relevant to the change (e.g. tests for the affected package), but at minimum the type/lint checks must run on the whole project.

## Commit message format

Use Conventional Commits:

```
<type>(<scope>): <imperative summary, no trailing period>

<optional body explaining *why*, wrapped at 72 chars>

<optional footer: Closes #123, BREAKING CHANGE: ...>
```

`type` ∈ `feat` `fix` `refactor` `perf` `test` `docs` `build` `chore` `ci`.

Examples:
- `feat(auth): add password reset endpoint`
- `fix(parser): handle empty input without panicking`
- `refactor(db): extract connection pool into separate module`

Write the summary in the imperative ("add", not "added" or "adds"). The body explains motivation; the diff already shows what changed.

## Do not

- ❌ Do not run `git push`. All commits stay local; the user pushes when they're ready.
- ❌ Do not amend or rebase commits that have already been made in this session unless explicitly asked.
- ❌ Do not commit failing builds, failing tests, or lint errors.
- ❌ Do not commit commented-out code, leftover `print` / `console.log` / `dbg!`.
- ❌ Do not commit secrets, `.env` files, local IDE config, or generated artifacts that aren't already tracked.
- ❌ Do not mix formatting changes with logic changes in the same commit.
- ❌ Do not batch unrelated changes. If you notice an unrelated issue while working, finish the current commit first, then address the other issue as its own commit.

## When in doubt

If you're unsure whether two changes should be one commit or two: make them two. Smaller commits are almost always the right call — they're easier to review, bisect, and revert.

If verification can't be run for some reason (missing dependency, broken environment), stop and tell the user instead of committing unverified code.