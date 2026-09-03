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

## Commit messages and changelog

This project uses [release-please](https://github.com/googleapis/release-please-action) to automate releases and generate `CHANGELOG.md`. Release-please relies on [conventional commits](https://www.conventionalcommits.org/) to determine version bumps.

**Commit subjects and PR titles must follow the conventional commits format:**

- `feat: <description>` — new feature (triggers a minor version bump)
- `fix: <description>` — bug fix (triggers a patch version bump)
- `chore: <description>` — maintenance task
- `docs: <description>` — documentation only
- `refactor: <description>` — code refactoring
- `test: <description>` — test changes
- `ci: <description>` — CI/CD changes

A `BREAKING CHANGE:` footer in the commit body triggers a major version bump.

**Do not add changelog fragment files.** The changelog is generated automatically from commit messages at release time.

### Deprecation

The public API surface is backward-compatibility sensitive, so an API that
external consumers may depend on is never removed without advance warning.

**Lifecycle policy:** deprecate in release *N*, then remove in the next major
version bump (*N+1* major). This gives fleet consumers at least one release
cycle to migrate before a symbol disappears.

**When to deprecate:** any API change that affects external consumers —
renaming or removing an exported symbol (see `__all__` in
`src/robotsix_config/__init__.py`), changing a public function's signature, or
retiring a public code path. Internal helpers (underscore-prefixed modules and
names) may change freely.

**How to deprecate at runtime:** wrap the callable with the
`deprecated` decorator from `robotsix_config._deprecation`. It emits a
`DeprecationWarning` — naming the deprecation version, the planned removal
version, and optional migration guidance — every time the callable is invoked:

```python
from robotsix_config._deprecation import deprecated


@deprecated("0.7.0", "1.0.0", "Use new_function instead")
def old_function(): ...
```

**How to document deprecations:** add a Google-style `Deprecated:` block to the
callable's docstring (compatible with the repo's ruff `D` rules):

```python
def old_function():
    """Do the old thing.

    Deprecated:
        version 0.7.0: Use new_function instead. Will be removed in 1.0.0.
    """
```

**How to test deprecations:** add a test that asserts the
`DeprecationWarning` is emitted and that its message matches the decorator's
`message` argument. Because `pyproject.toml` sets
`filterwarnings = ["error"]`, capture the warning with `pytest.warns(...)` so
it does not escalate to an error. See
`tests/robotsix_config/test_deprecations.py` for examples.

**How to review deprecation PRs:** when reviewing a PR that introduces a
deprecation, maintainers should verify:

- The change genuinely needs a deprecation — it alters a public, exported
  symbol (see `__all__` in `src/robotsix_config/__init__.py`), a public
  function signature, or a public code path. Internal helpers
  (underscore-prefixed modules and names) may change freely and need no
  deprecation.
- The deprecated symbol emits a `DeprecationWarning` at runtime via the
  `deprecated` decorator from `robotsix_config._deprecation`.
- The `version` argument names the release in which the change ships (N), and
  `removed_in` names the next major release (N+1) per the lifecycle policy
  above — no removal scheduled within the same minor/major cycle as the
  deprecation.
- The callable's docstring carries a Google-style `Deprecated:` block naming
  the deprecation version and the replacement.
- Tests capture the warning with `pytest.warns(...)` and assert the message
  includes the deprecation/removal versions and any migration guidance.
- The deprecation itself is not a breaking change: the deprecated symbol's
  behavior is unchanged, and consumers have a working replacement path to
  migrate to.

A PR that **removes** a symbol deprecated in a previous release is only
acceptable in a major release, and only once the deprecation window (one
release cycle) has elapsed.

## Releasing

Releases are automated via GitHub Actions:

1. **Semantic versioning:** The repository uses [release-please](https://github.com/googleapis/release-please-action) to automatically create release PRs based on [conventional commits](https://www.conventionalcommits.org/).
   - Commit messages like `feat: ...`, `fix: ...`, `BREAKING CHANGE: ...` trigger version bumps.
   - Release-please opens a PR with the new version, CHANGELOG updates, and tags.

2. **Release creation:** The `auto-release` reusable workflow (defined in `.github/workflows/ci.yml`) handles GitHub release creation automatically when a release-please PR is merged. There is no separate publish-to-PyPI step — the stack is uv-git-source only, with no package index.

Maintainers must ensure conventional commits are used so release-please correctly identifies version bumps.
