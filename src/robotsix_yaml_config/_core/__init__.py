"""Core YAML cascade primitives: deep-merge, file reading, layered load.

Ported from the duplicated implementations in ``robotsix-mill`` and
``robotsix-auto-mail`` so both repos consume one source of truth.
"""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .._errors import (
    InvalidConfigStructureError,
    MissingConfigError,
    YamlParseError,
    YamlReadError,
)


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *overlay* into *base* (mutates *base*).

    For each key in *overlay*: if it already exists in *base* and both
    values are dicts, recurse; otherwise ``base[key]`` is replaced with
    a ``deepcopy`` of the overlay value.  Lists and other non-dict
    values are replaced wholesale (never extended).  Returns *base*.
    """
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base


def read_yaml_file(path: Path) -> dict[str, Any]:
    """Read and parse a single YAML file, returning a dict.

    Returns an empty dict for non-existent files.  Raises
    ``YamlReadError`` on OS-level read failures, ``YamlParseError`` on
    parse failures, and ``InvalidConfigStructureError`` for a non-dict
    top level (all subclasses of ``YamlConfigError``).
    """
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError as exc:
        raise YamlReadError(f"Failed to read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise YamlParseError(f"YAML parse error in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise InvalidConfigStructureError(
            f"Expected a mapping at top level of {path}, got {type(data).__name__}"
        )
    return data


def load_yaml_cascade(layers: Sequence[tuple[Path, bool]]) -> dict[str, Any]:
    """Load and deep-merge YAML files in order; later layers win.

    Each layer is a ``(path, required)`` tuple.  A required layer whose
    file is missing raises ``MissingConfigError`` (a subclass of
    ``YamlConfigError``) naming the file.  Optional
    layers whose files are missing are skipped.  Returns the fully merged
    dict (starting from an empty dict).
    """
    merged: dict[str, Any] = {}
    for path, required in layers:
        if not path.exists():
            if required:
                raise MissingConfigError(f"Required config file not found: {path}.")
            continue
        deep_merge(merged, read_yaml_file(path))
    return merged
