"""Tests for the error hierarchy."""

from __future__ import annotations

import pytest

from robotsix_config import ConfigError, InvalidConfigError


def test_hierarchy():
    assert issubclass(InvalidConfigError, ConfigError)


def test_catchable_as_base():
    exc = InvalidConfigError("y")
    with pytest.raises(ConfigError) as caught:
        raise exc
    assert caught.value is exc
