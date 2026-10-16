"""Root pytest configuration.

Keeps benchmarks disabled by default so test runs stay fast, without putting
``--benchmark-disable`` in a static ``addopts`` (which pytest would reject as
an unknown flag whenever the optional ``pytest-benchmark`` dev dependency is
not installed, breaking collection).
"""

from __future__ import annotations

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Default benchmarks to disabled when ``pytest-benchmark`` is installed.

    ``--benchmark-disable`` cannot live in a static ``addopts`` because
    ``pytest-benchmark`` is an optional dev dependency: pytest would reject the
    unknown flag (breaking collection) whenever the plugin is absent. Instead,
    flip the plugin's own ``benchmark_disable`` option on here when the user has
    not explicitly opted in with ``--benchmark-enable``. When the plugin is not
    installed the option does not exist and the benchmark tests skip themselves
    via ``pytest.importorskip``.
    """
    if not config.pluginmanager.hasplugin("benchmark"):
        return
    if config.getoption("benchmark_enable", default=False):
        return
    config.option.benchmark_disable = True
