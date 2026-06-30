"""Tests for filesystem edge cases in read_yaml_file."""

import pytest

from robotsix_yaml_config import YamlReadError, read_yaml_file


@pytest.fixture
def symlink_file(tmp_path):
    """A symlink pointing to a valid YAML file."""
    target = tmp_path / "target.yaml"
    target.write_text("key: value\n", encoding="utf-8")
    link = tmp_path / "link.yaml"
    link.symlink_to(target)
    return link


@pytest.fixture
def broken_symlink_file(tmp_path):
    """A symlink pointing to a non-existent file."""
    link = tmp_path / "broken.yaml"
    link.symlink_to(tmp_path / "does_not_exist.yaml")
    return link


@pytest.fixture
def no_perm_file(tmp_path):
    """A YAML file with no read permission."""
    p = tmp_path / "secret.yaml"
    p.write_text("secret: true\n", encoding="utf-8")
    p.chmod(0o000)
    yield p
    p.chmod(0o644)  # allow cleanup


@pytest.fixture
def unicode_path_file(tmp_path):
    """A YAML file whose filename contains non-ASCII characters."""
    p = tmp_path / "über_config.yaml"
    p.write_text("locale: de\n", encoding="utf-8")
    return p


def test_read_yaml_file_symlink_to_real_file(symlink_file):
    """Following a symlink to a real YAML file should work."""
    assert read_yaml_file(symlink_file) == {"key": "value"}


def test_read_yaml_file_broken_symlink_returns_empty(broken_symlink_file):
    """A broken symlink (non-existent target) should return {}."""
    assert read_yaml_file(broken_symlink_file) == {}


def test_read_yaml_file_permission_denied(no_perm_file):
    """A file without read permission should raise YamlReadError."""
    with pytest.raises(YamlReadError, match="Failed to read"):
        read_yaml_file(no_perm_file)


def test_read_yaml_file_unicode_path(unicode_path_file):
    """A file with non-ASCII characters in its path should load correctly."""
    assert read_yaml_file(unicode_path_file) == {"locale": "de"}
