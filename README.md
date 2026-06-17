# robotsix-yaml-config

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
| `overlay_env_vars(config, prefix, type_hints=None) -> dict` | Overlay `{PREFIX}_{KEY.upper()}` env vars onto existing keys with type coercion. Mutates and returns `config`. |

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

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.
In short:

```sh
uv sync --extra dev
uv run pytest
```
