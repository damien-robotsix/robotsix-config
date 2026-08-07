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
from pydantic import BaseModel, SecretStr

from robotsix_config import history as mod
from robotsix_config._errors import InvalidConfigError


class Langfuse(BaseModel):
    host: str = ""
    public_key: str = ""
    secret_key: SecretStr = SecretStr("")


class Cfg(BaseModel):
    name: str = ""
    retries: int = 3
    langfuse: Langfuse = Langfuse()


@pytest.fixture
def cfg_path(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "name": "svc",
                "retries": 3,
                "langfuse": {
                    "host": "https://lf.example",
                    "public_key": "pk-real",
                    "secret_key": "sk-real",
                },
            }
        ),
        encoding="utf-8",
    )
    return p


class TestSecretPaths:
    def test_secret_fields_are_found_through_a_submodel(self) -> None:
        """SecretStr in a $ref-ed submodel must still be discovered."""
        assert ("langfuse", "secret_key") in mod.secret_paths(Cfg)

    def test_plain_strings_are_not_secrets(self) -> None:
        paths = mod.secret_paths(Cfg)
        assert ("name",) not in paths
        assert ("langfuse", "host") not in paths

    def test_public_key_is_not_treated_as_a_secret(self) -> None:
        """The model is authoritative: a public key is not secret just because
        its name ends in '_key'. The name heuristic gets this wrong."""
        assert ("langfuse", "public_key") not in mod.secret_paths(Cfg)


class TestMaskSecrets:
    def test_secret_is_masked_and_other_values_survive(self) -> None:
        out = mod.mask_secrets(
            {"name": "svc", "langfuse": {"public_key": "pk", "secret_key": "sk-real"}},
            Cfg,
        )
        assert out["langfuse"]["secret_key"] == mod.MASKED_SECRET_SENTINEL
        assert out["langfuse"]["public_key"] == "pk"
        assert out["name"] == "svc"

    def test_empty_secret_is_not_masked(self) -> None:
        """Masking an unset secret would claim one exists, and the mask would
        then be posted back as 'unchanged' — inventing a credential."""
        out = mod.mask_secrets({"langfuse": {"secret_key": ""}}, Cfg)
        assert out["langfuse"]["secret_key"] == ""


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


class TestHistory:
    def test_versions_file_sits_beside_the_config(self, cfg_path) -> None:
        assert mod.versions_path(cfg_path).name == "config.json.versions"

    def test_missing_history_is_not_an_error(self, tmp_path) -> None:
        assert mod.read_versions(tmp_path / "absent.json") == []
        assert mod.current_version(tmp_path / "absent.json") == 0

    def test_corrupt_line_is_skipped_not_fatal(self, cfg_path) -> None:
        """One bad line from a killed process must not make the rest unreadable."""
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        vp = mod.versions_path(cfg_path)
        vp.write_text(vp.read_text(encoding="utf-8") + "{not json\n", encoding="utf-8")
        assert len(mod.read_versions(cfg_path)) == 2

    def test_include_data_false_omits_payloads(self, cfg_path) -> None:
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        entries = mod.read_versions(cfg_path, include_data=False)
        assert entries and all("data" not in e for e in entries)
        assert all("changed_keys" in e for e in entries)


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


class TestSecretsAreNeverStoredInHistory:
    """config-ownership.md: "the key name is logged, the value is never stored
    in version history". A long-lived append-only file must not accumulate
    credentials that outlive every rotation of them."""

    def test_history_snapshot_omits_secret_values(self, cfg_path) -> None:
        mod.apply_update(Cfg, {"langfuse": {"secret_key": "sk-new"}}, cfg_path)
        raw = mod.versions_path(cfg_path).read_text(encoding="utf-8")
        assert "sk-real" not in raw
        assert "sk-new" not in raw

    def test_non_secret_values_are_still_stored(self, cfg_path) -> None:
        """Stripping secrets must not gut the history of everything useful."""
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        latest = mod.read_versions(cfg_path)[-1]
        assert latest["data"]["retries"] == 9
        assert latest["data"]["langfuse"]["public_key"] == "pk-real"
        assert "secret_key" not in latest["data"]["langfuse"]

    def test_secret_change_is_marked_in_changed_keys(self, cfg_path) -> None:
        """The rotation must remain visible even though the value is not."""
        _, changed, _ = mod.apply_update(
            Cfg, {"langfuse": {"secret_key": "sk-new"}}, cfg_path
        )
        assert changed == ["langfuse (secret)"]

    def test_non_secret_change_is_not_marked(self, cfg_path) -> None:
        _, changed, _ = mod.apply_update(
            Cfg, {"langfuse": {"host": "https://new"}}, cfg_path
        )
        assert changed == ["langfuse"]

    def test_rollback_keeps_live_secrets(self, cfg_path) -> None:
        """The history cannot restore secrets, so it must not erase them
        either — a blanked credential reads as success and breaks the
        component at its next restart."""
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        restored, _, _ = mod.rollback(Cfg, 1, cfg_path)
        assert restored["langfuse"]["secret_key"] == "sk-real"
        assert restored["retries"] == 3
        on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert on_disk["langfuse"]["secret_key"] == "sk-real"

    def test_rollback_after_a_secret_rotation_keeps_the_new_secret(
        self, cfg_path
    ) -> None:
        """Rolling back non-secret settings must not silently revert a
        credential rotation — it cannot, and must not pretend to."""
        mod.apply_update(Cfg, {"langfuse": {"secret_key": "sk-rotated"}}, cfg_path)
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        restored, _, _ = mod.rollback(Cfg, 1, cfg_path)
        assert restored["langfuse"]["secret_key"] == "sk-rotated"


class TestDeepMerge:
    def test_nested_dicts_merge_rather_than_replace(self) -> None:
        out = mod.deep_merge({"a": {"x": 1, "y": 2}}, {"a": {"y": 3}})
        assert out == {"a": {"x": 1, "y": 3}}

    def test_inputs_are_not_mutated(self) -> None:
        existing = {"a": {"x": 1}}
        mod.deep_merge(existing, {"a": {"x": 2}})
        assert existing == {"a": {"x": 1}}

    def test_lists_are_replaced_wholesale(self) -> None:
        assert mod.deep_merge({"a": [1, 2, 3]}, {"a": [9]}) == {"a": [9]}
