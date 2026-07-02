"""Tests for load/dump/schema over one JSON config file."""

from __future__ import annotations

import json
import stat
from enum import StrEnum
from typing import Any, Optional

import pytest
from pydantic import BaseModel, SecretStr

from robotsix_config import (
    CONFIG_FILE_ENV,
    DEFAULT_CONFIG_PATH,
    InvalidConfigError,
    config_schema,
    config_schema_json,
    dump_config,
    load_config,
    resolve_config_path,
)


class LogLevel(StrEnum):
    info = "info"
    debug = "debug"


class Imap(BaseModel):
    host: str = "localhost"
    port: int = 993


class MailConfig(BaseModel):
    log_level: LogLevel = LogLevel.info
    password: SecretStr = SecretStr("")
    imap: Imap = Imap()


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


# -- resolve_config_path ------------------------------------------------------


def test_default_path_is_json(monkeypatch):
    monkeypatch.delenv(CONFIG_FILE_ENV, raising=False)
    assert resolve_config_path() == DEFAULT_CONFIG_PATH
    assert str(DEFAULT_CONFIG_PATH) == "config/config.json"


def test_env_locates_file(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_FILE_ENV, str(tmp_path / "c.json"))
    assert resolve_config_path() == tmp_path / "c.json"


# -- load_config: one JSON file, defaults from the model ----------------------


def test_defaults_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_FILE_ENV, str(tmp_path / "missing.json"))
    cfg = load_config(MailConfig)
    assert cfg.log_level is LogLevel.info
    assert cfg.imap == Imap()


def test_file_supplies_values(tmp_path):
    p = _write(tmp_path / "c.json", {"log_level": "debug", "imap": {"host": "mx"}})
    cfg = load_config(MailConfig, p)
    assert cfg.log_level is LogLevel.debug
    assert cfg.imap.host == "mx"
    assert cfg.imap.port == 993  # untouched default


def test_env_is_not_a_config_source(monkeypatch, tmp_path):
    p = _write(tmp_path / "c.json", {"imap": {"host": "file"}})
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__HOST", "env")  # must be ignored
    cfg = load_config(MailConfig)
    assert cfg.imap.host == "file"


def test_bad_json_raises(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(InvalidConfigError, match="Invalid JSON"):
        load_config(MailConfig, p)


def test_non_object_top_level_raises(tmp_path):
    p = _write(tmp_path / "c.json", [1, 2])
    with pytest.raises(InvalidConfigError, match="must be a JSON object"):
        load_config(MailConfig, p)


def test_validation_error_wrapped(tmp_path):
    p = _write(tmp_path / "c.json", {"imap": {"port": "not-an-int"}})
    with pytest.raises(InvalidConfigError, match="is invalid"):
        load_config(MailConfig, p)


def test_unreadable_path_raises(tmp_path):
    d = tmp_path / "adir"
    d.mkdir()  # a directory, not a file
    with pytest.raises(InvalidConfigError, match="Cannot read"):
        load_config(MailConfig, d)


# -- dump_config: JSON, 0600, secrets revealed, round-trips -------------------


def test_dump_writes_0600_and_reveals_secret(tmp_path):
    cfg = MailConfig(password=SecretStr("hunter2"), imap=Imap(host="mx"))
    target = tmp_path / "sub" / "config.json"
    written = dump_config(cfg, target)
    assert written == target
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["password"] == "hunter2"  # cleartext for the app to read back
    assert data["imap"]["host"] == "mx"


def test_dump_then_load_round_trip(tmp_path):
    cfg = MailConfig(log_level=LogLevel.debug, password=SecretStr("s3cr3t"))
    p = tmp_path / "config.json"
    dump_config(cfg, p)
    back = load_config(MailConfig, p)
    assert back.log_level is LogLevel.debug
    assert back.password.get_secret_value() == "s3cr3t"


def test_dump_reveals_secrets_in_lists(tmp_path):
    class Multi(BaseModel):
        tokens: list[SecretStr] = []

    p = tmp_path / "c.json"
    dump_config(Multi(tokens=[SecretStr("a"), SecretStr("b")]), p)
    assert json.loads(p.read_text())["tokens"] == ["a", "b"]


# -- config_schema: typed schema for the deploy UI ----------------------------


def test_schema_types_enum_defaults():
    schema = config_schema(MailConfig)
    assert schema["$defs"]["Imap"]["properties"]["port"]["type"] == "integer"
    assert schema["$defs"]["Imap"]["properties"]["port"]["default"] == 993
    assert schema["$defs"]["LogLevel"]["enum"] == ["info", "debug"]


def test_schema_marks_secret():
    pw = config_schema(MailConfig)["properties"]["password"]
    assert pw["type"] == "string"
    assert pw["format"] == "password"
    assert pw["writeOnly"] is True


def test_schema_required_and_optional():
    class Svc(BaseModel):
        name: str
        retries: int = 3
        note: Optional[str] = None  # noqa: UP045
        blob: Any = None

    schema = config_schema(Svc)
    assert schema["required"] == ["name"]
    assert schema["properties"]["retries"]["default"] == 3
    assert "note" not in schema.get("required", [])


def test_schema_json_is_parseable():
    text = config_schema_json(MailConfig)
    assert text.endswith("\n")
    assert json.loads(text)["title"] == "MailConfig"
