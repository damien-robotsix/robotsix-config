"""Tests for scripts/check_optional_imports.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

from scripts.check_optional_imports import (
    _check_file,
    _parse_optional_dev_deps,
    _top_level_module,
)


class TestTopLevelModule:
    def test_simple_name(self) -> None:
        assert _top_level_module("hypothesis") == "hypothesis"

    def test_dotted_name(self) -> None:
        assert _top_level_module("hypothesis.strategies") == "hypothesis"

    def test_deeply_nested(self) -> None:
        assert _top_level_module("a.b.c.d") == "a"


class TestParseOptionalDevDeps:
    def test_real_pyproject(self) -> None:
        """The real pyproject.toml must parse without error."""
        deps = _parse_optional_dev_deps(
            Path(__file__).resolve().parent.parent.parent.parent / "pyproject.toml"
        )
        assert "hypothesis" in deps
        assert "pytest" in deps
        assert "mkdocstrings" in deps  # extras stripped

    def test_minimal_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
                [project]
                name = "test"

                [project.optional-dependencies]
                dev = ["hypothesis>=6", "mkdocstrings[python]>=0.25"]
            """)
        )
        deps = _parse_optional_dev_deps(pyproject)
        assert deps == frozenset({"hypothesis", "mkdocstrings"})

    def test_no_dev_section(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")
        deps = _parse_optional_dev_deps(pyproject)
        assert deps == frozenset()


class TestCheckFile:
    @staticmethod
    def _write(tmp_path: Path, source: str) -> Path:
        p = tmp_path / "test_mod.py"
        p.write_text(textwrap.dedent(source))
        return p

    def test_unguarded_import(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            """\
            from hypothesis import given

            def test_foo():
                pass
            """,
        )
        violations = _check_file(p, frozenset({"hypothesis"}))
        assert len(violations) == 1
        assert violations[0].module == "hypothesis"

    def test_unguarded_import_as(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            """\
            import hypothesis as hyp

            def test_foo():
                pass
            """,
        )
        violations = _check_file(p, frozenset({"hypothesis"}))
        assert len(violations) == 1
        assert violations[0].module == "hypothesis"

    def test_guarded_by_importorskip(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            """\
            import pytest
            pytest.importorskip("hypothesis")
            from hypothesis import given

            def test_foo():
                pass
            """,
        )
        violations = _check_file(p, frozenset({"hypothesis"}))
        assert violations == []

    def test_guarded_by_try_except(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            """\
            try:
                from hypothesis import given
            except ImportError:
                given = None  # type: ignore[assignment]

            def test_foo():
                pass
            """,
        )
        violations = _check_file(p, frozenset({"hypothesis"}))
        assert violations == []

    def test_try_except_other_error_not_a_guard(self, tmp_path: Path) -> None:
        """A try/except ValueError does NOT count as an import guard."""
        p = self._write(
            tmp_path,
            """\
            try:
                from hypothesis import given
            except ValueError:
                given = None

            def test_foo():
                pass
            """,
        )
        violations = _check_file(p, frozenset({"hypothesis"}))
        assert len(violations) == 1

    def test_import_inside_function_is_not_module_level(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            """\
            def test_foo():
                from hypothesis import given
                pass
            """,
        )
        violations = _check_file(p, frozenset({"hypothesis"}))
        assert violations == []

    def test_non_optional_dep_not_flagged(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            """\
            from pydantic import BaseModel

            def test_foo():
                pass
            """,
        )
        violations = _check_file(p, frozenset({"hypothesis"}))
        assert violations == []

    def test_syntax_error_not_crashing(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, "this is not valid python !!!")
        violations = _check_file(p, frozenset({"hypothesis"}))
        assert violations == []

    def test_pytest_always_safe(self, tmp_path: Path) -> None:
        """``import pytest`` is never flagged even when pytest is an optional dep."""
        p = self._write(
            tmp_path,
            """\
            import pytest

            def test_foo():
                pass
            """,
        )
        violations = _check_file(p, frozenset({"pytest", "hypothesis"}))
        assert violations == []
