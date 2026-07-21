"""Typed errors for robotsix-config."""

from __future__ import annotations


class ConfigError(Exception):
    """Base error for all configuration failures."""


class InvalidConfigError(ConfigError):
    """The config file is not valid JSON, not a JSON object, or fails to
    validate against the model.
    """


__all__ = ["ConfigError", "InvalidConfigError"]
