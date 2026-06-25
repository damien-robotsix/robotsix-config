# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
