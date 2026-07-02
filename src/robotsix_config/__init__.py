"""robotsix-config — typed configuration for the robotsix stack.

Define your configuration as a pydantic model, load it from **one JSON file**,
and emit a **JSON Schema** so a deploy UI can render typed, validated inputs and
so config is type-checked. No YAML, no environment overlay, no cascade — one
file is the single source of config values, and the model's own field defaults
fill the gaps.

Public API:

- ``load_config(model_cls, path=None)`` — load the one JSON file into the model.
- ``dump_config(model, path=None)`` — write the model to the ``0600`` JSON file
  (secrets in cleartext, for the app to read back).
- ``config_schema(model_cls)`` / ``config_schema_json(model_cls)`` — the model's
  JSON Schema for a deploy UI.
- ``resolve_config_path()`` / ``CONFIG_FILE_ENV`` / ``DEFAULT_CONFIG_PATH`` — the
  one file's location (``ROBOTSIX_CONFIG_FILE`` or ``config/config.json``).
- ``ConfigError`` / ``MissingConfigError`` / ``InvalidConfigError`` — error types.

Secrets are declared with :class:`pydantic.SecretStr`: masked on read, written
in cleartext into the ``0600`` file, and marked in the JSON Schema as
``{"type": "string", "format": "password", "writeOnly": true}``.
"""

from __future__ import annotations

from ._errors import ConfigError, InvalidConfigError, MissingConfigError
from .config import (
    CONFIG_FILE_ENV,
    DEFAULT_CONFIG_PATH,
    config_schema,
    config_schema_json,
    dump_config,
    load_config,
    resolve_config_path,
)

__all__ = [
    "ConfigError",
    "MissingConfigError",
    "InvalidConfigError",
    "load_config",
    "dump_config",
    "config_schema",
    "config_schema_json",
    "resolve_config_path",
    "CONFIG_FILE_ENV",
    "DEFAULT_CONFIG_PATH",
]
