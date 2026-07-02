"""Tests for the standard config-file location."""

from __future__ import annotations

from pathlib import Path

from robotsix_yaml_config import (
    CONFIG_FILE_ENV,
    DEFAULT_CONFIG_PATH,
    resolve_config_path,
)


def test_default_when_env_unset(monkeypatch):
    monkeypatch.delenv(CONFIG_FILE_ENV, raising=False)
    assert resolve_config_path() == DEFAULT_CONFIG_PATH
    assert DEFAULT_CONFIG_PATH == Path("config/config.yaml")


def test_env_overrides_default(monkeypatch, tmp_path):
    p = tmp_path / "custom.yaml"
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    assert resolve_config_path() == p


def test_config_file_env_name():
    assert CONFIG_FILE_ENV == "ROBOTSIX_CONFIG_FILE"
