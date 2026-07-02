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
- ``overlay_env_nested`` — overlay ``{PREFIX}_{A}__{B}`` env vars as a nested dict.
- ``write_config_file`` — write a dict as YAML with ``0600``/``0700`` perms.
- ``resolve_config_path`` / ``CONFIG_FILE_ENV`` / ``DEFAULT_CONFIG_PATH`` —
  the standard ``ROBOTSIX_CONFIG_FILE`` config-file location.

The optional ``[pydantic]`` extra adds ``robotsix_yaml_config.schema`` with
``load_config`` and ``emit_deploy_template`` (see that module). The core has no
framework dependency beyond PyYAML.
"""

from __future__ import annotations

from ._core import deep_merge, load_yaml_cascade, read_yaml_file
from ._env import overlay_env_nested, overlay_env_vars
from ._errors import (
    InvalidConfigStructureError,
    MissingConfigError,
    YamlConfigError,
    YamlParseError,
    YamlReadError,
)
from ._flatten import flatten_config
from ._io import write_config_file
from ._paths import CONFIG_FILE_ENV, DEFAULT_CONFIG_PATH, resolve_config_path

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
    "overlay_env_nested",
    "write_config_file",
    "resolve_config_path",
    "CONFIG_FILE_ENV",
    "DEFAULT_CONFIG_PATH",
]
