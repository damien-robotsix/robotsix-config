"""Tests for the deep merge used by partial config updates."""

from __future__ import annotations

from robotsix_config import history as mod


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
