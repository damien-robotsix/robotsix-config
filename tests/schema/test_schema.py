"""Tests for the pydantic schema layer (single-file load_config, typed schema)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Optional

import pytest
import yaml
from pydantic import BaseModel, SecretStr

from robotsix_yaml_config import CONFIG_FILE_ENV
from robotsix_yaml_config.schema import (
    emit_deploy_schema,
    emit_deploy_schema_json,
    emit_deploy_template,
    load_config,
)


class Imap(BaseModel):
    host: str = "localhost"
    port: int = 993


class LogLevel(StrEnum):
    info = "info"
    debug = "debug"


class MailConfig(BaseModel):
    log_level: LogLevel = LogLevel.info
    password: SecretStr = SecretStr("")
    imap: Imap = Imap()


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


# -- load_config: one file, no env, defaults from the model -----------------


def test_defaults_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_FILE_ENV, str(tmp_path / "missing.yaml"))
    cfg = load_config(MailConfig)
    assert cfg.log_level is LogLevel.info
    assert cfg.imap.host == "localhost"
    assert cfg.imap.port == 993


def test_file_supplies_values(monkeypatch, tmp_path):
    text = "log_level: debug\nimap:\n  host: mail.example.com\n"
    p = _write(tmp_path / "c.yaml", text)
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    cfg = load_config(MailConfig)
    assert cfg.log_level is LogLevel.debug
    assert cfg.imap.host == "mail.example.com"
    assert cfg.imap.port == 993  # untouched default


def test_env_is_not_a_config_source(monkeypatch, tmp_path):
    """Environment variables must NOT influence config values."""
    p = _write(tmp_path / "c.yaml", "imap:\n  host: file.example.com\n")
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    # These would have been picked up by the old env overlay — now ignored.
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__HOST", "env.example.com")
    monkeypatch.setenv("ROBOTSIX_MAIL_LOG_LEVEL", "debug")
    cfg = load_config(MailConfig)
    assert cfg.imap.host == "file.example.com"  # file wins; env ignored
    assert cfg.log_level is LogLevel.info  # default; env ignored


def test_explicit_config_file_arg(tmp_path):
    p = _write(tmp_path / "explicit.yaml", "log_level: debug\n")
    cfg = load_config(MailConfig, p)
    assert cfg.log_level is LogLevel.debug


def test_secret_is_masked(monkeypatch, tmp_path):
    p = _write(tmp_path / "c.yaml", 'password: "hunter2"\n')
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    cfg = load_config(MailConfig)
    assert cfg.password.get_secret_value() == "hunter2"
    assert "hunter2" not in repr(cfg)


def test_top_level_non_mapping_rejected(monkeypatch, tmp_path):
    p = _write(tmp_path / "c.yaml", "- a\n- b\n")
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    with pytest.raises(Exception, match="mapping"):
        load_config(MailConfig)


# -- emit_deploy_schema: typed schema for the deploy UI ----------------------


def test_schema_encodes_types_and_defaults():
    schema = emit_deploy_schema(MailConfig)
    props = schema["properties"]
    # nested model becomes a $ref; enum + secret + int types are all encoded
    assert "$defs" in schema and "Imap" in schema["$defs"]
    assert schema["$defs"]["Imap"]["properties"]["port"]["type"] == "integer"
    assert schema["$defs"]["Imap"]["properties"]["port"]["default"] == 993
    # enum field carries its allowed values
    assert schema["$defs"]["LogLevel"]["enum"] == ["info", "debug"]
    assert "log_level" in props


def test_schema_marks_secret_as_password_writeonly():
    schema = emit_deploy_schema(MailConfig)
    pw = schema["properties"]["password"]
    assert pw["type"] == "string"
    assert pw["format"] == "password"
    assert pw["writeOnly"] is True


def test_schema_marks_required_fields():
    class Svc(BaseModel):
        name: str  # required
        retries: int = 3  # optional

    schema = emit_deploy_schema(Svc)
    assert schema["required"] == ["name"]
    assert schema["properties"]["retries"]["default"] == 3


def test_schema_optional_field():
    class Svc(BaseModel):
        note: Optional[str] = None  # noqa: UP045

    schema = emit_deploy_schema(Svc)
    assert "required" not in schema or "note" not in schema.get("required", [])


def test_schema_json_is_parseable():
    import json

    text = emit_deploy_schema_json(MailConfig)
    assert text.endswith("\n")
    assert json.loads(text)["title"] == "MailConfig"


# -- emit_deploy_template: starter config.yaml -------------------------------


def test_template_defaults_and_secret_slots():
    data = yaml.safe_load(emit_deploy_template(MailConfig))
    assert data["log_level"] == "info"  # enum default rendered as its value
    assert data["password"] == ""  # secret slot
    assert data["imap"] == {"host": "localhost", "port": 993}


class _Nested(BaseModel):
    x: int = 1


class _AllRequired(BaseModel):
    name: str  # required str -> ""
    count: int  # required int -> 0
    ratio: float  # required float -> 0.0
    flag: bool  # required bool -> False
    tags: list[str]  # required list -> []
    meta: dict[str, str]  # required dict -> {}
    either: int | str  # required union -> first arg's placeholder
    maybe: Optional[_Nested] = None  # noqa: UP045 -- optional nested model


def test_template_required_placeholders_and_optional_nested():
    data = yaml.safe_load(emit_deploy_template(_AllRequired))
    assert data["name"] == ""
    assert data["count"] == 0
    assert data["ratio"] == 0.0
    assert data["flag"] is False
    assert data["tags"] == []
    assert data["meta"] == {}
    assert data["either"] == 0
    # Optional[_Nested] is still rendered as the nested model's template.
    assert data["maybe"] == {"x": 1}


class _ModelDefault(BaseModel):
    # Annotation the model-detector ignores, but the default is a model / secret,
    # exercising the recursive default-coercion branches.
    blob: Any = _Nested()
    token: Any = SecretStr("s3cr3t")


def test_template_coerces_model_and_secret_defaults():
    data = yaml.safe_load(emit_deploy_template(_ModelDefault))
    assert data["blob"] == {"x": 1}  # BaseModel default -> nested dict
    assert data["token"] == ""  # SecretStr default -> empty slot
