# Changelog

All notable changes to this project will be documented in this file.

<!-- towncrier release notes start -->

## 0.0.0 (unreleased)

- Add `security`, `auto-release`, and `baseline-check` reusable workflow jobs to CI, pinned to `damien-robotsix/robotsix-github-workflows` at current main HEAD
- Pin all pre-commit hook `rev:` values to immutable commit SHAs (markdownlint-cli, zizmor, mirrors-mypy). Add missing fleet-standard hooks: `check-added-large-files`, `check-case-conflict`, `check-json`, `detect-private-key`, `actionlint`.
- Replace Renovate with Dependabot for dependency update automation (`.github/dependabot.yml` with pip, github-actions, and pre-commit ecosystems)
- Set up towncrier for changelog management: add `towncrier` dev dependency, `[tool.towncrier]` config with five fragment types (`feature`, `bugfix`, `doc`, `removal`, `misc`), and `changelog.d/` directory for per-change newsfragments.
- Fix `release-please-config.json` package-name from `robotsix-yaml-config` to `robotsix-config` to match `pyproject.toml`.
- Removed `MissingConfigError` — it was never raised in source code and was dead API surface.
- Remove the PyPI publish/release workflow — the stack is uv-git-source only, with no package index (see robotsix-standards).
- **Renamed `robotsix-yaml-config` → `robotsix-config` and rewritten clean
  (breaking; no backward compatibility).** The library is now a typed-config
  library built on **pydantic + JSON**, with **no YAML**: define one pydantic
  model, load it from **one JSON file** (`config/config.json` or
  `ROBOTSIX_CONFIG_FILE`), and emit a JSON Schema for the deploy UI. New API:
  `load_config`, `dump_config` (0600 JSON, secrets in cleartext),
  `config_schema` / `config_schema_json`, `resolve_config_path`, and
  `ConfigError` / `MissingConfigError` / `InvalidConfigError`. All YAML cascade
  primitives (`deep_merge`, `read_yaml_file`, `load_yaml_cascade`,
  `flatten_config`, `overlay_env_vars`) and the previous `schema` extra are
  **removed**; `pydantic` is now a core dependency and `pyyaml` is dropped.
- Add robotsix stack standards link to `README.md` and `AGENT.md`.
- Convert `_core` module from flat file to sub-package (`_core.py` → `_core/__init__.py`).
- Convert `_flatten` from flat `.py` file to sub-package (`_flatten.py` → `_flatten/__init__.py`).
- Move `_env` module source from flat `.py` file to package directory (`src/robotsix_yaml_config/_env.py` → `src/robotsix_yaml_config/_env/__init__.py`), aligning with the per-module layout already used by its docs and tests.
- Convert `_errors` module from flat file to sub-package (`src/robotsix_yaml_config/_errors.py` → `src/robotsix_yaml_config/_errors/__init__.py`)
- Add property-based hypothesis tests for ``flatten_config`` covering
  result-key correctness, empty alias maps, dict-valued stopping rule,
  identity-alias-map idempotence, reachable-key appearance, and
  unreachable-key silent drop.
- Added CodeQL SAST job to CI workflow for inter-procedural taint tracking (Python).
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Config-file location** (`_paths`): `resolve_config_path()`, `CONFIG_FILE_ENV`
  (`ROBOTSIX_CONFIG_FILE`), and `DEFAULT_CONFIG_PATH` — one standard config-file
  variable for the whole stack.
- **`0600` config writer** (`_io`): `write_config_file(path, data)` writes YAML
  with `0600` file / `0700` directory permissions for config holding secrets.
- **Schema layer** (optional `[pydantic]` extra, `robotsix_yaml_config.schema`):
  `load_config(model_cls, config_file=None)` loads **the one** YAML config file
  and validates it into a pydantic model — a single file is the only source of
  config values (**no environment overlay, no CLI-merge**); the model's field
  defaults fill the gaps, and `ROBOTSIX_CONFIG_FILE` only *locates* the file.
  `emit_deploy_schema(model_cls)` returns the model's typed **JSON Schema**
  (types, required, enums, defaults, `SecretStr` → `format: password` /
  `writeOnly`) for a deploy UI to render typed, validated inputs;
  `emit_deploy_schema_json` serializes it; `emit_deploy_template(model_cls)`
  emits a starter `config.yaml`. The core stays backend-agnostic (PyYAML only);
  pydantic is pulled only by this extra.
