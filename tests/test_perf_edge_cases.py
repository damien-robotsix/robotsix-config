"""Edge-case performance benchmarks for config load/dump/schema operations.

Complements ``test_perf_load.py`` (typical-case benchmarks) with boundary
conditions: empty and large payloads, the missing-file all-defaults fast path,
the dict-form schema, and schema generation for a deeply nested model.

Benchmarks are disabled by default (see the root ``conftest.py``) so CI test
runs stay fast. Enable and run them explicitly::

    uv run pytest --benchmark-enable tests/test_perf_*.py

See CONTRIBUTING.md ("Performance benchmarking") for details.
"""

from pathlib import Path

import pytest

# pytest-benchmark is an optional dev dependency; skip the whole module (which
# relies on its ``benchmark`` fixture) when it is not installed so collection
# stays green without the dev extra.
pytest.importorskip("pytest_benchmark")

from pydantic import Field, SecretStr

from robotsix_config import (
    ConfigModel,
    config_schema,
    config_schema_json,
    dump_config,
    load_config,
)


class _NestedEntry(ConfigModel):
    value: int = 0
    label: str = "entry"


class SampleConfig(ConfigModel):
    name: str = "sample-app"
    token: SecretStr = SecretStr("")
    retries: int = 3
    tags: list[str] = Field(default_factory=list)
    entries: list[_NestedEntry] = Field(default_factory=list)


class _DeepLevel3(ConfigModel):
    value: int = 0
    label: str = "level-3"


class _DeepLevel2(ConfigModel):
    name: str = "level-2"
    children: list[_DeepLevel3] = Field(default_factory=list)


class _DeepLevel1(ConfigModel):
    name: str = "level-1"
    children: list[_DeepLevel2] = Field(default_factory=list)


class DeeplyNestedConfig(ConfigModel):
    name: str = "deeply-nested-app"
    root: _DeepLevel1 = Field(default_factory=_DeepLevel1)
    siblings: list[_DeepLevel1] = Field(default_factory=list)


def _make_config(size: int) -> SampleConfig:
    """Build a config whose payload scales with ``size``."""
    return SampleConfig(
        name="benchmark-app",
        token=SecretStr("benchmark-secret"),
        retries=5,
        tags=[f"tag-{i}" for i in range(size)],
        entries=[_NestedEntry(value=i, label=f"entry-{i}") for i in range(size)],
    )


@pytest.mark.benchmark(group="load_config_edge")
def test_load_config_empty_benchmark(benchmark, tmp_path: Path) -> None:
    """Load an empty (size 0) payload."""
    path = tmp_path / "config.json"
    dump_config(_make_config(0), path)

    result = benchmark(load_config, SampleConfig, path)

    assert isinstance(result, SampleConfig)
    assert result.entries == []


@pytest.mark.benchmark(group="load_config_edge")
def test_load_config_large_benchmark(benchmark, tmp_path: Path) -> None:
    """Load a large (size 1000) payload."""
    path = tmp_path / "config.json"
    dump_config(_make_config(1000), path)

    result = benchmark(load_config, SampleConfig, path)

    assert isinstance(result, SampleConfig)
    assert len(result.entries) == 1000


@pytest.mark.benchmark(group="load_config_edge")
def test_load_config_missing_file_defaults_benchmark(benchmark, tmp_path: Path) -> None:
    """Load from a missing file, exercising the all-defaults fast path."""
    path = tmp_path / "missing.json"

    result = benchmark(load_config, SampleConfig, path)

    assert isinstance(result, SampleConfig)
    assert result.name == "sample-app"
    assert result.entries == []


@pytest.mark.benchmark(group="dump_config_edge")
def test_dump_config_empty_benchmark(benchmark, tmp_path: Path) -> None:
    """Dump an empty (size 0) payload."""
    cfg = _make_config(0)
    path = tmp_path / "config.json"

    result = benchmark(dump_config, cfg, path)

    assert result.exists()


@pytest.mark.benchmark(group="dump_config_edge")
def test_dump_config_large_benchmark(benchmark, tmp_path: Path) -> None:
    """Dump a large (size 1000) payload."""
    cfg = _make_config(1000)
    path = tmp_path / "config.json"

    result = benchmark(dump_config, cfg, path)

    assert result.exists()


@pytest.mark.benchmark(group="config_schema_edge")
def test_config_schema_dict_benchmark(benchmark) -> None:
    """Generate the dict-form schema."""
    result = benchmark(config_schema, SampleConfig)

    assert isinstance(result, dict)
    assert "properties" in result


@pytest.mark.benchmark(group="config_schema_edge")
def test_config_schema_deeply_nested_dict_benchmark(benchmark) -> None:
    """Generate the dict-form schema for a deeply nested model."""
    result = benchmark(config_schema, DeeplyNestedConfig)

    assert isinstance(result, dict)
    assert "properties" in result
    assert "$defs" in result


@pytest.mark.benchmark(group="config_schema_edge")
def test_config_schema_deeply_nested_json_benchmark(benchmark) -> None:
    """Generate the JSON-form schema for a deeply nested model."""
    result = benchmark(config_schema_json, DeeplyNestedConfig)

    assert isinstance(result, str)
    assert '"properties"' in result
