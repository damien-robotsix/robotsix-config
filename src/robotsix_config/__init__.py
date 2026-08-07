"""robotsix-config — typed configuration for the robotsix stack.

Define your configuration as a pydantic model (subclass :class:`ConfigModel`),
load it from **one JSON file**, and emit a **JSON Schema** so a deploy UI can
render typed, validated inputs and so config is type-checked. No YAML, no
environment overlay, no cascade — one file is the single source of config values,
and the model's own field defaults fill the gaps.

Public API:

- ``ConfigModel`` — canonical base class for config models.
- ``load_config(model_cls, path=None)`` — load the one JSON file into the model.
- ``dump_config(model, path=None)`` — write the model to the ``0600`` JSON file
  (secrets in cleartext, for the app to read back).
- ``config_schema(model_cls)`` / ``config_schema_json(model_cls)`` — the model's
  JSON Schema for a deploy UI.
- ``resolve_config_path()`` / ``CONFIG_FILE_ENV`` / ``DEFAULT_CONFIG_PATH`` — the
  one file's location (``ROBOTSIX_CONFIG_FILE`` or ``config/config.json``).
- ``ConfigError`` / ``InvalidConfigError`` — error types.

A component owns its settings **and** their history. The history lives in a
``<config>.versions`` JSONL sidecar; see :mod:`robotsix_config.history`:

- ``apply_update(model_cls, update)`` — the whole of ``PUT /config``: deep-merge,
  preserve secrets the caller did not resubmit, validate, write, record.
- ``rollback(model_cls, version)`` — restore an earlier version as a new one.
- ``read_versions()`` / ``current_version()`` — inspect the history.
- ``mask_secrets(data, model_cls)`` — mask before returning config over HTTP.

Secrets are declared with :class:`pydantic.SecretStr`: masked on read, written
in cleartext into the ``0600`` file, and marked in the JSON Schema as
``{"type": "string", "format": "password", "writeOnly": true}``.
"""

from __future__ import annotations

from ._errors import ConfigError, InvalidConfigError
from .config import (
    CONFIG_FILE_ENV,
    DEFAULT_CONFIG_PATH,
    ConfigModel,
    config_schema,
    config_schema_json,
    dump_config,
    load_config,
    resolve_config_path,
)
from .history import (
    MASKED_SECRET_SENTINEL,
    apply_update,
    current_version,
    load_with_history,
    mask_secrets,
    read_versions,
    rollback,
    secret_paths,
    versions_path,
)

__all__ = [
    "CONFIG_FILE_ENV",
    "DEFAULT_CONFIG_PATH",
    "MASKED_SECRET_SENTINEL",
    "ConfigError",
    "ConfigModel",
    "InvalidConfigError",
    "apply_update",
    "config_schema",
    "config_schema_json",
    "current_version",
    "dump_config",
    "load_config",
    "load_with_history",
    "mask_secrets",
    "read_versions",
    "resolve_config_path",
    "rollback",
    "secret_paths",
    "versions_path",
]
