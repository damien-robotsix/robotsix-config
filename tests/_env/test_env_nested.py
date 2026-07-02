"""Tests for overlay_env_nested."""

from __future__ import annotations

from robotsix_yaml_config import overlay_env_nested


def test_adds_top_level_key(monkeypatch):
    monkeypatch.setenv("ROBOTSIX_MAIL_LOG_LEVEL", "debug")
    config: dict = {}
    result = overlay_env_nested(config, "ROBOTSIX_MAIL")
    assert result == {"log_level": "debug"}
    assert result is config


def test_single_underscore_stays_in_segment(monkeypatch):
    # log_level is one field, not nested log.level.
    monkeypatch.setenv("ROBOTSIX_MAIL_LOG_LEVEL", "warning")
    assert overlay_env_nested({}, "ROBOTSIX_MAIL") == {"log_level": "warning"}


def test_double_underscore_nests(monkeypatch):
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__HOST", "mail.example.com")
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__PORT", "993")
    result = overlay_env_nested({}, "ROBOTSIX_MAIL")
    assert result == {"imap": {"host": "mail.example.com", "port": "993"}}


def test_deep_merges_over_existing(monkeypatch):
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__HOST", "env.example.com")
    config = {"imap": {"host": "file.example.com", "port": 993}, "log_level": "info"}
    result = overlay_env_nested(config, "ROBOTSIX_MAIL")
    assert result["imap"] == {"host": "env.example.com", "port": 993}  # port kept
    assert result["log_level"] == "info"


def test_prefix_normalized_without_trailing_underscore(monkeypatch):
    monkeypatch.setenv("ROBOTSIX_MAIL_X", "1")
    assert overlay_env_nested({}, "ROBOTSIX_MAIL") == {"x": "1"}


def test_prefix_boundary_not_greedy(monkeypatch):
    # ROBOTSIX_MAILBOX_* must NOT match the ROBOTSIX_MAIL_ prefix.
    monkeypatch.setenv("ROBOTSIX_MAILBOX_X", "leak")
    monkeypatch.setenv("ROBOTSIX_MAIL_Y", "ok")
    assert overlay_env_nested({}, "ROBOTSIX_MAIL") == {"y": "ok"}


def test_scalar_overwritten_by_nested(monkeypatch):
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__HOST", "h")
    config = {"imap": "was-a-string"}
    result = overlay_env_nested(config, "ROBOTSIX_MAIL")
    assert result == {"imap": {"host": "h"}}


def test_no_matching_vars_is_noop(monkeypatch):
    monkeypatch.delenv("ROBOTSIX_MAIL_X", raising=False)
    config = {"a": 1}
    assert overlay_env_nested(config, "ROBOTSIX_MAIL") == {"a": 1}
