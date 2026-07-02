"""Overlay environment variables onto a config dict.

Two overlay strategies:

- :func:`overlay_env_vars` — flat, typed overlay onto **existing** top-level
  keys (``{PREFIX}_{KEY}``). Values are coerced via ``type_hints``.
- :func:`overlay_env_nested` — build a **nested** overlay from
  ``{PREFIX}_{A}__{B}`` variables and deep-merge it in. Values stay strings;
  coercion is left to a downstream validator (e.g. pydantic). This is the
  overlay used by the schema layer.
"""

from __future__ import annotations

import os
from typing import Any

from .._core import deep_merge

# Case-insensitive truthy/falsy spellings for bool coercion.  A raw
# ``bool(value)`` is WRONG because ``bool("false")`` is ``True``.
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


def _coerce(value: str, hint: type) -> Any:
    """Coerce the string env *value* to the type given by *hint*."""
    if hint is bool:
        lowered = value.strip().lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
        # Fall back to truthy parse for unrecognised spellings.
        return bool(lowered)
    if hint is int:
        return int(value)
    if hint is float:
        return float(value)
    # ``str`` (and any unhandled hint) → value unchanged.
    return value


def overlay_env_vars(
    config: dict[str, Any],
    prefix: str,
    type_hints: dict[str, type] | None = None,
) -> dict[str, Any]:
    """Overlay ``{PREFIX}_{KEY.upper()}`` env vars onto *config*.

    For each key already present in *config*, look up the env var named
    ``f"{prefix}_{key.upper()}"``.  If it is set, coerce its string value
    using ``type_hints.get(key)`` (defaulting to ``str`` when absent or
    when *type_hints* is ``None``) and overwrite ``config[key]``.  Keys
    that are not already in *config* are never added.  Mutates and
    returns *config*.
    """
    hints = type_hints or {}
    for key in config:
        env_name = f"{prefix}_{key.upper()}"
        if env_name in os.environ:
            hint = hints.get(key, str)
            config[key] = _coerce(os.environ[env_name], hint)
    return config


def overlay_env_nested(
    config: dict[str, Any],
    prefix: str,
    *,
    delimiter: str = "__",
) -> dict[str, Any]:
    """Overlay ``{PREFIX}_{PATH}`` env vars, building a nested structure.

    Every environment variable whose name starts with *prefix* (a single
    ``_`` is appended if absent) contributes a value: the remainder of the
    name is lower-cased and split on *delimiter* into a nested path. A single
    ``_`` stays part of a segment, so ``ROBOTSIX_MAIL_LOG_LEVEL`` sets
    ``config["log_level"]`` while ``ROBOTSIX_MAIL_IMAP__HOST`` sets
    ``config["imap"]["host"]``.

    Unlike :func:`overlay_env_vars`, this **adds** nested keys (it does not
    require them to pre-exist) and leaves values as **strings** — coercion is
    the downstream validator's job (e.g. pydantic during ``model_validate``).
    Mutates and returns *config*.
    """
    marker = prefix if prefix.endswith("_") else prefix + "_"
    overlay: dict[str, Any] = {}
    for name, value in os.environ.items():
        if not name.startswith(marker):
            continue
        path = name[len(marker) :].lower().split(delimiter)
        cursor = overlay
        for segment in path[:-1]:
            existing = cursor.get(segment)
            if not isinstance(existing, dict):
                existing = {}
                cursor[segment] = existing
            cursor = existing
        cursor[path[-1]] = value
    return deep_merge(config, overlay)
