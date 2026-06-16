from __future__ import annotations

import pytest


@pytest.fixture
def bad_yaml_file(tmp_path):
    """A YAML file with a syntax error (unclosed bracket)."""
    p = tmp_path / "bad.yaml"
    p.write_text("a: [1, 2\n", encoding="utf-8")
    return p


@pytest.fixture
def list_yaml_file(tmp_path):
    """A valid YAML file whose top-level node is a list, not a mapping."""
    p = tmp_path / "list.yaml"
    p.write_text("- 1\n- 2\n", encoding="utf-8")
    return p


@pytest.fixture
def non_file_path(tmp_path):
    """A path that exists but is a directory, not a readable file."""
    p = tmp_path / "adir"
    p.mkdir()
    return p


@pytest.fixture
def app_env(monkeypatch):
    """Helper to set multiple APP_* env vars in one call."""

    def _set(**env_vars):
        for k, v in env_vars.items():
            monkeypatch.setenv(f"APP_{k.upper()}", v)

    return _set
