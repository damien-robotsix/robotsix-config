"""Tests for secret detection, masking and stripping in the config history.

The failure this module exists to prevent: a partial config update that
destroys a secret the caller never meant to change. A UI shows a secret as
``"**********"``, the operator edits an unrelated field, the form posts every
field back, and the mask overwrites the real credential. That has cost this
fleet live credentials more than once, so it is tested here from several angles.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, SecretStr

from robotsix_config import history as mod
from robotsix_config._history_secrets import _is_secret

from ._history_models import Cfg, ListSecretsCfg, MapCfg


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


class TestSecretPathsThroughDataNamedSegments:
    """A secret under a map key or a list index must still be found.

    Before the wildcard, ``secret_paths`` stopped at ``properties`` and never
    descended into ``additionalProperties`` or ``items``. Every caller of
    ``_is_secret`` inherited the blind spot at once: ``mask_secrets`` returned
    the live credential in cleartext over HTTP, and the next save wrote the
    mask the UI had shown back over it.
    """

    def test_secret_under_a_map_key_is_found_as_a_wildcard(self) -> None:
        assert ("projects", mod.PATH_WILDCARD, "secret_key") in mod.secret_paths(MapCfg)

    def test_secret_under_a_list_index_is_found_as_a_wildcard(self) -> None:
        assert ("replicas", mod.PATH_WILDCARD, "secret_key") in mod.secret_paths(MapCfg)

    def test_map_of_bare_secrets_is_found(self) -> None:
        """dict[str, SecretStr] — the secret *is* the map value."""
        assert ("tokens", mod.PATH_WILDCARD) in mod.secret_paths(MapCfg)

    def test_non_secret_under_a_map_key_is_not_matched(self) -> None:
        paths = mod.secret_paths(MapCfg)
        assert ("projects", mod.PATH_WILDCARD, "public_key") not in paths

    def test_wildcard_does_not_match_a_shorter_or_longer_path(self) -> None:
        known = mod.secret_paths(MapCfg)
        assert not _is_secret(("projects", "a"), known)
        assert not _is_secret(("projects", "a", "secret_key", "deeper"), known)

    def test_map_secret_is_masked_before_leaving_the_process(self) -> None:
        out = mod.mask_secrets(
            {"projects": {"prod": {"public_key": "pk", "secret_key": "sk-real"}}},
            MapCfg,
        )
        assert out["projects"]["prod"]["secret_key"] == mod.MASKED_SECRET_SENTINEL
        assert out["projects"]["prod"]["public_key"] == "pk"

    def test_saving_an_edit_beside_a_map_secret_preserves_the_credential(
        self, tmp_path
    ) -> None:
        """The exact UI round-trip that destroyed credentials.

        A map node diffs whole, so editing the public key resubmits the masked
        secret alongside it. The mask means "unchanged", never "set it to
        literal asterisks".
        """
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps(
                {
                    "projects": {
                        "prod": {"public_key": "pk-old", "secret_key": "sk-real"}
                    }
                }
            ),
            encoding="utf-8",
        )
        mod.apply_update(
            MapCfg,
            {
                "projects": {
                    "prod": {
                        "public_key": "pk-new",
                        "secret_key": mod.MASKED_SECRET_SENTINEL,
                    }
                }
            },
            cfg,
        )
        on_disk = json.loads(cfg.read_text(encoding="utf-8"))
        assert on_disk["projects"]["prod"]["secret_key"] == "sk-real"
        assert on_disk["projects"]["prod"]["public_key"] == "pk-new"

    def test_map_secret_is_never_written_to_history(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"projects": {}}), encoding="utf-8")
        mod.apply_update(
            MapCfg,
            {"projects": {"prod": {"public_key": "pk", "secret_key": "sk-real"}}},
            cfg,
        )
        recorded = mod.versions_path(cfg).read_text(encoding="utf-8")
        assert "sk-real" not in recorded
        assert "projects (secret)" in recorded


class TestListNestedSecrets:
    """A secret inside a list element must be treated like any other secret.

    ``secret_paths`` already discovers a wildcard under ``items``, but the
    consumers walked only ``dict`` values, so a ``list[Langfuse]`` was opaque:
    the credential leaked over GET /config and into the append-only history.
    """

    def test_list_secret_is_masked_before_leaving_the_process(self) -> None:
        out = mod.mask_secrets(
            {"replicas": [{"public_key": "pk", "secret_key": "sk-real"}]},
            MapCfg,
        )
        assert out["replicas"][0]["secret_key"] == mod.MASKED_SECRET_SENTINEL
        assert out["replicas"][0]["public_key"] == "pk"

    def test_list_secret_is_never_written_to_history(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"replicas": []}), encoding="utf-8")
        mod.apply_update(
            MapCfg,
            {"replicas": [{"public_key": "pk", "secret_key": "sk-real"}]},
            cfg,
        )
        recorded = mod.versions_path(cfg).read_text(encoding="utf-8")
        assert "sk-real" not in recorded
        assert "replicas (secret)" in recorded

    def test_saving_an_edit_beside_a_list_secret_preserves_the_credential(
        self, tmp_path
    ) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps(
                {"replicas": [{"public_key": "pk-old", "secret_key": "sk-real"}]}
            ),
            encoding="utf-8",
        )
        mod.apply_update(
            MapCfg,
            {
                "replicas": [
                    {
                        "public_key": "pk-new",
                        "secret_key": mod.MASKED_SECRET_SENTINEL,
                    }
                ]
            },
            cfg,
        )
        on_disk = json.loads(cfg.read_text(encoding="utf-8"))
        assert on_disk["replicas"][0]["secret_key"] == "sk-real"
        assert on_disk["replicas"][0]["public_key"] == "pk-new"

    def test_rollback_keeps_live_list_secrets(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"replicas": [{"public_key": "pk", "secret_key": "sk-real"}]}),
            encoding="utf-8",
        )
        mod.apply_update(MapCfg, {"name": "a"}, cfg)
        mod.apply_update(MapCfg, {"name": "b"}, cfg)
        restored, _, _ = mod.rollback(MapCfg, 1, cfg)
        assert restored["replicas"][0]["secret_key"] == "sk-real"


class TestBareListSecrets:
    """A ``list[SecretStr]`` is itself secret at every index.

    These cover the scalar branches of the list walkers — the nested-model
    tests above only exercise the dict branches of those same loops.
    """

    def test_bare_list_secret_is_masked(self) -> None:
        out = mod.mask_secrets(
            {"secrets": ["sk-real"], "names": ["keep"]},
            ListSecretsCfg,
        )
        assert out["secrets"] == [mod.MASKED_SECRET_SENTINEL]
        assert out["names"] == ["keep"]

    def test_bare_list_secret_is_stripped(self) -> None:
        out = mod.strip_secrets(
            {"secrets": ["sk-real"], "names": ["keep"]},
            ListSecretsCfg,
        )
        assert out["secrets"] == []
        assert out["names"] == ["keep"]

    def test_saving_an_edit_beside_a_bare_list_secret_preserves_it(
        self, tmp_path
    ) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"secrets": ["sk-real"], "names": ["old"]}),
            encoding="utf-8",
        )
        mod.apply_update(
            ListSecretsCfg,
            {"secrets": [mod.MASKED_SECRET_SENTINEL], "names": ["new"]},
            cfg,
        )
        on_disk = json.loads(cfg.read_text(encoding="utf-8"))
        assert on_disk["secrets"] == ["sk-real"]
        assert on_disk["names"] == ["new"]

    def test_rollback_keeps_live_bare_list_secrets(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"secrets": ["sk-real"], "names": ["a"]}),
            encoding="utf-8",
        )
        mod.apply_update(ListSecretsCfg, {"names": ["b"]}, cfg)
        mod.apply_update(ListSecretsCfg, {"names": ["c"]}, cfg)
        restored, _, _ = mod.rollback(ListSecretsCfg, 1, cfg)
        assert restored["secrets"] == ["sk-real"]


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

    def test_record_version_requires_a_model(self) -> None:
        """Without a model, secret detection degrades to name-guessing — and
        this writes to a permanent append-only file, so a miss cannot be
        undone. The model must be supplied."""
        import inspect

        sig = inspect.signature(mod.record_version)
        assert sig.parameters["model_cls"].default is inspect.Parameter.empty

    def test_a_secret_whose_name_looks_ordinary_is_still_stripped(
        self, cfg_path
    ) -> None:
        """The case name-guessing would miss: a SecretStr field named
        something the suffix list does not match."""

        class Odd(BaseModel):
            webhook: SecretStr = SecretStr("")
            note: str = ""

        target = cfg_path.parent / "odd.json"
        target.write_text(
            json.dumps({"webhook": "hunter2", "note": "x"}), encoding="utf-8"
        )
        mod.apply_update(Odd, {"note": "y"}, target)
        assert "hunter2" not in mod.versions_path(target).read_text(encoding="utf-8")

    def test_rollback_after_a_secret_rotation_keeps_the_new_secret(
        self, cfg_path
    ) -> None:
        """Rolling back non-secret settings must not silently revert a
        credential rotation — it cannot, and must not pretend to."""
        mod.apply_update(Cfg, {"langfuse": {"secret_key": "sk-rotated"}}, cfg_path)
        mod.apply_update(Cfg, {"retries": 9}, cfg_path)
        restored, _, _ = mod.rollback(Cfg, 1, cfg_path)
        assert restored["langfuse"]["secret_key"] == "sk-rotated"
