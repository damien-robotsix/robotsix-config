"""robotsix-yaml-config — backend-agnostic YAML configuration cascade.

Public API:

- ``YamlConfigError`` — base error type for cascade failures.
- ``MissingConfigError`` — required config file not found (also a
  ``FileNotFoundError``).
- ``YamlReadError`` — OS-level error reading a config file.
- ``YamlParseError`` — file is not valid YAML.
- ``InvalidConfigStructureError`` — YAML top level is not a mapping.
- ``deep_merge`` — recursive dict merge (lists replaced wholesale).
- ``read_yaml_file`` — parse a single YAML file to a dict.
- ``load_yaml_cascade`` — load & merge layered YAML files in order.
- ``flatten_config`` — flatten a nested dict via a dotted-path alias map.
- ``overlay_env_vars`` — overlay typed env-var values onto a flat dict.
"""

from __future__ import annotations

from ._core import deep_merge, load_yaml_cascade, read_yaml_file
from ._env import overlay_env_vars
from ._errors import (
    InvalidConfigStructureError,
    MissingConfigError,
    YamlConfigError,
    YamlParseError,
    YamlReadError,
)
from ._flatten import flatten_config

__all__ = [
    "YamlConfigError",
    "MissingConfigError",
    "YamlReadError",
    "YamlParseError",
    "InvalidConfigStructureError",
    "deep_merge",
    "read_yaml_file",
    "load_yaml_cascade",
    "flatten_config",
    "overlay_env_vars",
]
