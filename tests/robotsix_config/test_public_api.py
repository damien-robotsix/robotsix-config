"""Snapshot test guarding the public API surface of ``robotsix_config``.

Adding, removing or renaming an exported symbol, or changing the signature of
a public function, must fail this test so the change is made explicitly (and
reviewed) by editing the snapshots below in the same PR.
"""

from __future__ import annotations

import inspect

import pytest

import robotsix_config

EXPECTED_ALL = [
    "CONFIG_FILE_ENV",
    "ConfigError",
    "ConfigModel",
    "DEFAULT_CONFIG_PATH",
    "InvalidConfigError",
    "MASKED_SECRET_SENTINEL",
    "PATH_WILDCARD",
    "apply_update",
    "config_schema",
    "config_schema_json",
    "current_version",
    "dump_config",
    "load_config",
    "load_with_history",
    "mask_secrets",
    "read_versions",
    "resolve_config_path",
    "rollback",
    "secret_paths",
    "versions_path",
]

_PATH_ARG = "'str | os.PathLike[str] | None' = None"

EXPECTED_SIGNATURES = {
    "apply_update": (
        f"(model_cls: 'type[BaseModel]', update: 'dict[str, Any]', "
        f"config_path: {_PATH_ARG}) -> 'tuple[dict[str, Any], list[str], int]'"
    ),
    "config_schema": "(model_cls: 'type[BaseModel]') -> 'dict[str, Any]'",
    "config_schema_json": (
        "(model_cls: 'type[BaseModel]', *, indent: 'int' = 2) -> 'str'"
    ),
    "current_version": f"(config_path: {_PATH_ARG}) -> 'int'",
    "dump_config": (
        f"(model: 'BaseModel', path: {_PATH_ARG}, *, indent: 'int' = 2) -> 'Path'"
    ),
    "load_config": f"(model_cls: 'type[ModelT]', path: {_PATH_ARG}) -> 'ModelT'",
    "load_with_history": (
        f"(model_cls: 'type[ModelT]', config_path: {_PATH_ARG}) -> 'tuple[ModelT, int]'"
    ),
    "mask_secrets": (
        "(data: 'dict[str, Any]', model_cls: 'type[BaseModel] | None' = None) "
        "-> 'dict[str, Any]'"
    ),
    "read_versions": (
        f"(config_path: {_PATH_ARG}, *, include_data: 'bool' = True) "
        "-> 'list[dict[str, Any]]'"
    ),
    "resolve_config_path": "() -> 'Path'",
    "rollback": (
        f"(model_cls: 'type[BaseModel]', target_version: 'int', "
        f"config_path: {_PATH_ARG}) -> 'tuple[dict[str, Any], list[str], int]'"
    ),
    "secret_paths": "(model_cls: 'type[BaseModel]') -> 'set[tuple[str, ...]]'",
    "versions_path": f"(config_path: {_PATH_ARG}) -> 'Path'",
}


def test_all_matches_snapshot() -> None:
    assert sorted(robotsix_config.__all__) == sorted(EXPECTED_ALL)


def test_every_public_function_has_a_signature_snapshot() -> None:
    functions = {
        name
        for name in robotsix_config.__all__
        if inspect.isfunction(getattr(robotsix_config, name))
    }
    assert functions == set(EXPECTED_SIGNATURES)


@pytest.mark.parametrize("name", sorted(EXPECTED_SIGNATURES))
def test_signature_matches_snapshot(name: str) -> None:
    func = getattr(robotsix_config, name)
    assert str(inspect.signature(func)) == EXPECTED_SIGNATURES[name]
