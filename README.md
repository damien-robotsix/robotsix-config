# robotsix-yaml-config

Backend-agnostic primitives for a layered YAML configuration cascade:

1. Start from code-defined defaults.
2. Deep-merge one or more YAML config files in precedence order.
3. Overlay environment variables field-by-field (highest priority).
4. Flatten the nested dict into flat keyword arguments via a
   dotted-path alias map.

The package operates on plain dicts only — no pydantic, no
pydantic-settings — so it can be consumed by any configuration backend.

## Installation

This package is published to PyPI:

```bash
# Using pip
pip install robotsix-yaml-config

# Using uv (recommended for development)
uv add robotsix-yaml-config
```

**Python version:** requires Python 3.14 or later.

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

The four pipeline stages — code defaults, deep-merged YAML files, env
overlay, and flatten — compose like this:

```python
from pathlib import Path
from robotsix_yaml_config import (
    deep_merge,
    load_yaml_cascade,
    overlay_env_vars,
    flatten_config,
)

# 1. Code-defined defaults.
config = {"host": "localhost", "port": 5432, "debug": False}

# 2. Deep-merge YAML files in precedence order (later layers win).
#    Each layer is a (path, required) tuple: required-but-missing -> YamlConfigError;
#    optional-but-missing -> skipped.
file_config = load_yaml_cascade([
    (Path("defaults.yaml"), False),  # optional layer
    (Path("config.yaml"), True),     # required layer
])
deep_merge(config, file_config)      # mutates `config` in place, returns it

# 3. Overlay env vars onto existing top-level keys (highest priority).
#    Reads APP_HOST / APP_PORT / APP_DEBUG; coerces with type_hints.
#    e.g. `export APP_PORT=6543` -> config["port"] == 6543 (int)
overlay_env_vars(config, prefix="APP", type_hints={"port": int, "debug": bool})

# 4. Flatten into keyword arguments via a dotted-path alias map.
flat = flatten_config(config, alias_map={"host": "db_host", "port": "db_port"})
# flat == {"db_host": "localhost", "db_port": 6543}
```

Full API reference with per-symbol examples is available at
**[robotsix-yaml-config docs](https://damien-robotsix.github.io/robotsix-yaml-config)**.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.
In short:

```sh
uv sync --extra dev
uv run pytest
```
