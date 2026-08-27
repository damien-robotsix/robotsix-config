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

## Legacy key migration

`load_config` strips config keys the model no longer declares (self-healing) and
logs a `WARNING` for each. That protects a component from crash-looping on a
config written for an older schema — but on its own it *discards the value*.

To carry a removed key's value to its canonical home, declare a
`migrate_legacy_config` classmethod on the model:

```python
from robotsix_config import ConfigModel


class Settings(ConfigModel):
    new_home: str = ""

    @classmethod
    def migrate_legacy_config(cls, data: dict) -> dict:
        legacy = data.pop("old_home", None)
        if legacy and not data.get("new_home"):
            data["new_home"] = legacy
        return data
```

It is called on the raw file contents **before** stripping. That ordering is the
whole point: a migration written as a pydantic `@model_validator(mode="before")`
runs inside `model_validate`, which `load_config` only reaches *after* the
unknown key has already been stripped — so the value is gone before the
migration can read it, with only a `WARNING` to show for it.

Two requirements:

- **Be idempotent.** `load_config` persists the cleaned config, so the hook is
  re-run against its own output on every later start.
- **Let an explicit value win.** Guard with `if not data.get("new_home")` so a
  value the operator set deliberately is never clobbered by a stale legacy one.

A hook that raises, or returns something other than a `dict`, is ignored with a
`WARNING` and the unmigrated config is loaded — refusing to load would turn a
bad migration into an unbootable component.

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
