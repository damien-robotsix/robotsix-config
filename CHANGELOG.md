# Changelog

All notable changes to this project will be documented in this file.

<!-- towncrier release notes start -->

## 0.0.0 (unreleased)

- Remove stale keep-a-changelog section from CHANGELOG.md left behind when towncrier was adopted for changelog management.
- Adopt ruff D (pydocstyle) rules with Google convention; fix docstring gaps in public API functions.
- Add ``ConfigModel`` base class — the canonical way to define typed configuration.
  ``dump_config`` now writes the temp file with ``0600`` directly (instead of
  inheriting the target's previous mode), and directory ``0700`` permission
  enforcement is tested.
- Add CodeQL suppression for `py/clear-text-storage-sensitive-data` with justification referencing config-standard §3 (clear-text secrets in `config.json` are policy-accepted; mitigated by `SecretStr` masking + `0600`/`0700` file perms).
- Add unit tests for ``scripts/check_schema_freshness.py`` covering ``_import_model`` (success, ValueError, AttributeError) and ``main`` (fresh file, missing file, stale file).
- `dump_config` now writes atomically via a temp file + ``os.replace()``, preventing
  truncated or partially-written config files on crash or power loss.
- Enabled the `copy_paste` periodic workflow (jscpd-based copy-paste detection) for the repo.  Added `.robotsix-mill/periodic/copy_paste.yaml`.
- Enable `survey` periodic workflow with competitive-analysis agent.
- Added `changelog_autofill` periodic agent configuration.
- Add `.robotsix-mill/periodic/docstring_coverage.yaml` to enable automated docstring-coverage enforcement on the public API.
- Enable audit periodic scan for dependency vulnerability checking.
- Preserve tuple type in `_reveal()`: `tuple[SecretStr, ...]` model fields no longer silently convert to lists during `dump_config()` serialization
- Add `repo_description_sync` periodic agent configuration to keep forge description in sync with README.
- Enable baseline periodic workflows (test_gap, bc_check, security_posture) via `.robotsix-mill/periodic/` presence files.
- Recreate `docs/robotsix_config/modules.yaml` with the four-module taxonomy
  (`robotsix_config`, `config`, `_errors`, `tests`) that was validated in
  PR #174. All 19 paths are current.
- `_reveal()` now recursively reveals `SecretStr` values inside `set` and `frozenset` containers, matching the existing behaviour for `list`/`tuple`/`dict`.
- Deactivate all periodic mill workflows by removing every `.yaml` file under `.robotsix-mill/periodic/`.
- Remove stale `docs/robotsix_config/modules.yaml` — the module taxonomy file is no longer consumed by any build step.
- Adopt `robotsix-modules` for automated module taxonomy validation:
  added `robotsix-modules>=0.2.0` dev dependency, a `robotsix-modules-validate`
  pre-commit hook, and a `check-modules` CI job that validates
  `docs/robotsix_config/modules.yaml` and checks for unregistered files.
- Deactivate all periodic mill workflows by removing every `.yaml` file under `.robotsix-mill/periodic/`
- Update `CITATION.cff` title, description, and URL to match the renamed `robotsix-config` project.
- Updated GitHub issue templates: fixed stale `robotsix-yaml-config` URLs to `robotsix-config`, and replaced removed-component checkboxes with current feature names (load_config, dump_config, config_schema, resolve_config_path, error types).
- Add Docker 503 infrastructure outage boilerplate response to triage_boilerplate periodic workflow, documenting the pattern so triagers can consistently handle transient Docker Hub / registry unavailability.
- Add `triage_boilerplate` periodic workflow via `.robotsix-mill/periodic/triage_boilerplate.yaml` presence file, enabling the built-in triage boilerplate scanner to propose response templates for recurring triage patterns.
- Reorganize module documentation under `docs/robotsix_config/` — move `api.md`, `contributing.md`, `index.md`, `modules.yaml`, and `security.md` into the per-module subdirectory, matching the convention used by `config/` and `_errors/`.
- Parametrize error-path tests in `tests/config/test_config.py` into a single `test_invalid_config_raises` and add `write_config` fixture to `tests/conftest.py`.
- Remove content duplicated between `README.md` and `docs/index.md` — the docs landing page is now the canonical source for the description and quick-start example; `README.md` retains a minimal tagline + install + link to the full documentation.
- Added `docs` optional-dependencies group with mkdocs-material and mkdocstrings, fixing the docs workflow's `--extra docs` reference.
- Add `.github/workflows/lint-workflows.yml` using shared reusable workflow from `damien-robotsix/robotsix-github-workflows` pinned to commit `7314c9b6c2b536ca81023e8841f272b72733262e`, with `run-actionlint: true` and `run-zizmor: true` enabled.
- Enable changelog autofill periodic workflow to automate CHANGELOG.md entries from PR titles.
- Upgrade `actions/dependency-review-action` from v4.0.0 to v5.0.0 and tighten `fail-on-severity` from `high` to `moderate` to catch more vulnerabilities.
- Inline the Docs deployment workflow to fix GitHub Pages deployment failures caused by insufficient permissions in the reusable `python-docs.yml` workflow
- Add `scripts/check_schema_freshness.py` and a `check-schema` CI job to
  enforce that committed JSON Schema files stay in sync with their
  Pydantic models.
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
