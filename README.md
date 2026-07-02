# robotsix-config

[![CI](https://img.shields.io/github/actions/workflow/status/damien-robotsix/robotsix-config/ci.yml?branch=main&label=CI)](https://github.com/damien-robotsix/robotsix-config/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/damien-robotsix/robotsix-config/docs.yml?branch=main&label=Docs)](https://github.com/damien-robotsix/robotsix-config/actions/workflows/docs.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Typed configuration for the robotsix stack. Define your configuration as a
**pydantic model**, load it from **one JSON file**, and emit a **JSON Schema**
so a deploy UI can render typed, validated inputs and so config is type-checked.

No YAML, no environment overlay, no cascade — **one file is the single source of
config values**, and the model's own field defaults fill the gaps.

See the **[full documentation](https://damien-robotsix.github.io/robotsix-config)**.

## Installation

```bash
uv add robotsix-config
```

Requires Python 3.14+.

## Public API

| Symbol | Behaviour |
|---|---|
| `load_config(model_cls, path=None) -> model` | Load **the one** JSON config file and validate it into the pydantic model. The file is the only source of config values — no env overlay, no CLI-merge; the model's field defaults fill the gaps. File located via `path` or `ROBOTSIX_CONFIG_FILE` (which only locates, never carries values). |
| `dump_config(model, path=None, *, indent=2) -> Path` | Write the model to the JSON config file with `0600` perms in a `0700` dir. `SecretStr` fields are written in **cleartext** (the app reads them back via `load_config`). |
| `config_schema(model_cls) -> dict` | The model's **JSON Schema** (types, required, enums, defaults, `SecretStr` → `format: password` / `writeOnly`) for a deploy UI. |
| `config_schema_json(model_cls, *, indent=2) -> str` | `config_schema` serialized to a JSON string — write to `config/config.schema.json`. |
| `resolve_config_path() -> Path` | The `ROBOTSIX_CONFIG_FILE` env var, or `config/config.json`. Also `CONFIG_FILE_ENV`, `DEFAULT_CONFIG_PATH`. |
| `ConfigError` / `MissingConfigError` / `InvalidConfigError` | Error hierarchy. `MissingConfigError` is also a `FileNotFoundError`. |

## Quick start

```python
from pydantic import BaseModel, SecretStr
from robotsix_config import load_config, dump_config, config_schema_json


class Config(BaseModel):
    host: str = "localhost"
    port: int = 8080
    api_key: SecretStr = SecretStr("")


cfg = load_config(Config)                 # one JSON file -> validated model
schema = config_schema_json(Config)       # commit as config/config.schema.json
dump_config(cfg)                          # persist to the 0600 config.json
```

## Standards

This repo follows the [robotsix stack standards](https://github.com/damien-robotsix/robotsix-standards).

## Development

```sh
uv sync --extra dev
uv run pytest
```
