"""Tests for the append-only version sidecar: reading, recording, rotation."""

from __future__ import annotations

import os

import pytest

from robotsix_config import history as mod

from ._history_models import Cfg


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


class TestRotation:
    """The sidecar keeps only the newest ``max_versions()`` entries (default 10):
    unbounded sidecars grew to 50+ full config snapshots per component
    (2026-09-09). Oldest entries drop; version numbers keep increasing."""

    def _record_n(self, tmp_path, n: int) -> str:
        cfg = tmp_path / "config.json"
        cfg.write_text("{}")
        for i in range(1, n + 1):
            mod.record_version({"name": f"v{i}", "retries": i}, ["name"], Cfg, cfg)
        return str(cfg)

    def test_default_keeps_the_newest_ten(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv(mod.MAX_VERSIONS_ENV, raising=False)
        cfg = self._record_n(tmp_path, 12)
        entries = mod.read_versions(cfg)
        assert [e["version"] for e in entries] == list(range(3, 13))
        assert entries[-1]["data"]["name"] == "v12"
        assert mod.current_version(cfg) == 12
        # exactly ten lines on disk, no blank leftovers
        raw = mod.versions_path(cfg).read_text().splitlines()
        assert len(raw) == 10

    def test_numbering_continues_after_rotation(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv(mod.MAX_VERSIONS_ENV, "3")
        cfg = self._record_n(tmp_path, 5)
        assert [e["version"] for e in mod.read_versions(cfg)] == [3, 4, 5]
        v = mod.record_version({"name": "v6"}, ["name"], Cfg, cfg)
        assert v == 6
        assert [e["version"] for e in mod.read_versions(cfg)] == [4, 5, 6]

    def test_zero_disables_rotation(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv(mod.MAX_VERSIONS_ENV, "0")
        cfg = self._record_n(tmp_path, 15)
        assert len(mod.read_versions(cfg)) == 15

    def test_invalid_env_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv(mod.MAX_VERSIONS_ENV, "many")
        assert mod.max_versions() == mod.DEFAULT_MAX_VERSIONS
        monkeypatch.setenv(mod.MAX_VERSIONS_ENV, "-4")
        assert mod.max_versions() == mod.DEFAULT_MAX_VERSIONS
        monkeypatch.setenv(mod.MAX_VERSIONS_ENV, " 25 ")
        assert mod.max_versions() == 25

    @pytest.mark.skipif(os.name != "posix", reason="0600 is a POSIX-only guarantee")
    def test_rotation_keeps_file_private(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv(mod.MAX_VERSIONS_ENV, "2")
        cfg = self._record_n(tmp_path, 4)
        mode = mod.versions_path(cfg).stat().st_mode & 0o777
        assert mode == 0o600

    def test_trim_retries_on_transient_permission_error(
        self, tmp_path, monkeypatch
    ) -> None:
        """A Windows-style ``PermissionError`` on the first ``os.replace``
        (antivirus/backup handle) is retried instead of failing the trim."""
        import time

        from robotsix_config import _history_store

        monkeypatch.setattr(time, "sleep", lambda _s: None)
        path = tmp_path / "config.json.versions"
        path.write_text("".join(f'{{"version": {i}}}\n' for i in range(1, 6)))

        calls = 0
        original_replace = os.replace

        def flaky_replace(src, dst):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise PermissionError("simulated open handle")
            original_replace(src, dst)

        monkeypatch.setattr(os, "replace", flaky_replace)

        _history_store._trim_history(path, 2)

        assert calls == 2
        assert path.read_text().splitlines() == ['{"version": 4}', '{"version": 5}']
        assert [p.name for p in tmp_path.iterdir()] == [path.name]
