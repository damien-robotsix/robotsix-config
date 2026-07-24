# Contributing to robotsix-config

Thanks for your interest in contributing! This document describes how to
set up a development environment and run the same checks CI runs, so that
a change which passes locally also passes CI.

All commands use [`uv`](https://github.com/astral-sh/uv). CI installs the
project with `uv`, so using it locally keeps your environment in sync with
CI.

## Setup

1. Install `uv` (see the
   [astral-sh/uv install docs](https://github.com/astral-sh/uv#installation),
   or `pip install uv`).
2. Install the project together with its development dependencies:

   ```sh
   uv sync --extra dev
   ```

Python **3.14+** is required (`requires-python = ">=3.14"`). CI installs it
with `uv python install 3.14`; `uv` will pick up or provision a compatible
interpreter for you.

## Running tests

Run the test suite:

```sh
uv run pytest
```

To reproduce the coverage report CI produces:

```sh
uv run pytest --cov=src --cov-report=term-missing
```

## Code quality

CI runs the following checks; run them locally before pushing.

Lint:

```sh
uv run ruff check .
```

Format (CI enforces `uv run ruff format --check .`, so format locally
before pushing to avoid a CI failure):

```sh
uv run ruff format .
```

Type-check:

```sh
uv run mypy src tests
```

CI also runs supply-chain and dependency checks:

```sh
uv audit --frozen
uvx deptry src
```

Dead code:

```sh
uv run vulture src/
```

## Pre-commit

This repo ships a `.pre-commit-config.yaml`. Install the git hook with:

```sh
uv run pre-commit install
```

`pre-commit` is run via `uv run`/`uvx`, so you do not need a separate
global install.

Some hooks auto-fix files in place — ruff (`--fix`), `trailing-whitespace`,
and `end-of-file-fixer`. When a hook modifies a file, the commit is
aborted; review and commit the mechanical fixups before committing again.

## Pull requests

- Keep changes focused and scoped to a single concern.
- Make sure all of the CI checks above pass locally before opening a PR.
- The public API surface is backward-compatibility sensitive: changes to
  `__all__` in `src/robotsix_config/__init__.py` need care, since
  consumers rely on these exported symbols.

## Changelog entries

This project uses [towncrier](https://towncrier.readthedocs.io/) to
manage the changelog. Every pull request must include a changelog
fragment file in `changelog.d/`.

Fragments are plain text files named
`<ticket-id>.<fragment-type>.md` (e.g.
`20260701T120000Z-fix-login-timeout-a3f2.bugfix.md`). The file
contains a single line describing the change, prefixed with `- `:

```text
- Fixed a timeout bug in the login flow.
```

Available fragment types: `bugfix`, `feature`, `removal`,
`deprecation`, `misc`.

To check that your fragment is valid before pushing:

```sh
uv run towncrier check --compare-with origin/main
```

This command runs in CI on every pull request, so a missing or
malformed fragment will cause a CI failure. The fragment is
automatically collected into the changelog at release time.

## Releasing

Releases are automated via GitHub Actions:

1. **Semantic versioning:** The repository uses [release-please](https://github.com/googleapis/release-please-action) to automatically create release PRs based on [conventional commits](https://www.conventionalcommits.org/).
   - Commit messages like `feat: ...`, `fix: ...`, `BREAKING CHANGE: ...` trigger version bumps.
   - Release-please opens a PR with the new version, CHANGELOG updates, and tags.

2. **Release creation:** The `auto-release` reusable workflow (defined in `.github/workflows/ci.yml`) handles GitHub release creation automatically when a release-please PR is merged. There is no separate publish-to-PyPI step — the stack is uv-git-source only, with no package index.

Maintainers must ensure conventional commits are used so release-please correctly identifies version bumps.
