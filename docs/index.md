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

See the [API Reference](api.md) for full documentation of every
public symbol.
