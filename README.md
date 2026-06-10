# robotsix-yaml-config

Backend-agnostic primitives for a layered YAML configuration cascade:

1. Start from code-defined defaults.
2. Deep-merge one or more YAML config files in precedence order.
3. Overlay environment variables field-by-field (highest priority).
4. Flatten the nested dict into flat keyword arguments via a
   dotted-path alias map.

The package operates on plain dicts only — no pydantic, no
pydantic-settings — so it can be consumed by any configuration backend.

## Public API

| Symbol | Behaviour |
|---|---|
| `YamlConfigError(Exception)` | Raised for missing required files, YAML parse errors, non-dict top-level mappings. |
| `deep_merge(base, overlay) -> dict` | Recursively merge `overlay` into `base` (mutates `base`). Scalars overwrite; nested dicts recurse; lists/other are replaced wholesale via `deepcopy`. Returns `base`. |
| `read_yaml_file(path) -> dict` | Read & parse one YAML file. Missing file → `{}`. Parse error or non-dict top level → `YamlConfigError`. |
| `load_yaml_cascade(layers) -> dict` | Load & deep-merge `(path, required)` layers in order. A required-but-missing layer raises `YamlConfigError`. Later layers win. |
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

## Usage Examples

### End-to-end 4-step cascade

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

### Public-symbol examples

`YamlConfigError` — raised for missing required layers and parse errors:

```python
from pathlib import Path
from robotsix_yaml_config import YamlConfigError, load_yaml_cascade

try:
    load_yaml_cascade([(Path("must-exist.yaml"), True)])
except YamlConfigError as exc:
    print(f"config problem: {exc}")
```

`deep_merge(base, overlay)` — mutates and returns `base`; scalars
overwrite, nested dicts recurse, lists/other values are replaced
wholesale (never extended):

```python
from robotsix_yaml_config import deep_merge

base = {"db": {"host": "localhost", "port": 5432}, "tags": ["a"]}
overlay = {"db": {"port": 6543}, "tags": ["b"]}
deep_merge(base, overlay)
# base == {"db": {"host": "localhost", "port": 6543}, "tags": ["b"]}
# nested "db" merged key-by-key; "tags" list replaced wholesale
```

`read_yaml_file(path)` — missing file returns `{}`; parse error or
non-dict top level raises `YamlConfigError`:

```python
from pathlib import Path
from robotsix_yaml_config import read_yaml_file

data = read_yaml_file(Path("config.yaml"))   # dict, or {} if file is absent
```

`load_yaml_cascade(layers)` — `(path, required)` tuples merged in
order; later layers win:

```python
from pathlib import Path
from robotsix_yaml_config import load_yaml_cascade

merged = load_yaml_cascade([
    (Path("defaults.yaml"), False),  # optional: skipped if missing
    (Path("config.yaml"), True),     # required: raises if missing
])
```

`flatten_config(nested, alias_map)` — walks a nested dict, mapping
dotted paths through `alias_map`. Unknown paths are dropped and
dict-valued aliases are emitted as-is. There is NO separator argument —
the path separator is hard-coded to `.`:

```python
from robotsix_yaml_config import flatten_config

nested = {"db": {"host": "localhost", "port": 5432}, "extra": {"x": 1}}
flat = flatten_config(nested, alias_map={"db.host": "db_host", "db.port": "db_port"})
# flat == {"db_host": "localhost", "db_port": 5432}
# "extra.x" is unmapped, so it is dropped
```

`overlay_env_vars(config, prefix, type_hints=None)` — only keys already
present in `config` are overlaid, read from `f"{prefix}_{KEY.upper()}"`
and coerced via `type_hints`. Bool coercion is case-insensitive
(`"false"`/`"0"`/`"no"`/`"off"`/`""` → `False`):

```python
import os
from robotsix_yaml_config import overlay_env_vars

os.environ["APP_PORT"] = "6543"
os.environ["APP_DEBUG"] = "false"
config = {"host": "localhost", "port": 5432, "debug": True}
overlay_env_vars(config, prefix="APP", type_hints={"port": int, "debug": bool})
# config == {"host": "localhost", "port": 6543, "debug": False}
# APP_HOST is unset, so "host" is left untouched
```

### Example `config.yaml`

The keys below match the 4-step example; the nested `db` mapping
motivates `flatten_config`'s dotted-path alias map:

```yaml
host: localhost
port: 5432
debug: false
db:
  host: db.internal
  port: 5432
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.
In short:

```sh
uv sync --extra dev
uv run pytest
```
