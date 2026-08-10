"""Tests for load/dump/schema over one JSON config file."""

from __future__ import annotations

import errno
import json
import os
import stat
import sys
from enum import StrEnum
from typing import Any, Optional

import pytest
from pydantic import BaseModel, SecretStr

from robotsix_config import (
    CONFIG_FILE_ENV,
    DEFAULT_CONFIG_PATH,
    ConfigModel,
    InvalidConfigError,
    config_schema,
    config_schema_json,
    dump_config,
    load_config,
    resolve_config_path,
)
from robotsix_config.config import _atomic_replace


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


# -- resolve_config_path ------------------------------------------------------


def test_default_path_is_json(monkeypatch):
    monkeypatch.delenv(CONFIG_FILE_ENV, raising=False)
    assert resolve_config_path() == DEFAULT_CONFIG_PATH
    assert DEFAULT_CONFIG_PATH.parts == ("config", "config.json")


def test_env_locates_file(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_FILE_ENV, str(tmp_path / "c.json"))
    assert resolve_config_path() == tmp_path / "c.json"


# -- load_config: one JSON file, defaults from the model ----------------------


def test_defaults_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_FILE_ENV, str(tmp_path / "missing.json"))
    cfg = load_config(MailConfig)
    assert cfg.log_level is LogLevel.info
    assert cfg.imap == Imap()


def test_file_supplies_values(tmp_path, write_config):
    p = write_config(
        tmp_path / "c.json", {"log_level": "debug", "imap": {"host": "mx"}}
    )
    cfg = load_config(MailConfig, p)
    assert cfg.log_level is LogLevel.debug
    assert cfg.imap.host == "mx"
    assert cfg.imap.port == 993  # untouched default


def test_env_is_not_a_config_source(monkeypatch, tmp_path, write_config):
    p = write_config(tmp_path / "c.json", {"imap": {"host": "file"}})
    monkeypatch.setenv(CONFIG_FILE_ENV, str(p))
    monkeypatch.setenv("ROBOTSIX_MAIL_IMAP__HOST", "env")  # must be ignored
    cfg = load_config(MailConfig)
    assert cfg.imap.host == "file"


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize(
    "payload_factory,error_match",
    [
        (lambda p: p.write_text("{not json", encoding="utf-8"), "Invalid JSON"),
        (lambda p: _write(p, [1, 2]), "must be a JSON object"),
        (
            lambda p: _write(p, {"imap": {"port": "not-an-int"}}),
            "is invalid",
        ),
        (lambda p: p.mkdir(parents=True), "Cannot read"),
    ],
)
def test_invalid_config_raises(payload_factory, error_match, tmp_path):
    target = tmp_path / "config.json"
    payload_factory(target)
    with pytest.raises(InvalidConfigError, match=error_match):
        load_config(MailConfig, target)


# -- dump_config: JSON, 0600, secrets revealed, round-trips -------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX perms")
def test_dump_writes_0600_and_reveals_the_secret(tmp_path):
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


def test_dump_atomic_preserves_existing_on_failure(monkeypatch, tmp_path):
    """If fsync fails, an existing target file is left unchanged."""
    target = tmp_path / "config.json"
    cfg = MailConfig(log_level=LogLevel.info)
    dump_config(cfg, target)
    original = target.read_text(encoding="utf-8")

    def _raise(*args, **kwargs):
        raise OSError(errno.EIO, "simulated fsync failure")

    monkeypatch.setattr(os, "fsync", _raise)

    cfg2 = MailConfig(log_level=LogLevel.debug)
    with pytest.raises(OSError, match="simulated fsync failure"):
        dump_config(cfg2, target)

    # Target must be untouched — identical to what was there before the crash.
    assert target.read_text(encoding="utf-8") == original
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["log_level"] == "info"


def test_dump_atomic_no_leftover_on_new_file_failure(monkeypatch, tmp_path):
    """If fsync fails on a new file, the target path must not exist."""
    target = tmp_path / "sub" / "new_config.json"

    def _raise(*args, **kwargs):
        raise OSError(errno.EIO, "simulated fsync failure")

    monkeypatch.setattr(os, "fsync", _raise)

    cfg = MailConfig(log_level=LogLevel.debug)
    with pytest.raises(OSError, match="simulated fsync failure"):
        dump_config(cfg, target)

    assert not target.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX perms")
