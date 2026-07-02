"""Tests for the error hierarchy."""

from __future__ import annotations

from robotsix_config import ConfigError, InvalidConfigError, MissingConfigError


def test_hierarchy():
    assert issubclass(MissingConfigError, ConfigError)
    assert issubclass(InvalidConfigError, ConfigError)
    # MissingConfigError is also a FileNotFoundError for existing handlers.
    assert issubclass(MissingConfigError, FileNotFoundError)


def test_catchable_as_base():
    for exc in (MissingConfigError("x"), InvalidConfigError("y")):
        try:
            raise exc
        except ConfigError as caught:
            assert caught is exc
