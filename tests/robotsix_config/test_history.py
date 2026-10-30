"""Tests for the append-only config version history.

The failure this module exists to prevent: a partial config update that
destroys a secret the caller never meant to change. A UI shows a secret as
``"**********"``, the operator edits an unrelated field, the form posts every
field back, and the mask overwrites the real credential. That has cost this
fleet live credentials more than once, so it is tested here from several angles.
"""

from __future__ import annotations

import json

import pytest

from robotsix_config import history as mod
from robotsix_config._errors import InvalidConfigError

from ._history_models import Cfg


class TestApplyUpdate:
    def test_partial_update_leaves_other_keys_alone(self, cfg_path) -> None:
        merged, changed, version = mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        assert merged["retries"] == 9
        assert merged["name"] == "svc"
        assert merged["langfuse"]["public_key"] == "pk-real"
        assert changed == ["retries"]
        assert version >= 1

    def test_masked_secret_does_not_overwrite_the_real_one(self, cfg_path) -> None:
        """The core regression: posting the mask back must not destroy it."""
        merged, _, _ = mod.apply_update(
            Cfg,
            {
                "langfuse": {
                    "secret_key": mod.MASKED_SECRET_SENTINEL,
                    "host": "https://new",
                }
            },
            cfg_path,
        )
        assert merged["langfuse"]["secret_key"] == "sk-real"
        assert merged["langfuse"]["host"] == "https://new"

    def test_blank_secret_does_not_overwrite_the_real_one(self, cfg_path) -> None:
        """A form that submits empty for an untouched password field is the
        other half of the same bug."""
        merged, _, _ = mod.apply_update(Cfg, {"langfuse": {"secret_key": ""}}, cfg_path)
        assert merged["langfuse"]["secret_key"] == "sk-real"

    def test_a_real_secret_change_is_applied(self, cfg_path) -> None:
        """Preservation must not become 'secrets can never be changed'."""
        merged, changed, _ = mod.apply_update(
            Cfg, {"langfuse": {"secret_key": "sk-new"}}, cfg_path
        )
        assert merged["langfuse"]["secret_key"] == "sk-new"
        assert changed == ["langfuse (secret)"]

    def test_invalid_update_leaves_the_file_untouched(self, cfg_path) -> None:
        """Validation happens before the write: a component must never persist
        config its own model refuses to load, or it crash-loops on restart."""
        before = cfg_path.read_text(encoding="utf-8")
        with pytest.raises(InvalidConfigError):
            mod.apply_update(Cfg, {"retries": "not-an-int"}, cfg_path)
        assert cfg_path.read_text(encoding="utf-8") == before
        assert mod.current_version(cfg_path) == 0

    def test_noop_update_records_no_version(self, cfg_path) -> None:
        _, changed, _ = mod.apply_update(Cfg, {"retries": 3}, cfg_path)
        assert changed == []
        assert mod.read_versions(cfg_path) == []

    def test_first_change_also_records_the_starting_point(self, cfg_path) -> None:
        """Without an 'initial' entry the first change has nothing to roll back to."""
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        entries = mod.read_versions(cfg_path)
        assert [e["changed_keys"] for e in entries] == [["initial"], ["retries"]]
        assert entries[0]["data"]["retries"] == 3

    def test_missing_config_file_is_created(self, tmp_path) -> None:
        target = tmp_path / "nested" / "config.json"
        merged, _changed, version = mod.apply_update(Cfg, {"name": "fresh"}, target)
        assert merged["name"] == "fresh"
        assert version == 1
        assert json.loads(target.read_text(encoding="utf-8"))["name"] == "fresh"


class TestRollback:
    def test_rollback_restores_values_as_a_new_version(self, cfg_path) -> None:
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        mod.apply_update(Cfg, {"retries": 11}, cfg_path)
        restored, changed, version = mod.rollback(Cfg, 1, cfg_path)
        assert restored["retries"] == 3
        assert changed == ["retries"]
        assert version == 4  # initial, 9, 11, rollback

    def test_history_is_never_truncated(self, cfg_path) -> None:
        """Rolling back must not delete what came after — the history has to
        keep explaining how the file reached its current state."""
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        mod.rollback(Cfg, 1, cfg_path)
        versions = [e["version"] for e in mod.read_versions(cfg_path)]
        assert versions == [1, 2, 3]

    def test_unknown_version_is_rejected(self, cfg_path) -> None:
        with pytest.raises(InvalidConfigError, match="No version 42"):
            mod.rollback(Cfg, 42, cfg_path)

    def test_version_that_no_longer_validates_is_rejected(self, cfg_path) -> None:
        """A field dropped from the model since that version was recorded must
        fail loudly rather than write config the app cannot load."""
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        vp = mod.versions_path(cfg_path)
        bad = {
            "version": 99,
            "timestamp": "x",
            "changed_keys": [],
            "data": {"retries": "no"},
        }
        vp.write_text(
            vp.read_text(encoding="utf-8") + json.dumps(bad) + "\n", encoding="utf-8"
        )
        with pytest.raises(InvalidConfigError, match="no longer validates"):
            mod.rollback(Cfg, 99, cfg_path)


class TestLoadWithHistoryAndInvalidConfig:
    def test_load_with_history_returns_model_and_version(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"name": "svc", "retries": 5}), encoding="utf-8")
        model, version = mod.load_with_history(Cfg, cfg)
        assert model.name == "svc"
        assert model.retries == 5
        assert version == 0

    def test_apply_update_rejects_invalid_json(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text("{not json", encoding="utf-8")
        with pytest.raises(InvalidConfigError):
            mod.apply_update(Cfg, {"name": "x"}, cfg)

    def test_apply_update_rejects_non_object_config(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text("[]", encoding="utf-8")
        with pytest.raises(InvalidConfigError):
            mod.apply_update(Cfg, {"name": "x"}, cfg)
