# robotsix-yaml-config

[![PyPI - Version](https://img.shields.io/pypi/v/robotsix-yaml-config.svg)](https://pypi.org/project/robotsix-yaml-config/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/robotsix-yaml-config.svg)](https://pypi.org/project/robotsix-yaml-config/)
[![CI](https://img.shields.io/github/actions/workflow/status/damien-robotsix/robotsix-yaml-config/ci.yml?branch=main&label=CI)](https://github.com/damien-robotsix/robotsix-yaml-config/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/damien-robotsix/robotsix-yaml-config/docs.yml?branch=main&label=Docs)](https://github.com/damien-robotsix/robotsix-yaml-config/actions/workflows/docs.yml)
[![codecov](https://codecov.io/gh/damien-robotsix/robotsix-yaml-config/branch/main/graph/badge.svg)](https://codecov.io/gh/damien-robotsix/robotsix-yaml-config)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Backend-agnostic primitives for a layered YAML configuration cascade:
start from code defaults, deep-merge YAML files, overlay environment
variables, and flatten into keyword arguments — all operating on plain
dicts with no framework lock-in.

See the **[full documentation](https://damien-robotsix.github.io/robotsix-yaml-config)**
for a detailed walkthrough of each pipeline stage.

## Installation

```bash
pip install robotsix-yaml-config
```

Requires Python 3.14 or later.

## Public API

| Symbol | Behaviour |
|---|---|
| `YamlConfigError(Exception)` | Base exception for cascade failures; all other exceptions inherit from this. |
| `MissingConfigError(YamlConfigError, FileNotFoundError)` | Raised when a required config file is not found. Also catchable as `FileNotFoundError`. |
| `YamlReadError(YamlConfigError)` | Raised on OS-level errors while reading a config file. |
| `YamlParseError(YamlConfigError)` | Raised on YAML syntax errors. |
| `InvalidConfigStructureError(YamlConfigError)` | Raised when the YAML top level is not a mapping. |
| `deep_merge(base, overlay) -> dict` | Recursively merge `overlay` into `base` (mutates `base`). Scalars overwrite; nested dicts recurse; lists/other are replaced wholesale via `deepcopy`. Returns `base`. |
| `read_yaml_file(path) -> dict` | Read & parse one YAML file. Missing file → `{}`. Raises `YamlReadError`, `YamlParseError`, or `InvalidConfigStructureError` on errors (all subclasses of `YamlConfigError`). |
| `load_yaml_cascade(layers) -> dict` | Load & deep-merge `(path, required)` layers in order. A required-but-missing layer raises `MissingConfigError`. Later layers win. |
| `flatten_config(nested, alias_map) -> dict` | Walk a nested dict, map each dotted path through `alias_map`, return a flat `{alias: value}` dict. Unknown paths dropped; dict-valued aliases emitted as-is. |
| `overlay_env_vars(config, prefix, type_hints=None) -> dict` | Overlay `{PREFIX}_{KEY.upper()}` env vars onto existing keys with type coercion. Mutates and returns `config`. Standalone primitive — the config standard does **not** use an env overlay. |
| `write_config_file(path, data) -> Path` | Write `data` as YAML with `0600` file / `0700` dir permissions (for config holding secrets). |
| `resolve_config_path() -> Path` | The `ROBOTSIX_CONFIG_FILE` env var, or `config/config.yaml` by default. Also `CONFIG_FILE_ENV`, `DEFAULT_CONFIG_PATH`. |

### Schema layer — optional `[pydantic]` extra

`robotsix_yaml_config.schema` (installed via `uv add "robotsix-yaml-config[pydantic]"`)
adds the robotsix stack config *conventions* on top of the dict primitives, for
services that want a typed, validated model. The core stays backend-agnostic
(PyYAML only); pydantic is pulled only by this extra.

| Symbol | Behaviour |
|---|---|
| `load_config(model_cls, config_file=None) -> model` | Load **the one** YAML config file and validate it into a pydantic model. A single file is the only source of config values — **no env overlay, no CLI-merge**; the model's field defaults fill the gaps. File located via `config_file` or `ROBOTSIX_CONFIG_FILE` (which only locates, never carries values). |
| `emit_deploy_schema(model_cls) -> dict` | The model's **JSON Schema** (types, required, enums, defaults, `SecretStr` → `format: password` / `writeOnly`) for a deploy UI to render typed, validated inputs. Commit as `config/config.schema.json`. |
| `emit_deploy_schema_json(model_cls, *, indent=2) -> str` | `emit_deploy_schema` serialized to a JSON string (trailing newline). |
| `emit_deploy_template(model_cls) -> str` | A starter `config/config.yaml` from the model; `SecretStr` fields become empty secret slots. |

### `overlay_env_vars` coercion

`type_hints.get(key)` selects the coercion (default `str`):

- `str` → value unchanged
- `int` → `int(value)`
- `float` → `float(value)`
- `bool` → case-insensitive: `{"1","true","yes","on"}` → `True`,
  `{"0","false","no","off",""}` → `False`. (A raw `bool(value)` is
  wrong because `bool("false")` is `True`.)

## Quick start

For the full quick-start example — code defaults, deep-merged YAML files,
env-var overlay, and flatten — see the
**[documentation](https://damien-robotsix.github.io/robotsix-yaml-config)**.

## Standards

This repo follows the [robotsix stack standards](https://github.com/damien-robotsix/robotsix-standards).

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.
In short:

```sh
uv sync --extra dev
uv run pytest
```
