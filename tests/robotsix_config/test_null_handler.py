"""The package logger carries a NullHandler (library logging convention)."""

from __future__ import annotations

import logging
import subprocess
import sys
import textwrap


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
