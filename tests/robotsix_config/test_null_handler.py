"""The package logger carries a NullHandler (library logging convention)."""

from __future__ import annotations

import logging
import subprocess
import sys
import textwrap
from pathlib import Path


def test_package_logger_has_null_handler() -> None:
    """Importing the package attaches a NullHandler to ``robotsix_config``."""
    import robotsix_config  # noqa: F401

    handlers = logging.getLogger("robotsix_config").handlers
    assert any(isinstance(h, logging.NullHandler) for h in handlers)


def test_unconfigured_app_sees_no_library_warnings_on_stderr() -> None:
    """Without app logging config, library warnings do not reach stderr.

    The lastResort stderr fallback is bypassed once a NullHandler is attached
    to the ``robotsix_config`` package logger; both the module loggers and
    the ``robotsix_config.history`` logger propagate to it.
    """
    code = textwrap.dedent(
        """
        import logging
        import robotsix_config
        logging.getLogger("robotsix_config.config").warning("self-heal warning")
        logging.getLogger("robotsix_config.history").warning("history warning")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stderr == ""


# A script that drives the real warning sites in
# ``robotsix_config.config`` (unknown-key strip, raising migration hook,
# non-dict migration return) through ``load_config``. ``{setup}`` is the
# consumer's logging configuration, run *after* importing the package.
_EMIT_REAL_WARNINGS = """
import json
import logging
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel

import robotsix_config
from robotsix_config import load_config

{setup}


class Strip(BaseModel):
    name: str = "svc"


class Raising(BaseModel):
    name: str = "svc"

    @classmethod
    def migrate_legacy_config(cls, data):
        raise RuntimeError("boom")


class BadReturn(BaseModel):
    name: str = "svc"

    @classmethod
    def migrate_legacy_config(cls, data):
        return "not a dict"


with tempfile.TemporaryDirectory() as tmp:
    for i, (model, data) in enumerate(
        (
            (Strip, {{"name": "x", "gone_key": 1}}),
            (Raising, {{"name": "x"}}),
            (BadReturn, {{"name": "x"}}),
        )
    ):
        path = Path(tmp) / f"config{{i}}.json"
        path.write_text(json.dumps(data))
        load_config(model, path)
"""

_EXPECTED_MESSAGES = (
    "Stripping unknown config key 'gone_key'",
    "migrate_legacy_config raised",
    "expected dict",
)


def _run(setup: str) -> subprocess.CompletedProcess[str]:
    code = _EMIT_REAL_WARNINGS.format(setup=textwrap.dedent(setup))
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )


def test_real_load_config_warnings_are_silent_without_logging_config() -> None:
    """The real self-heal / migration warnings produce no stderr output.

    Neither a configured handler nor the ``logging.lastResort`` fallback
    writes anything when the consumer never configures logging.
    """
    result = _run("")
    assert result.stderr == ""
    assert result.stdout == ""


def test_consumer_root_logging_config_still_receives_records() -> None:
    """A consumer that configures root logging still sees the warnings."""
    result = _run(
        """
        logging.basicConfig(
            stream=sys.stdout, level=logging.WARNING, format="%(name)s|%(message)s"
        )
        """
    )
    assert result.stderr == ""
    for message in _EXPECTED_MESSAGES:
        assert message in result.stdout
    assert "robotsix_config.config|" in result.stdout


def test_consumer_handler_on_package_logger_receives_records() -> None:
    """A handler attached directly to ``robotsix_config`` receives the records.

    The NullHandler stays in place alongside it, and each record is
    delivered exactly once (no duplicate output, nothing via lastResort).
    """
    result = _run(
        """
        _pkg = logging.getLogger("robotsix_config")
        _h = logging.StreamHandler(sys.stdout)
        _h.setFormatter(logging.Formatter("%(levelname)s|%(message)s"))
        _pkg.addHandler(_h)
        assert any(isinstance(h, logging.NullHandler) for h in _pkg.handlers)
        """
    )
    assert result.stderr == ""
    for message in _EXPECTED_MESSAGES:
        assert result.stdout.count(message) == 1
    assert "WARNING|" in result.stdout


def test_in_process_handler_on_package_logger_receives_records(
    tmp_path: Path,
) -> None:
    """In-process: a consumer handler on the package logger gets the record."""
    import json

    from pydantic import BaseModel

    from robotsix_config import load_config

    class Model(BaseModel):
        name: str = "svc"

    records: list[logging.LogRecord] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Collect(level=logging.WARNING)
    pkg_logger = logging.getLogger("robotsix_config")
    pkg_logger.addHandler(handler)
    try:
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"name": "x", "gone_key": 1}), encoding="utf-8")
        load_config(Model, path)
    finally:
        pkg_logger.removeHandler(handler)

    assert any(
        r.name == "robotsix_config.config" and "gone_key" in r.getMessage()
        for r in records
    )
    assert any(isinstance(h, logging.NullHandler) for h in pkg_logger.handlers)