def test_dump_creates_0700_directory(tmp_path):
    """``dump_config`` always ensures the parent directory is mode 0700."""
    target = tmp_path / "sub" / "config.json"
    cfg = MailConfig()
    dump_config(cfg, target)
    dir_mode = stat.S_IMODE(target.parent.stat().st_mode)
    assert dir_mode == 0o700


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX perms")
def test_dump_corrects_directory_perms_on_rewrite(tmp_path):
    """``dump_config`` fixes a directory that already exists with wrong perms."""
    target = tmp_path / "sub" / "config.json"
    target.parent.mkdir(parents=True)
    target.parent.chmod(0o755)  # deliberately wrong
    cfg = MailConfig()
    dump_config(cfg, target)
    dir_mode = stat.S_IMODE(target.parent.stat().st_mode)
    assert dir_mode == 0o700


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX perms")
def test_dump_writes_0600_regardless_of_existing_perms(tmp_path, write_config):
    """``dump_config`` writes 0600 regardless of the existing file's mode."""
    target = tmp_path / "config.json"
    write_config(target, {"log_level": "debug"})
    target.chmod(0o644)
    cfg = MailConfig(password=SecretStr("s3cr3t"))
    dump_config(cfg, target)
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


def test_dump_reveals_secrets_in_lists():
    from robotsix_config.config import _reveal

    class Multi(BaseModel):
        tokens: list[SecretStr] = []

    model = Multi(tokens=[SecretStr("a"), SecretStr("b")])
    revealed = _reveal(model.model_dump(mode="python"))
    assert revealed["tokens"] == ["a", "b"]


def test_dump_reveals_secrets_in_tuples():
    from robotsix_config.config import _reveal

    class Multi(BaseModel):
        items: tuple[SecretStr, ...] = ()

    model = Multi(items=(SecretStr("a"), SecretStr("b")))
    revealed = _reveal(model.model_dump(mode="python"))
    assert revealed["items"] == ("a", "b")


def test_dump_reveals_secrets_in_sets():
    from robotsix_config.config import _reveal

    class Multi(BaseModel):
        items: set[SecretStr] = set()

    model = Multi(items={SecretStr("x"), SecretStr("y")})
    revealed = _reveal(model.model_dump(mode="python"))
    # sets/frozensets are converted to list for JSON serialization
    assert sorted(revealed["items"]) == ["x", "y"]


def test_dump_reveals_secrets_in_frozensets():
    from robotsix_config.config import _reveal

    class Multi(BaseModel):
        items: frozenset[SecretStr] = frozenset()

    model = Multi(items=frozenset({SecretStr("a"), SecretStr("b")}))
    revealed = _reveal(model.model_dump(mode="python"))
    assert sorted(revealed["items"]) == ["a", "b"]


# -- round-trip integration tests for collection-typed SecretStr fields ------


def test_round_trip_list_of_secrets(tmp_path):
    class Multi(BaseModel):
        tokens: list[SecretStr] = []

    model = Multi(tokens=[SecretStr("a"), SecretStr("b")])
    p = tmp_path / "config.json"
    dump_config(model, p)
    back = load_config(Multi, p)
    assert [t.get_secret_value() for t in back.tokens] == ["a", "b"]


def test_round_trip_set_of_secrets(tmp_path):
    class Multi(BaseModel):
        tokens: set[SecretStr] = set()

    model = Multi(tokens={SecretStr("x"), SecretStr("y")})
    p = tmp_path / "config.json"
    dump_config(model, p)
    back = load_config(Multi, p)
    assert {t.get_secret_value() for t in back.tokens} == {"x", "y"}


def test_round_trip_frozenset_of_secrets(tmp_path):
    class Multi(BaseModel):
        tokens: frozenset[SecretStr] = frozenset()

    model = Multi(tokens=frozenset({SecretStr("m"), SecretStr("n")}))
    p = tmp_path / "config.json"
    dump_config(model, p)
    back = load_config(Multi, p)
    assert {t.get_secret_value() for t in back.tokens} == {"m", "n"}


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


# -- ConfigModel: canonical base class ----------------------------------------


