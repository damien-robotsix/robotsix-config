"""Tests for the exception hierarchy / backward compatibility."""

from __future__ import annotations

import pytest

from robotsix_yaml_config import (
    MissingConfigError,
    YamlConfigError,
    load_yaml_cascade,
    read_yaml_file,
)


def test_parse_error_still_catchable_as_base(bad_yaml_file):
    with pytest.raises(YamlConfigError, match="YAML parse error"):
        read_yaml_file(bad_yaml_file)


def test_oserror_still_catchable_as_base(non_file_path):
    with pytest.raises(YamlConfigError, match="Failed to read"):
        read_yaml_file(non_file_path)


def test_non_dict_still_catchable_as_base(list_yaml_file):
    with pytest.raises(YamlConfigError, match="Expected a mapping"):
        read_yaml_file(list_yaml_file)


def test_missing_required_still_catchable_as_base(tmp_path):
    with pytest.raises(YamlConfigError, match="Required config file not found"):
        load_yaml_cascade([(tmp_path / "missing.yaml", True)])


def test_missing_required_catchable_as_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_yaml_cascade([(tmp_path / "missing.yaml", True)])


def test_missing_config_error_lineage():
    assert issubclass(MissingConfigError, FileNotFoundError)
    assert issubclass(MissingConfigError, YamlConfigError)
