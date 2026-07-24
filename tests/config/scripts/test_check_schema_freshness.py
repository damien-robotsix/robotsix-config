"""Unit tests for scripts/check_schema_freshness.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_schema_freshness import _import_model, main


class TestImportModel:
    def test_success(self) -> None:
        """Importing a real Pydantic model by dotted path succeeds."""
        cls = _import_model("pydantic.BaseModel")
        from pydantic import BaseModel

        assert cls is BaseModel

    def test_invalid_module_path_raises_valueerror(self) -> None:
        """A dotted path with no dot raises ValueError."""
        with pytest.raises(ValueError, match="Expected a dotted path"):
            _import_model("NoDotsHere")

    def test_missing_attribute_raises_attributeerror(self) -> None:
        """A valid module but non-existent class raises AttributeError."""
        with pytest.raises(AttributeError, match="has no attribute"):
            _import_model("pydantic.NonexistentClass42")


class TestMain:
    @staticmethod
    def _fresh_schema_text() -> str:
        """Return the canonical schema text for SimpleModel."""
        from tests.config.scripts._test_models import SimpleModel

        return json.dumps(SimpleModel.model_json_schema(), indent=2) + "\n"

    def test_fresh_file_is_noop(self, tmp_path: Path) -> None:
        """When the file already matches, main exits 0 and prints 'fresh'."""
        output = tmp_path / "schema.json"
        output.write_text(self._fresh_schema_text(), encoding="utf-8")

        # Should not raise SystemExit
        main(
            [
                "--model",
                "tests.config.scripts._test_models.SimpleModel",
                "--output",
                str(output),
            ]
        )

    def test_missing_file_creates_and_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When the file is missing, main creates it and exits 1."""
        output = tmp_path / "missing_schema.json"

        with pytest.raises(SystemExit) as excinfo:
            main(
                [
                    "--model",
                    "tests.config.scripts._test_models.SimpleModel",
                    "--output",
                    str(output),
                ]
            )
        assert excinfo.value.code == 1
        assert output.is_file()

        captured = capsys.readouterr()
        assert "missing" in captured.out

    def test_stale_file_rewrites_and_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When the file is stale, main rewrites it, prints a diff, and exits 1."""
        output = tmp_path / "stale_schema.json"
        output.write_text('{"stale": true}\n', encoding="utf-8")

        with pytest.raises(SystemExit) as excinfo:
            main(
                [
                    "--model",
                    "tests.config.scripts._test_models.SimpleModel",
                    "--output",
                    str(output),
                ]
            )
        assert excinfo.value.code == 1

        # File must be rewritten to the fresh content.
        assert output.read_text(encoding="utf-8") == self._fresh_schema_text()

        captured = capsys.readouterr()
        assert "stale" in captured.out
        assert "Diff:" in captured.out
