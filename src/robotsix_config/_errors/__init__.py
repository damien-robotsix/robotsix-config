"""Typed errors for robotsix-config."""

from __future__ import annotations


class ConfigError(Exception):
    """Base error for all configuration failures."""


class MissingConfigError(ConfigError, FileNotFoundError):
    """A required config file was not found.

    Also a :class:`FileNotFoundError`, so existing ``except FileNotFoundError``
    handlers keep working.
    """


class InvalidConfigError(ConfigError):
    """The config file is not valid JSON, not a JSON object, or fails to
    validate against the model."""


__all__ = ["ConfigError", "MissingConfigError", "InvalidConfigError"]
