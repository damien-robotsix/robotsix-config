"""Tests for the runtime deprecation decorator.

``pyproject.toml`` sets ``filterwarnings = ["error"]``, so a stray
``DeprecationWarning`` would fail the suite outright. These tests capture the
warning explicitly with :func:`pytest.warns`, which both proves the warning is
emitted and prevents it from escalating to an error.
"""

from __future__ import annotations

import pytest

from robotsix_config._deprecation import deprecated


def test_deprecated_emits_warning_on_call():
    @deprecated("0.7.0", "1.0.0")
    def old_function() -> int:
        return 42

    with pytest.warns(DeprecationWarning):
        result = old_function()

    assert result == 42


def test_deprecated_warning_matches_message_parameter():
    @deprecated("0.7.0", "1.0.0", "Use new_function instead")
    def old_function() -> None:
        pass

    with pytest.warns(DeprecationWarning, match="Use new_function instead"):
        old_function()


def test_deprecated_warning_reports_versions():
    @deprecated("0.7.0", "1.0.0")
    def old_function() -> None:
        pass

    with pytest.warns(DeprecationWarning) as record:
        old_function()

    text = str(record[0].message)
    assert "0.7.0" in text
    assert "1.0.0" in text


def test_deprecated_preserves_metadata():
    @deprecated("0.7.0", "1.0.0")
    def old_function() -> None:
        """Original docstring."""

    assert old_function.__name__ == "old_function"
    assert old_function.__doc__ == "Original docstring."
