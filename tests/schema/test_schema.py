"""Tests for the pydantic schema layer (load_config, emit_deploy_template)."""

from __future__ import annotations

import yaml
from pydantic import BaseModel, SecretStr

from robotsix_yaml_config import CONFIG_FILE_ENV
from robotsix_yaml_config.schema import emit_deploy_template, load_config


class Imap(BaseModel):
    host: str = "localhost"
    port: int = 993


class MailConfig(BaseModel):
    log_level: str = "info"
    password: SecretStr = SecretStr("")
    imap: Imap = Imap()


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


# -- load_config precedence -------------------------------------------------


def test_defaults_when_no_file_or_env(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_FILE_ENV, str(tmp_path / "missing.yaml"))
    cfg = load_config(MailConfig, env_prefix="ROBOTSIX_MAIL")
    assert cfg.log_level == "info"
    assert cfg.imap.host == "localhost"
    assert cfg.imap.port == 993


def test_file_overrides_defaults(monkeypatch, tmp_path):
    text = "log_level: debug\nimap:\n  host: mail.example.com\n"
    p = _write(tmp_path / "c.yaml", text)
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    cfg = load_config(MailConfig, env_prefix="ROBOTSIX_MAIL")
    assert cfg.log_level == "debug"
    assert cfg.imap.host == "mail.example.com"
    assert cfg.imap.port == 993


def test_env_overrides_file_and_coerces(monkeypatch, tmp_path):
    p = _write(tmp_path / "c.yaml", "imap:\n  host: file.example.com\n  port: 993\n")
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__HOST", "env.example.com")
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__PORT", "1993")  # string -> pydantic int
    cfg = load_config(MailConfig, env_prefix="ROBOTSIX_MAIL")
    assert cfg.imap.host == "env.example.com"
    assert cfg.imap.port == 1993
    assert isinstance(cfg.imap.port, int)


def test_overrides_win(monkeypatch, tmp_path):
    p = _write(tmp_path / "c.yaml", "log_level: debug\n")
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    monkeypatch.setenv("ROBOTSIX_MAIL_LOG_LEVEL", "warning")
    cfg = load_config(
        MailConfig, env_prefix="ROBOTSIX_MAIL", overrides={"log_level": "error"}
    )
    assert cfg.log_level == "error"


def test_defaults_arg_below_file(monkeypatch, tmp_path):
    p = _write(tmp_path / "c.yaml", "log_level: fromfile\n")
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    cfg = load_config(
        MailConfig,
        env_prefix="ROBOTSIX_MAIL",
        defaults={"log_level": "fromdefaults", "imap": {"host": "d"}},
    )
    assert cfg.log_level == "fromfile"  # file beats defaults
    assert cfg.imap.host == "d"  # defaults still apply where file is silent


def test_explicit_config_file_arg_beats_env(monkeypatch, tmp_path):
    env_file = _write(tmp_path / "env.yaml", "log_level: fromenvpath\n")
    arg_file = _write(tmp_path / "arg.yaml", "log_level: fromarg\n")
    monkeypatch.setenv(CONFIG_FILE_ENV, str(env_file))
    cfg = load_config(MailConfig, env_prefix="ROBOTSIX_MAIL", config_file=arg_file)
    assert cfg.log_level == "fromarg"


def test_secret_is_masked(monkeypatch, tmp_path):
    p = _write(tmp_path / "c.yaml", 'password: "hunter2"\n')
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    cfg = load_config(MailConfig, env_prefix="ROBOTSIX_MAIL")
    assert cfg.password.get_secret_value() == "hunter2"
    assert "hunter2" not in repr(cfg)


# -- emit_deploy_template ---------------------------------------------------


def test_template_defaults_and_secret_slots():
    data = yaml.safe_load(emit_deploy_template(MailConfig))
    assert data["log_level"] == "info"
    assert data["password"] == ""  # secret slot
    assert data["imap"] == {"host": "localhost", "port": 993}


def test_template_required_fields_get_placeholders():
    class Svc(BaseModel):
        name: str  # required str
        retries: int  # required int
        token: SecretStr  # required secret

    data = yaml.safe_load(emit_deploy_template(Svc))
    assert data == {"name": "", "retries": 0, "token": ""}


def test_template_list_and_optional():
    from typing import Optional

    class Svc(BaseModel):
        hosts: list[str] = []
        note: Optional[str] = None  # noqa: UP045 - exercise Optional handling

    data = yaml.safe_load(emit_deploy_template(Svc))
    assert data["hosts"] == []
    assert data["note"] is None


def test_template_default_factory():
    from pydantic import Field

    class Svc(BaseModel):
        tags: list[str] = Field(default_factory=list)

    data = yaml.safe_load(emit_deploy_template(Svc))
    assert data["tags"] == []


def test_template_optional_secret_is_slot():
    from typing import Optional

    class Svc(BaseModel):
        token: Optional[SecretStr] = None  # noqa: UP045 - exercise Optional[SecretStr]

    data = yaml.safe_load(emit_deploy_template(Svc))
    assert data["token"] == ""  # secret slot even when Optional


def test_template_optional_nested_model():
    from typing import Optional

    class Svc(BaseModel):
        imap: Optional[Imap] = None  # noqa: UP045 - exercise Optional[Model]

    data = yaml.safe_load(emit_deploy_template(Svc))
    assert data["imap"] == {"host": "localhost", "port": 993}


def test_template_required_dict_placeholder():
    class Svc(BaseModel):
        opts: dict[str, str]  # required dict → {} placeholder

    data = yaml.safe_load(emit_deploy_template(Svc))
    assert data["opts"] == {}


def test_template_unknown_type_placeholder_is_none():
    class Svc(BaseModel):
        model_config = {"arbitrary_types_allowed": True}
        blob: bytes  # required, not in the placeholder table → None

    data = yaml.safe_load(emit_deploy_template(Svc))
    assert data["blob"] is None
