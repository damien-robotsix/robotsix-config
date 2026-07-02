"""Tests for the 0600/0700 config-file writer."""

from __future__ import annotations

import stat

import yaml

from robotsix_yaml_config import read_yaml_file, write_config_file


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_writes_file_0600_in_dir_0700(tmp_path):
    target = tmp_path / "nested" / "config.yaml"
    returned = write_config_file(target, {"a": 1, "secret": ""})
    assert returned == target
    assert target.is_file()
    assert _mode(target) == 0o600
    assert _mode(target.parent) == 0o700


def test_tightens_preexisting_lax_file(tmp_path):
    target = tmp_path / "config.yaml"
    target.write_text("old: 1\n", encoding="utf-8")
    target.chmod(0o644)  # simulate a world-readable pre-existing file
    write_config_file(target, {"new": 2})
    assert _mode(target) == 0o600


def test_content_round_trips(tmp_path):
    target = tmp_path / "config.yaml"
    payload = {"log_level": "info", "imap": {"host": "h", "port": 993}}
    write_config_file(target, payload)
    assert read_yaml_file(target) == payload
    # Written as a YAML mapping, not flow style.
    assert "log_level: info" in target.read_text(encoding="utf-8")


def test_preserves_key_order(tmp_path):
    target = tmp_path / "config.yaml"
    write_config_file(target, {"z": 1, "a": 2, "m": 3})
    loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert list(loaded.keys()) == ["z", "a", "m"]
