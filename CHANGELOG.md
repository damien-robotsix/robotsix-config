# Changelog

All notable changes to this project will be documented in this file.

<!-- towncrier release notes start -->

0.2.0 (2026-08-08)

# Features

- Add `robotsix_config.history` — append-only version history for a component's own config file, so components own their settings *and* their setting history. `apply_update()` performs the whole of `PUT /config` (deep-merge, preserve secrets the caller did not resubmit, validate before writing, record a version), `rollback()` restores an earlier version as a new one, `read_versions()` inspects the history, and `mask_secrets()` masks before returning config over HTTP. Secret values are never written to the history — only that a secret-bearing key changed. Secrets are identified from the model's `SecretStr` fields rather than guessed from key names. (#20260807T233000Z-component-owned-config-history)

# Bug Fixes

- Grant `pull-requests: write` to the `auto-release` caller job in ci.yml — the pinned reusable workflow's `release` job requests it for the protected-branch PR fallback, and the missing grant made every CI run fail at startup ("The nested job 'release' is requesting 'pull-requests: write', but is only allowed 'pull-requests: none'") since early July. (#fix-ci-auto-release-permissions)
- Add the missing `[tool.uv.sources]` git pin for `robotsix-modules` (not on PyPI) and regenerate `uv.lock` — `uv sync` failed to resolve the dev extra in CI once the workflow parsed again. (#fix-uv-sources-robotsix-modules)
- Fix the `CI` workflow failing to start at all: the `baseline-check` reusable-workflow caller declared an empty `with: {}`, which GitHub rejects during workflow parsing. Combined with the invalid `timeout-minutes` keys removed separately, this had left the repository with no successful CI run since 2026-07-28. (#20260808T002500Z-ci-empty-with-startup-failure)
- Fix CI failures on main: update uvx build invocation for py.typed check, add uv ecosystem to dependabot, fix modules.yaml validation (IDs, descriptions, missing files), skip POSIX permission tests on Windows, fix path separator assertion. (#20260808T100610Z-ci-failure-ci-on-main-9d8f)
- Fixed two CI jobs that failed on every commit: Bandit flagged the `MASKED_SECRET_SENTINEL` mask as a hardcoded password (it carried a ruff `noqa` but no bandit `nosec`), and the schema-freshness check ran under the runner's system Python instead of `uv run`, so it died with `ModuleNotFoundError: No module named 'pydantic'`. (#20260808T111500Z-ci-bandit-and-schema-freshness)
- Moved `auto-release` out of `ci.yml` into its own weekly scheduled workflow, per changelog-driven-releases.md §4, and switched it to the fleet GitHub App (`app-id` / `app-private-key`) on the same reusable-workflow pin the rest of the fleet uses. As a per-push CI job on a stale pin it required a `release-token` secret this repo does not have, which is a startup failure that reds every run. (#20260808T112500Z-auto-release-to-scheduled-workflow)

# Miscellaneous

- #20260725T042008Z-robotsix-config-remove-dead-security-pos-d290, #20260713T051418Z-robotsix-config-recreate-docs-robotsix-c-a782, #20260722T073336Z-add-step-security-harden-runner-to-all-i-9a4c, #20260722T073336Z-remove-stale-keep-a-changelog-content-fr-44fc, #20260723T073822Z-add-openssf-scorecard-workflow-for-autom-89f0, #20260723T073822Z-remove-dead-types-pyyaml-dependency-from-9a1e, #20260723T073822Z-remove-stale-pypi-publishing-section-fro-df79, #20260724T074547Z-fix-stale-pypi-publishing-token-comment-e055, #20260724T074554Z-add-missing-docstring-to-read-json-priva-a054, #20260724T074554Z-enable-uv-malware-check-1-in-ci-setup-ac-7b11, #20260725T075029Z-add-tool-uv-exclude-newer-to-pyproject-t-eaf2, #20260726T075559Z-add-uv-malware-check-1-to-cross-platform-7854, #20260726T075559Z-replace-broken-mirrors-mypy-pre-commit-h-538f, #20260727T075934Z-add-locked-to-cross-platform-tests-uv-sy-d4c5, #20260720T080137Z-robotsix-config-enable-copy-paste-period-e6ed, #20260720T080137Z-robotsix-config-enable-survey-periodic-w-fae1, #20260704T080208Z-add-codeql-yml-using-shared-reusable-to-78a5, #20260704T080208Z-add-lint-workflows-yml-using-shared-reus-37ec, #20260704T080208Z-migrate-robotsix-config-docs-yml-to-shar-ac7b, #20260704T081334Z-remove-inline-codeql-sast-job-from-ci-ym-23d6, #20260728T082013Z-add-sarif-output-and-code-scanning-uploa-3a2e, #20260704T082204Z-ci-fix-out-of-scope-ci-failure-lint-zizm-ba03, #20260708T082420Z-add-set-frozenset-handling-to-reveal-wit-ed15, #20260704T083042Z-ci-fix-address-zizmor-excessive-permissi-23eb, #20260730T083854Z-fix-contributing-md-replace-nonexistent-5e9c, #20260730T083854Z-fix-mypy-type-arg-errors-from-bare-gener-955f, #20260731T084142Z-add-doc-to-the-fragment-type-list-in-con-5d09, #20260704T085008Z-ci-fix-out-of-scope-ci-failure-lint-zizm-ae0e, #20260801T085010Z-fix-dump-config-crash-on-models-with-set-3872, #20260803T090834Z-fix-ruff-lint-violations-unsorted-all-ru-b2fc, #20260720T091606Z-atomic-safe-writes-for-dump-config-using-0ac0, #20260805T093131Z-add-timeout-minutes-to-all-ci-jobs-to-pr-4519, #20260706T093150Z-deactivate-all-periodic-mill-workflows-k-f00e, #20260706T093635Z-deactivate-all-periodic-mill-workflows-k-fd79, #20260705T101248Z-robotsix-config-add-triage-boilerplate-p-c590, #20260721T101530Z-adopt-ruff-d-pydocstyle-rules-with-googl-3c50, #20260722T104928Z-enforce-changelog-fragments-in-ci-with-t-344a, #20260705T113001Z-triage-boilerplate-docker-503-sandbox-fa-e90a, #20260705T113001Z-triage-boilerplate-internal-only-doc-cla-5d2e, #20260723T113152Z-add-hypothesis-property-based-tests-for-4d5b, #20260803T115848Z-robotsix-config-enable-mypy-baseline-per-cae7, #20260803T115850Z-robotsix-config-enable-module-size-perio-d5cb, #20260724T122423Z-generate-and-attach-a-cyclonedx-sbom-to-ab38, #20260725T130720Z-add-macos-windows-ci-test-job-and-harden-dc73, #20260704T135836Z-missing-vulture-whitelist-py-breaks-pre-5801, #20260705T140446Z-bug-report-and-config-issue-templates-re-eef2, #20260704T141322Z-docs-yml-references-nonexistent-extra-do-9448, #20260704T141322Z-readme-md-and-docs-index-md-have-substan-82d8, #20260705T141621Z-docs-yml-permissions-deny-reusable-workf-5280, #20260705T141621Z-stale-references-to-old-project-name-rob-ead6, #20260801T142613Z-fix-contradictory-set-frozenset-assertio-be40, #20260706T143435Z-robotsix-config-adopt-robotsix-modules-f-468b, #20260706T143435Z-robotsix-config-enable-core-periodic-wor-ab78, #20260703T144842Z-add-security-auto-release-and-baseline-c-43ea, #20260703T144842Z-set-up-towncrier-for-changelog-managemen-4153, #20260703T145533Z-add-actionlint-to-ci-workflow-for-workfl-f503, #20260703T145533Z-upgrade-actions-dependency-review-action-6a45, #20260703T150716Z-ci-failure-docs-on-main-4e93, #20260703T150728Z-ci-add-json-schema-freshness-check-to-ke-da39, #20260706T151742Z-redundant-checkout-in-composite-setup-ac-48cc, #20260706T151742Z-stale-docs-robotsix-config-modules-yaml-a0ff, #20260804T155532Z-add-direct-unit-test-for-atomic-replace-3473, #20260804T161930Z-robotsix-config-enable-pin-bump-periodic-0d55, #20260703T162408Z-ci-failure-docs-on-main-7cd5, #20260802T163030Z-add-automated-py-typed-wheel-marker-guar-270b, #20260703T163932Z-ci-failure-docs-on-main-060c, #20260714T165300Z-robotsix-config-enable-baseline-periodic-fa11, #20260803T170924Z-adopt-pytest-warnings-as-errors-in-tool-cb24, #20260804T171434Z-make-mypy-a-blocking-gate-in-ci-for-robo-2019, #20260805T173005Z-enforce-agent-md-optional-dependency-imp-d0c3, #20260806T182930Z-mirror-ci-check-modules-in-the-local-pre-5529, #20260719T185310Z-robotsix-config-enable-audit-periodic-wo-365d, #20260719T185310Z-robotsix-config-enable-completeness-chec-2f5c, #20260719T185310Z-robotsix-config-enable-docstring-coverag-2c88, #20260719T185310Z-robotsix-config-enable-health-periodic-w-8bcc, #20260719T185310Z-robotsix-config-enable-module-curator-pe-244b, #20260719T185310Z-robotsix-config-enable-repo-description-ef20, #20260719T200051Z-reveal-silently-erases-tuple-type-use-ty-6b93, #20260704T201843Z-parametrize-error-path-tests-and-add-fix-a584, #20260720T202339Z-test-gap-add-unit-tests-for-scripts-chec-b673, #20260704T202927Z-reorganize-module-robotsix-config-align-94fd, #20260703T203034Z-enable-changelog-autofill-periodic-workf-0655, #20260807T203858Z-ci-failure-github-workflows-codeql-yml-o-54bb, #20260720T210036Z-consolidate-modules-config-scripts-merge-f72f, #20260806T222128Z-add-the-robotsix-modules-check-registrat-20e6, #20260722T223855Z-reorganize-module-config-align-to-per-mo-0da7, #20260720T225202Z-enforce-config-standard-for-secrets-in-s-985c, #20260720T225203Z-verify-provide-canonical-secret-conventi-8fb9, #20260719T232926Z-robotsix-config-enable-changelog-autofil-ad96


## [0.3.0](https://github.com/damien-robotsix/robotsix-config/compare/v0.2.0...v0.3.0) (2026-08-09)


### Features

* **release:** finish the release-please adoption ([#259](https://github.com/damien-robotsix/robotsix-config/issues/259)) ([31c540e](https://github.com/damien-robotsix/robotsix-config/commit/31c540ec1353c449bb1f03600d45954a86d52d45))


### Bug Fixes

* **uv:** drop the relative exclude-newer that made uv.lock unverifiable ([#258](https://github.com/damien-robotsix/robotsix-config/issues/258)) ([3cf8382](https://github.com/damien-robotsix/robotsix-config/commit/3cf8382d1805a1f1cf649ff537f01810f25fb9c7))

## 0.0.0 (unreleased)

- Align optional-dependency import enforcement with the fleet-wide deptry standard: the existing CI deptry gate (DEP004) catches optional/dev dependencies imported in production code. Test-file import-guard conventions are documented in AGENT.md.
- Add `robotsix-modules-check-registration` pre-commit hook to catch module-registration drift at commit time, mirroring the CI `check-modules` job.
- Enable `pin_bump` periodic in robotsix-config, matching every other fleet Python repo with a `uv.lock`.
- Adopt pytest `filterwarnings = ["error"]` to fail on warnings during test runs, matching the pydantic-ecosystem strictness baseline.
- robotsix-config: Enable mypy_baseline periodic workflow
- Enable `module_size` periodic scanner to detect oversized Python source files and propose split tickets.
- Fix three ruff lint violations: sort ``__all__`` in ``src/robotsix_config/__init__.py`` (RUF022), sort ``__all__`` in ``src/robotsix_config/config/__init__.py`` (RUF022), and remove shebang from non-executable ``scripts/check_schema_freshness.py`` (EXE001).
- Added `scripts/check_py_typed.py` guard and `check-py-typed` CI job that build the wheel and assert the `py.typed` marker is included, preventing silent type-information loss from packaging regressions.
- Fix four property tests in ``test_config_properties.py`` to assert list conversion for set/frozenset fields, matching the ``_reveal`` implementation introduced in #228.
- Fix `dump_config` crash on models with `set`/`frozenset` fields: `_reveal` now converts sets/frozensets to lists for JSON serialization
- Add `doc` to the fragment type list in `CONTRIBUTING.md`, matching the five types configured in `pyproject.toml`.
- Fixed `CONTRIBUTING.md` fragment type list: replaced nonexistent `deprecation` with `removal` to match the towncrier config in `pyproject.toml`.
- Harden ``dump_config`` for cross-platform safety: wrap ``os.chmod`` in
  ``try/except OSError`` (``0600`` is best-effort on Windows) and retry
  ``os.replace`` on ``PermissionError`` (antivirus / open-handle races).
  Added a ``macos-latest`` + ``windows-latest`` matrix job to CI.
- Add `[tool.uv] exclude-newer = "7d"` supply-chain hardening: prevents installation of packages published less than 7 days ago, closing the window before a CVE advisory can be published.
- Removed leftover `.robotsix-mill/periodic/security_posture.yaml` periodic workflow
  definition (the name `security_posture` is no longer valid).
- Add missing docstring to ``_read_json`` private helper in ``robotsix_config.config``.
- Update `CONTRIBUTING.md` "Releasing" section: replace stale PyPI publishing step with the actual `auto-release` workflow description (no publish-to-PyPI step exists).
- Fix YAML structural defect in `ci.yml`: move `changelog-check` job out of `ruff` job's mapping, restore `ruff` properties, remove duplicate setup step
- Moved `tests/scripts/` test files under `tests/config/scripts/` for per-module layout consistency.
- Add `hypothesis>=6` dev dependency and property-based tests for `_reveal()` and `dump_config`/`load_config` round-trip invariants.
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
