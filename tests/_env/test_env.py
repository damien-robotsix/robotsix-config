"""Tests for overlay_env_vars."""

from __future__ import annotations

from robotsix_yaml_config import overlay_env_vars
from robotsix_yaml_config._env import _TRUE_VALUES, _FALSE_VALUES


def test_overlay_prefix_lookup_hits(app_env):
    app_env(host="example.com")
    config = {"host": "localhost"}
    result = overlay_env_vars(config, "APP")
    assert result == {"host": "example.com"}
    assert result is config


def test_overlay_str_default_unchanged_value(app_env):
    app_env(name="mill")
    config = {"name": "default"}
    # No type hint → str → value used verbatim.
    assert overlay_env_vars(config, "APP") == {"name": "mill"}


def test_overlay_int_coercion(app_env):
    app_env(port="8080")
    config = {"port": 3000}
    result = overlay_env_vars(config, "APP", {"port": int})
    assert result == {"port": 8080}
    assert isinstance(result["port"], int)


def test_overlay_float_coercion(app_env):
    app_env(ratio="0.25")
    config = {"ratio": 1.0}
    result = overlay_env_vars(config, "APP", {"ratio": float})
    assert result == {"ratio": 0.25}


def test_overlay_bool_false_string(app_env):
    app_env(debug="false")
    config = {"debug": True}
    result = overlay_env_vars(config, "APP", {"debug": bool})
    assert result == {"debug": False}


def test_overlay_bool_truthy_spellings(app_env):
    for raw in _TRUE_VALUES | {"TRUE", "On"}:
        app_env(flag=raw)
        config = {"flag": False}
        result = overlay_env_vars(config, "APP", {"flag": bool})
        assert result == {"flag": True}, raw


def test_overlay_bool_falsy_spellings(app_env):
    for raw in _FALSE_VALUES | {"FALSE"}:
        app_env(flag=raw)
        config = {"flag": True}
        result = overlay_env_vars(config, "APP", {"flag": bool})
        assert result == {"flag": False}, raw


def test_overlay_unset_leaves_config_unchanged(monkeypatch):
    monkeypatch.delenv("APP_HOST", raising=False)
    config = {"host": "localhost", "port": 3000}
    result = overlay_env_vars(config, "APP", {"port": int})
    assert result == {"host": "localhost", "port": 3000}


def test_overlay_does_not_add_missing_keys(app_env):
    app_env(extra="value")
    config = {"host": "localhost"}
    result = overlay_env_vars(config, "APP")
    assert result == {"host": "localhost"}
    assert "extra" not in result


def test_overlay_uppercases_key(app_env):
    # config key is lowercase; env var must be the uppercased form.
    app_env(data_dir="/data")
    config = {"data_dir": "/tmp"}
    assert overlay_env_vars(config, "APP") == {"data_dir": "/data"}
