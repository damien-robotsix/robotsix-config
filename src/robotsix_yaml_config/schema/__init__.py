"""Pydantic schema layer (optional ``[pydantic]`` extra).

Adds the robotsix stack config *conventions* on top of the dict primitives, for
components that want a typed, validated config model:

- :func:`load_config` — load **the one** YAML config file and validate it into a
  pydantic model. Config values come from a single file; there is no environment
  overlay and no CLI-merge. The model's own field defaults fill anything the
  file omits.
- :func:`emit_deploy_schema` — the model's **JSON Schema** (types, required,
  enums, defaults, secret marking) so a deploy UI can render typed, validated
  inputs and reject wrong types before deploy.
- :func:`emit_deploy_template` — a starter ``config.yaml`` with defaults and
  empty secret slots.

Install it via the extra::

    uv add "robotsix-yaml-config[pydantic]"
    from robotsix_yaml_config.schema import load_config, emit_deploy_schema

Secrets are declared with :class:`pydantic.SecretStr`: masked on read, and
rendered in the JSON Schema as
``{"type": "string", "format": "password", "writeOnly": true}``.
"""

from __future__ import annotations

import json
import os
import typing
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, SecretStr

from .._core import read_yaml_file
from .._paths import resolve_config_path


def load_config[ModelT: BaseModel](
    model_cls: type[ModelT],
    config_file: str | os.PathLike[str] | None = None,
) -> ModelT:
    """Load **the one** config file and validate it into *model_cls*.

    Config values come from exactly one YAML file — the one at *config_file*
    when given, else :func:`~robotsix_yaml_config.resolve_config_path` (the
    ``ROBOTSIX_CONFIG_FILE`` variable, or ``config/config.yaml`` by default).
    **A single file is the only source of config values** — there is no
    environment overlay and no CLI-merge, so config can't drift across sources.
    The model's own field defaults fill anything the file omits; a missing file
    therefore means "all defaults" (and errors only if a field is required and
    undefaulted).

    ``ROBOTSIX_CONFIG_FILE`` only *locates* the file (for a mounted deploy); it
    never carries config values.
    """
    path = Path(config_file) if config_file is not None else resolve_config_path()
    return model_cls.model_validate(read_yaml_file(path))


def emit_deploy_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Return *model_cls*'s JSON Schema, for a deploy UI to render typed inputs.

    The schema encodes each field's type, whether it is required, its enum
    values, defaults, and nested structure — enough for a deploy UI to render
    typed, validated inputs (number field, checkbox, enum dropdown, masked
    secret) and reject wrong types before deploy. Secret fields
    (:class:`pydantic.SecretStr`) appear as
    ``{"type": "string", "format": "password", "writeOnly": true}``.

    Commit the emitted schema as ``config/config.schema.json`` and keep it in
    sync with the model in CI.
    """
    return model_cls.model_json_schema()


def emit_deploy_schema_json(model_cls: type[BaseModel], *, indent: int = 2) -> str:
    """Return :func:`emit_deploy_schema` serialized as a JSON string (trailing
    newline), suitable for writing to ``config/config.schema.json``."""
    return json.dumps(emit_deploy_schema(model_cls), indent=indent) + "\n"


# --------------------------------------------------------------------------- #
#  Deploy-template emitter (starter config.yaml with defaults + secret slots)  #
# --------------------------------------------------------------------------- #

_TYPE_PLACEHOLDERS: dict[type, Any] = {str: "", int: 0, float: 0.0, bool: False}


def _is_secret(annotation: Any) -> bool:
    if annotation is SecretStr:
        return True
    return SecretStr in typing.get_args(annotation)


def _model_of(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for arg in typing.get_args(annotation):
        if isinstance(arg, type) and issubclass(arg, BaseModel):
            return arg
    return None


def _placeholder(annotation: Any) -> Any:
    origin = typing.get_origin(annotation)
    if origin in (list, set, tuple):
        return []
    if origin is dict:
        return {}
    if isinstance(annotation, type):
        return _TYPE_PLACEHOLDERS.get(annotation)
    for arg in typing.get_args(annotation):
        if arg is type(None):
            continue
        return _placeholder(arg)
    return None


def _coerce_default(value: Any) -> Any:
    if isinstance(value, SecretStr):
        return ""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {k: _coerce_default(v) for k, v in value.model_dump().items()}
    return value


def _model_to_template(model_cls: type[BaseModel]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        key = field.alias or name
        annotation = field.annotation

        if _is_secret(annotation):
            out[key] = ""  # secret slot — operator fills it
            continue

        nested = _model_of(annotation)
        if nested is not None:
            out[key] = _model_to_template(nested)
            continue

        if field.is_required():
            out[key] = _placeholder(annotation)
        else:
            out[key] = _coerce_default(field.get_default(call_default_factory=True))
    return out


def emit_deploy_template(model_cls: type[BaseModel]) -> str:
    """Return a starter ``config/config.yaml`` for *model_cls*.

    Secret fields (``SecretStr``) become empty-string slots; everything else
    carries its default (or a type-appropriate placeholder when required).
    Nested models become nested mappings. Useful for local dev; the deploy UI
    uses :func:`emit_deploy_schema` instead.
    """
    data = _model_to_template(model_cls)
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)


__all__ = [
    "load_config",
    "emit_deploy_schema",
    "emit_deploy_schema_json",
    "emit_deploy_template",
]
