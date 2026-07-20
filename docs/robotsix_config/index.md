# robotsix-config

Typed configuration for the robotsix stack. Define your configuration as a
**pydantic model**, load it from **one JSON file**, and emit a **JSON Schema**
so a deploy UI can render typed, validated inputs and so config is type-checked.

No YAML, no environment overlay, no cascade — **one file is the single source of
config values**, and the model's own field defaults fill the gaps.

## Quick start

```python
from pydantic import SecretStr
from robotsix_config import ConfigModel, load_config, dump_config, config_schema_json


class Config(ConfigModel):
    host: str = "localhost"
    port: int = 8080
    api_key: SecretStr = SecretStr("")


# Load the one file (ROBOTSIX_CONFIG_FILE or config/config.json) into the model.
cfg = load_config(Config)

# Emit the typed schema the deploy UI renders (commit as config/config.schema.json):
schema = config_schema_json(Config)

# Persist config back to the 0600 JSON file (secrets in cleartext for read-back):
dump_config(cfg)
```

## Model

- **Subclass `ConfigModel`.** The canonical base class for configuration models —
  a drop-in replacement for `pydantic.BaseModel` with no extra overhead.
  Declare secrets as `pydantic.SecretStr` fields: masked on ``repr()``, written
  in cleartext into the `0600` file by `dump_config`, and marked in the JSON
  Schema as `{"type": "string", "format": "password", "writeOnly": true}`.
- **One file.** `load_config` reads exactly one JSON file — `ROBOTSIX_CONFIG_FILE`
  or `config/config.json`. That variable only *locates* the file; it carries no
  values. No env overlay, no CLI-merge.
- **Defaults live in the model.** A missing file means "all defaults"; the file
  overrides only what it sets.
- **Typed schema.** `config_schema` / `config_schema_json` emit the model's JSON
  Schema (types, required, enums, defaults, secret marking) for the deploy UI.
- **`0600`/`0700` enforcement.** `dump_config` writes the config file with
  `0600` permissions (inside a `0700` directory). On rewrite it corrects
  existing misconfigured permissions, and the write is atomic
  (temp file + `os.replace`).

See the [API reference](api.md).
