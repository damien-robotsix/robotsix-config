"""Tests for robotsix_config.cli."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from robotsix_config.cli import (
    _config_check_keys,
    _import_model,
    _schema_check,
    _schema_generate,
    main,
)


# -- _import_model -----------------------------------------------------------


class TestImportModel:
    def test_success(self) -> None:
        cls = _import_model("pydantic.BaseModel")
        from pydantic import BaseModel

        assert cls is BaseModel

    def test_invalid_module_path_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="Expected a dotted path"):
            _import_model("NoDotsHere")

    def test_missing_module_raises_importerror(self) -> None:
        with pytest.raises(ImportError, match="Could not import module"):
            _import_model("nonexistent.module.Cls")

    def test_missing_attribute_raises_attributeerror(self) -> None:
        with pytest.raises(AttributeError, match="has no attribute"):
            _import_model("pydantic.NonexistentClass42")

    def test_non_basemodel_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="not a pydantic BaseModel subclass"):
            _import_model("json.JSONDecoder")


# -- schema generate ---------------------------------------------------------


class TestSchemaGenerate:
    def test_writes_fresh_schema(self, tmp_path: Path) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        output = tmp_path / "schema.json"
        _schema_generate(AppSettings, output)

        assert output.is_file()
        content = output.read_text(encoding="utf-8")
        assert content.endswith("\n")
        data = json.loads(content)
        assert "properties" in data
        assert "api_key" in data["properties"]

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        output = tmp_path / "sub" / "deep" / "schema.json"
        _schema_generate(AppSettings, output)
        assert output.is_file()


# -- schema check ------------------------------------------------------------


class TestSchemaCheck:
    def test_in_sync_exits_zero(self, tmp_path: Path) -> None:
        from robotsix_config.config import config_schema_json
        from tests.config.scripts._test_cli_models import AppSettings

        output = tmp_path / "schema.json"
        output.write_text(config_schema_json(AppSettings), encoding="utf-8")

        # Should not raise SystemExit
        _schema_check(AppSettings, output)

    def test_missing_file_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        output = tmp_path / "missing.json"

        with pytest.raises(SystemExit) as excinfo:
            _schema_check(AppSettings, output)
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "missing" in captured.out

    def test_stale_file_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        output = tmp_path / "stale.json"
        output.write_text('{"stale": true}\n', encoding="utf-8")

        with pytest.raises(SystemExit) as excinfo:
            _schema_check(AppSettings, output)
        assert excinfo.value.code == 1

        captured = capsys.readouterr()
        assert "out of sync" in captured.out
        assert "Diff:" in captured.out
        # The file must NOT be overwritten in check mode.
        assert output.read_text(encoding="utf-8") == '{"stale": true}\n'


# -- config check-keys -------------------------------------------------------


class TestConfigCheckKeys:
    def test_all_keys_present_exits_zero(
        self, tmp_path: Path, write_config, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        config_path = write_config(
            tmp_path / "config.json",
            {"api_key": "secret", "endpoint": "https://x", "retries": 5},
        )
        # Should not raise SystemExit
        _config_check_keys(AppSettings, config_path)
        captured = capsys.readouterr()
        assert "match" in captured.out

    def test_missing_key_exits_nonzero(
        self, tmp_path: Path, write_config, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        config_path = write_config(
            tmp_path / "config.json", {"api_key": "secret"}
        )
        with pytest.raises(SystemExit) as excinfo:
            _config_check_keys(AppSettings, config_path)
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "missing keys" in captured.err

    def test_unknown_key_exits_nonzero(
        self, tmp_path: Path, write_config, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        config_path = write_config(
            tmp_path / "config.json",
            {"api_key": "secret", "endpoint": "https://x", "retries": 5, "extra": 1},
        )
        with pytest.raises(SystemExit) as excinfo:
            _config_check_keys(AppSettings, config_path)
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "unknown keys" in captured.err

    def test_both_missing_and_unknown_exits_nonzero(
        self, tmp_path: Path, write_config, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        config_path = write_config(
            tmp_path / "config.json", {"api_key": "secret", "extra": 1}
        )
        with pytest.raises(SystemExit) as excinfo:
            _config_check_keys(AppSettings, config_path)
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "missing keys" in captured.err
        assert "unknown keys" in captured.err

    def test_config_not_found_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        config_path = tmp_path / "nonexistent.json"
        with pytest.raises(SystemExit) as excinfo:
            _config_check_keys(AppSettings, config_path)
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_invalid_json_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        config_path = tmp_path / "bad.json"
        config_path.write_text("{not json", encoding="utf-8")
        with pytest.raises(SystemExit) as excinfo:
            _config_check_keys(AppSettings, config_path)
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid JSON" in captured.err

    def test_non_dict_json_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        config_path = tmp_path / "list.json"
        config_path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(SystemExit) as excinfo:
            _config_check_keys(AppSettings, config_path)
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "JSON object" in captured.err

    def test_empty_model_matches_empty_config(
        self, tmp_path: Path, write_config, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import NoFieldsModel

        config_path = write_config(tmp_path / "config.json", {})
        _config_check_keys(NoFieldsModel, config_path)
        captured = capsys.readouterr()
        assert "match" in captured.out


# -- main() integration ------------------------------------------------------


class TestMainIntegration:
    def test_schema_generate_default_output(
        self, tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``main(['schema', model])`` writes to ``config/config.schema.json`` by default."""
        # Change CWD so the default output lands in tmp_path.
        monkeypatch.chdir(tmp_path)
        exit_code = main(
            [
                "schema",
                "tests.config.scripts._test_cli_models.AppSettings",
            ]
        )
        assert exit_code == 0
        output = tmp_path / "config" / "config.schema.json"
        assert output.is_file()
        captured = capsys.readouterr()
        assert "Wrote schema" in captured.out

    def test_schema_check_sync(
        self, tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from robotsix_config.config import config_schema_json
        from tests.config.scripts._test_cli_models import AppSettings

        monkeypatch.chdir(tmp_path)
        output_dir = tmp_path / "config"
        output_dir.mkdir()
        output = output_dir / "config.schema.json"
        output.write_text(config_schema_json(AppSettings), encoding="utf-8")

        exit_code = main(
            [
                "schema",
                "--check",
                "tests.config.scripts._test_cli_models.AppSettings",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "in sync" in captured.out

    def test_schema_check_drift(
        self, tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.config.scripts._test_cli_models import AppSettings

        monkeypatch.chdir(tmp_path)
        output_dir = tmp_path / "config"
        output_dir.mkdir()
        output = output_dir / "config.schema.json"
        output.write_text('{"stale": true}\n', encoding="utf-8")

        exit_code = main(
            [
                "schema",
                "--check",
                "tests.config.scripts._test_cli_models.AppSettings",
            ]
        )
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "out of sync" in captured.out

    def test_schema_bad_model_path(
        self, tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        exit_code = main(["schema", "nonexistent.Module.Cls"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Could not import" in captured.err

    def test_config_check_keys(
        self, tmp_path: Path, write_config, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config_path = write_config(
            tmp_path / "config.json",
            {"api_key": "secret", "endpoint": "https://x", "retries": 5},
        )
        exit_code = main(
            [
                "config",
                "--check-keys",
                "tests.config.scripts._test_cli_models.AppSettings",
                "--config",
                str(config_path),
            ]
        )
        assert exit_code == 0

    def test_config_check_keys_missing(
        self, tmp_path: Path, write_config, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config_path = write_config(tmp_path / "config.json", {"api_key": "secret"})
        exit_code = main(
            [
                "config",
                "--check-keys",
                "tests.config.scripts._test_cli_models.AppSettings",
                "--config",
                str(config_path),
            ]
        )
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "missing keys" in captured.err


# -- console-script subprocess test ------------------------------------------


class TestConsoleScriptSubprocess:
    """Invoke the installed ``robotsix-config`` binary via subprocess."""

    def test_schema_generate_via_module(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        output = tmp_path / "out" / "schema.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "robotsix_config",
                "schema",
                "tests.config.scripts._test_cli_models.AppSettings",
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        assert output.is_file()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert "properties" in data

    def test_schema_check_via_module(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from robotsix_config.config import config_schema_json
        from tests.config.scripts._test_cli_models import AppSettings

        output = tmp_path / "schema.json"
        output.write_text(config_schema_json(AppSettings), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "robotsix_config",
                "schema",
                "--check",
                "tests.config.scripts._test_cli_models.AppSettings",
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        assert "in sync" in result.stdout

    def test_config_check_keys_via_module(
        self, tmp_path: Path, write_config, monkeypatch
    ) -> None:
        config_path = write_config(
            tmp_path / "config.json",
            {"api_key": "secret", "endpoint": "https://x", "retries": 5},
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "robotsix_config",
                "config",
                "--check-keys",
                "tests.config.scripts._test_cli_models.AppSettings",
                "--config",
                str(config_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        assert "match" in result.stdout

    def test_bad_model_exits_nonzero(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "robotsix_config",
                "schema",
                "nonexistent.Module.Cls",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Could not import" in result.stderr