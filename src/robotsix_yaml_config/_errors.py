"""Error types for the YAML configuration cascade."""

from __future__ import annotations


class YamlConfigError(Exception):
    """Base for all YAML-config cascade failures."""


class MissingConfigError(YamlConfigError, FileNotFoundError):
    """A required config file was not found."""


class YamlReadError(YamlConfigError):
    """An OS-level error occurred while reading a config file."""


class YamlParseError(YamlConfigError):
    """The file is not valid YAML."""


class InvalidConfigStructureError(YamlConfigError):
    """The YAML top level is not a mapping."""
