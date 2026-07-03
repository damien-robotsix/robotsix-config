"""Tests for the error hierarchy."""

from __future__ import annotations

from robotsix_config import ConfigError, InvalidConfigError


def test_hierarchy():
    assert issubclass(InvalidConfigError, ConfigError)


def test_catchable_as_base():
    exc = InvalidConfigError("y")
    try:
        raise exc
    except ConfigError as caught:
        assert caught is exc