class AppConfig(ConfigModel):
    name: str = "my-app"
    token: SecretStr = SecretStr("")


def test_config_model_subclasses_base_model():
    """``ConfigModel`` is a drop-in replacement for ``BaseModel``."""
    assert issubclass(ConfigModel, BaseModel)


def test_config_model_load_and_dump_round_trip(tmp_path):
    """A ``ConfigModel`` subclass works identically with load/dump."""
    cfg = AppConfig(name="test-app", token=SecretStr("tok"))
    p = tmp_path / "config.json"
    dump_config(cfg, p)
    back = load_config(AppConfig, p)
    assert back.name == "test-app"
    assert back.token.get_secret_value() == "tok"


def test_config_model_secret_masked_on_repr():
    """SecretStr fields on a ``ConfigModel`` subclass are masked in repr."""
    cfg = AppConfig(token=SecretStr("s3cr3t"))
    r = repr(cfg)
    assert "s3cr3t" not in r


def test_config_model_secret_writeonly_in_schema():
    """SecretStr fields on a ``ConfigModel`` subclass are ``writeOnly``."""
    schema = config_schema(AppConfig)
    token = schema["properties"]["token"]
    assert token["type"] == "string"
    assert token["format"] == "password"
    assert token["writeOnly"] is True


# -- cross-platform: dump_config succeeds and round-trips on every OS ---------


def test_dump_config_succeeds_on_current_platform(tmp_path):
    """``dump_config`` must succeed and round-trip regardless of OS.

    On Windows, ``os.chmod`` only toggles the read-only attribute and
    ``os.replace`` can raise ``PermissionError`` when the target is held
    open — this test ensures the hardening (retry loop + best-effort chmod)
    keeps ``dump_config`` working everywhere.
    """
    cfg = MailConfig(password=SecretStr("cross-platform"), imap=Imap(host="mx"))
    target = tmp_path / "config.json"
    written = dump_config(cfg, target)
    assert written == target
    assert target.exists()
    back = load_config(MailConfig, target)
    assert back.password.get_secret_value() == "cross-platform"
    assert back.imap.host == "mx"


# -- _atomic_replace: retry-on-PermissionError unit coverage ------------------


def test_atomic_replace_retries_on_permission_error_then_succeeds(
    tmp_path,
    monkeypatch,
):
    """``_atomic_replace`` retries and ultimately succeeds when the first
    ``os.replace`` call raises ``PermissionError``."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.write_text("content")

    call_count = 0
    _original_replace = os.replace

    def _mock_replace(s, d):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise PermissionError("simulated open handle")
        _original_replace(s, d)

    monkeypatch.setattr(os, "replace", _mock_replace)

    _atomic_replace(str(src), dst)

    assert call_count == 2
    assert dst.exists()
    assert dst.read_text() == "content"


def test_atomic_replace_raises_after_exhausting_retries(tmp_path, monkeypatch):
    """``_atomic_replace`` re-raises ``PermissionError`` when every retry
    attempt fails."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.write_text("content")

    call_count = 0

    def _mock_replace(s, d):
        nonlocal call_count
        call_count += 1
        raise PermissionError("simulated persistent open handle")

    monkeypatch.setattr(os, "replace", _mock_replace)

    with pytest.raises(PermissionError):
        _atomic_replace(str(src), dst, attempts=3, delay=0)

    assert call_count == 3
    assert not dst.exists()


# -- Self-healing: strip unknown keys on load --------------------------------


class SubModel(BaseModel):
    host: str = "localhost"
    port: int = 8080


class HealModel(BaseModel):
    name: str = "svc"
    retries: int = 3
    sub: SubModel = SubModel()


def test_unknown_top_level_key_is_stripped(tmp_path, caplog):
    """A persisted top-level key not on the model is stripped and logged."""
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {"name": "svc", "retries": 5, "legal_guardrails": {"enabled": True}}
        ),
        encoding="utf-8",
    )
    cfg = load_config(HealModel, p)
    assert cfg.name == "svc"
    assert cfg.retries == 5
    assert not hasattr(cfg, "legal_guardrails")
    assert any("legal_guardrails" in r.message for r in caplog.records)
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_multiple_unknown_keys_are_all_stripped(tmp_path, caplog):
    """Multiple unknown top-level keys are all removed."""
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "name": "svc",
                "old_feature_a": {"x": 1},
                "old_feature_b": {"y": 2},
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(HealModel, p)
    assert cfg.name == "svc"
    assert not hasattr(cfg, "old_feature_a")
    assert not hasattr(cfg, "old_feature_b")
    assert any("old_feature_a" in r.message for r in caplog.records)
    assert any("old_feature_b" in r.message for r in caplog.records)


