"""Unit tests for scripts/check_py_typed.py."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.check_py_typed import EXPECTED_MARKER, _verify_marker


def _make_wheel(path: Path, names: list[str]) -> Path:
    """Write a minimal zip (wheel) at ``path`` containing ``names``."""
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            zf.writestr(name, b"")
    return path


class TestVerifyMarker:
    def test_marker_present_is_noop(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A wheel containing the marker exits 0 and prints confirmation."""
        wheel = _make_wheel(
            tmp_path / "robotsix_config-1.0-py3-none-any.whl",
            [EXPECTED_MARKER, "robotsix_config/__init__.py"],
        )

        # Should not raise SystemExit.
        _verify_marker([wheel])

        captured = capsys.readouterr()
        assert "confirmed" in captured.out

    def test_no_wheel_exits_nonzero(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty wheel list prints to stderr and exits 1."""
        with pytest.raises(SystemExit) as excinfo:
            _verify_marker([])

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "No wheel produced" in captured.err

    def test_marker_missing_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A wheel without the marker prints its contents and exits 1."""
        wheel = _make_wheel(
            tmp_path / "robotsix_config-1.0-py3-none-any.whl",
            ["robotsix_config/__init__.py"],
        )

        with pytest.raises(SystemExit) as excinfo:
            _verify_marker([wheel])

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "not found in wheel" in captured.err
        assert "Wheel contents:" in captured.err
        assert "robotsix_config/__init__.py" in captured.err
