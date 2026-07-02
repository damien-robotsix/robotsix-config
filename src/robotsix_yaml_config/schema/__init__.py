"""Pydantic schema layer (optional ``[pydantic]`` extra).

The core of ``robotsix-yaml-config`` is backend-agnostic dict primitives. This
module adds the robotsix stack *conventions* on top of them, for services that
want a typed, validated config model:

- :func:`load_config` — run the cascade (defaults -> file -> env -> overrides)
  and validate the merged dict into a pydantic model, with the fixed precedence
  and the single ``ROBOTSIX_CONFIG_FILE`` locate variable.
- :func:`emit_deploy_template` — generate the central-deploy ``config.yaml``
  template from the model (secret fields become empty slots).

Import it only when the ``pydantic`` extra is installed::

    uv add "robotsix-yaml-config[pydantic]"
    from robotsix_yaml_config.schema import load_config, emit_deploy_template

Secrets are declared with :class:`pydantic.SecretStr` (masked on read).
"""

from __future__ import annotations

import os
import typing
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, SecretStr

from .._core import deep_merge, read_yaml_file
from .._env import overlay_env_nested
from .._paths import resolve_config_path


def load_config[ModelT: BaseModel](
    model_cls: type[ModelT],
    *,
    env_prefix: str,
    config_file: str | os.PathLike[str] | None = None,
    defaults: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    env_delimiter: str = "__",
) -> ModelT:
    """Load, merge, and validate config into *model_cls*.

    Precedence (lowest -> highest): ``defaults`` < YAML file < ``{env_prefix}``
    environment overlay < ``overrides``. The YAML file is *config_file* when
    given, else :func:`~robotsix_yaml_config.resolve_config_path` (the
    ``ROBOTSIX_CONFIG_FILE`` variable or ``config/config.yaml``). The merged
    dict is validated with ``model_cls.model_validate`` — pydantic performs the
    type coercion for string-valued environment values.

    Parameters
    ----------
    model_cls:
        The pydantic model to validate into.
    env_prefix:
        Per-service prefix for the environment overlay, e.g. ``"ROBOTSIX_MAIL"``
        (``ROBOTSIX_MAIL_IMAP__HOST`` sets ``imap.host``).
    config_file:
        Explicit config path; overrides ``ROBOTSIX_CONFIG_FILE`` resolution.
    defaults:
        Base mapping merged below the file (optional).
    overrides:
        Highest-precedence mapping, e.g. parsed CLI flags (optional).
    env_delimiter:
        Nested-path delimiter in env var names (default ``"__"``).
    """
    path = Path(config_file) if config_file is not None else resolve_config_path()
    merged: dict[str, Any] = {}
    if defaults:
        deep_merge(merged, defaults)
    deep_merge(merged, read_yaml_file(path))
    overlay_env_nested(merged, env_prefix, delimiter=env_delimiter)
    if overrides:
        deep_merge(merged, overrides)
    return model_cls.model_validate(merged)


# --------------------------------------------------------------------------- #
#  Deploy-template emitter                                                    #
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
    """Return a central-deploy ``config/config.yaml`` template for *model_cls*.

    Secret fields (``SecretStr``) become empty-string slots; everything else
    carries its default (or a type-appropriate placeholder when required).
    Nested models become nested mappings.
    """
    data = _model_to_template(model_cls)
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)


__all__ = ["load_config", "emit_deploy_template"]