- Enable `content.code.copy` in mkdocs-material theme features for copy-to-clipboard on code blocks.

### Changed
- Update `docs-build` CI job to use Python 3.14 and `uv sync --locked --extra dev` instead of
  a Python 3.13 workaround with bare `uv pip install`, aligning it with all other CI jobs.
- Updated `CONTRIBUTING.md` supply-chain check example from `pip-audit` to `uv audit --frozen`,
  matching the actual CI pipeline.

### Added
- Add `validate-pyproject` pre-commit hook (with `validate-pyproject-schema-store[all]`) to validate `pyproject.toml` schema including tool-specific tables (ruff, mypy, pytest, coverage, etc.).
- Register project-level documentation files (`docs/api.md`, `docs/contributing.md`, `docs/index.md`, `docs/modules.yaml`, `docs/security.md`) in `docs/modules.yaml` under the `robotsix_yaml_config` module.
- Add `zizmor` pre-commit hook to audit GitHub Actions workflow files for security issues.
- Add `dependency-audit` job to CI that runs `uv audit --frozen` to scan for known vulnerabilities in dependencies.
- Add `watch` key to `mkdocs.yml` (watching `src/robotsix_yaml_config`) so `mkdocs serve` auto-rebuilds on source/docstring changes.

- Pinned all GitHub Actions in `.github/workflows/release.yml` to commit SHAs
  (`release-please-action`, `checkout`, `setup-uv`, `pypi-publish`) to close
  a supply-chain security gap.
- Pinned `cyclonedx-bom` version in `.github/workflows/release.yml` with a
  bounded range (`>=4,<5`) to ensure reproducible SBOM generation across
  releases.

- Added `Documentation` and `Changelog` URLs to `[project.urls]` in `pyproject.toml`
  for PyPI sidebar discoverability (PEP 753 well-known labels).
- Added `docs-build` CI job that runs `mkdocs build --strict` on Python 3.13
  on every push and pull request to catch broken documentation before merge.
- Converted `docs/contributing.md` to a snippet include of the root
  `CONTRIBUTING.md`, matching the pattern used by `docs/security.md`, so
  the published docs site shows the full contributing guide inline.
- Added `[tool.coverage.run]` and `[tool.coverage.report]` sections to
  `pyproject.toml`, enforcing `fail_under = 90` (aligned with CI threshold)
  and standard fleet settings (`branch = true`, `relative_files = true`,
  `source = ["robotsix_yaml_config"]`).
- Added `Security` page to the mkdocs documentation site, sourcing content
  from the repo-root `SECURITY.md` via `pymdownx.snippets`.

### Changed
- Added `--locked` flag to all `uv sync` calls in `.github/workflows/ci.yml` so CI
  validates the lockfile instead of silently re-resolving dependencies when it is stale.

### Deprecated

### Removed

### Fixed

### Security

## [0.1.0] — 2026-06-05

### Added

- `deep_merge` — recursive dict merge (lists replaced wholesale)
- `read_yaml_file` — parse a single YAML file to a dict (missing file → `{}`)
- `load_yaml_cascade` — load & deep-merge layered YAML files in precedence order
- `overlay_env_vars` — overlay typed env-var values (`{PREFIX}_{KEY.upper()}`) with coercion (`str`, `int`, `float`, `bool`)
- `flatten_config` — flatten a nested dict into a flat `{alias: value}` dict via a dotted-path alias map
- `YamlConfigError` — typed error for cascade failures, YAML parse errors, and non-dict top-level mappings

[Unreleased]: https://github.com/damien-robotsix/robotsix-yaml-config/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/damien-robotsix/robotsix-yaml-config/releases/tag/v0.1.0
