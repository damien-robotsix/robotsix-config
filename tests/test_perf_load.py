"""Performance benchmarks for config load/dump/schema operations.

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


def _make_config(size: int) -> SampleConfig:
    """Build a config whose payload scales with ``size``."""
    return SampleConfig(
        name="benchmark-app",
        token=SecretStr("benchmark-secret"),
        retries=5,
        tags=[f"tag-{i}" for i in range(size)],
        entries=[_NestedEntry(value=i, label=f"entry-{i}") for i in range(size)],
    )


@pytest.mark.benchmark(group="load_config")
@pytest.mark.parametrize("size", [1, 10, 100])
def test_load_config_benchmark(benchmark, tmp_path: Path, size: int) -> None:
    path = tmp_path / "config.json"
    dump_config(_make_config(size), path)

    result = benchmark(load_config, SampleConfig, path)

    assert isinstance(result, SampleConfig)
    assert len(result.entries) == size


@pytest.mark.benchmark(group="dump_config")
@pytest.mark.parametrize("size", [1, 10, 100])
def test_dump_config_benchmark(benchmark, tmp_path: Path, size: int) -> None:
    cfg = _make_config(size)
    path = tmp_path / "config.json"

    result = benchmark(dump_config, cfg, path)

    assert result.exists()


@pytest.mark.benchmark(group="config_schema_json")
def test_config_schema_json_benchmark(benchmark) -> None:
    result = benchmark(config_schema_json, SampleConfig)

    assert isinstance(result, str)
    assert '"properties"' in result