def test_unknown_nested_key_is_stripped(tmp_path, caplog):
    """A nested unknown key inside a declared sub-model is stripped."""
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "name": "svc",
                "sub": {
                    "host": "mx.example",
                    "port": 993,
                    "removed_field": "should be stripped",
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(HealModel, p)
    assert cfg.name == "svc"
    assert cfg.sub.host == "mx.example"
    assert cfg.sub.port == 993
    assert not hasattr(cfg.sub, "removed_field")
    assert any("removed_field" in r.message for r in caplog.records)


def test_no_strip_when_no_unknown_keys(tmp_path, caplog):
    """When all keys are known, no warning is emitted and no version is written."""
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps({"name": "svc", "retries": 5, "sub": {"host": "mx", "port": 9090}}),
        encoding="utf-8",
    )
    cfg = load_config(HealModel, p)
    assert cfg.name == "svc"
    assert cfg.retries == 5
    assert cfg.sub.host == "mx"
    # No WARNING-level records about stripping.
    assert not any("Stripping" in r.message for r in caplog.records)


def test_dict_typed_field_preserves_arbitrary_keys(tmp_path):
    """A field typed as a plain dict (dict[str, Any]) keeps its arbitrary
    keys — only $ref submodels have their unknown keys stripped."""

    class DictModel(BaseModel):
        name: str = "svc"
        metadata: dict[str, Any] = {}

    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {"name": "svc", "metadata": {"anything": "goes", "nested": {"x": 1}}}
        ),
        encoding="utf-8",
    )
    cfg = load_config(DictModel, p)
    assert cfg.name == "svc"
    assert cfg.metadata == {"anything": "goes", "nested": {"x": 1}}


def test_heal_persists_cleaned_config_and_new_version(tmp_path, caplog):
    """After stripping, the cleaned config is written back and a version entry
    is appended with the dropped keys listed as changed_keys."""
    from robotsix_config import history as mod

    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {"name": "svc", "retries": 5, "legal_guardrails": {"enabled": True}}
        ),
        encoding="utf-8",
    )
    load_config(HealModel, p)

    # The on-disk file should now be cleaned.
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert "legal_guardrails" not in on_disk
    assert on_disk["name"] == "svc"

    # A version entry should exist with changed_keys showing the dropped key.
    entries = mod.read_versions(p)
    assert len(entries) >= 1
    # The last entry records the heal.
    heal_entry = entries[-1]
    assert "legal_guardrails" in heal_entry["changed_keys"]


def test_heal_preserves_prior_version_history(tmp_path, caplog):
    """The prior (stale) version remains in history and is rollback-able."""
    from robotsix_config import history as mod

    p = tmp_path / "config.json"

    # Write initial config with a now-removed key.
    p.write_text(
        json.dumps(
            {
                "name": "svc",
                "retries": 3,
                "legal_guardrails": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )

    # Load triggers the heal.
    load_config(HealModel, p)

    entries = mod.read_versions(p)
    # Should have at least 2 entries: initial (the stale state) and heal.
    assert len(entries) >= 2

    # The first entry should be the initial (stale) state.
    initial = entries[0]
    assert initial["changed_keys"] == ["initial"]
    assert initial["data"]["retries"] == 3
    assert "legal_guardrails" in initial["data"]

    # The heal entry should list the dropped key.
    heal_entry = entries[-1]
    assert "legal_guardrails" in heal_entry["changed_keys"]

    # The stale version should still be rollback-able.
    # Rollback to version 1 (the initial state).
    restored, _changed, _new_ver = mod.rollback(HealModel, 1, p)
    assert restored["retries"] == 3
    # The legal_guardrails key won't be in restored because the model doesn't
    # have it, but the version entry should still be there.
    assert "legal_guardrails" in entries[0]["data"]
