"""Property-based tests for flatten_config."""

from __future__ import annotations

import copy
import random

import pytest

from robotsix_yaml_config import flatten_config

hypothesis = pytest.importorskip("hypothesis")
given = hypothesis.given
settings = hypothesis.settings
st = pytest.importorskip("hypothesis.strategies")

# Strategy: nested dicts with string/integer/text list leaves.
# Follow the same recursive pattern as tests/_core/test_properties.py.
nested_configs = st.recursive(
    st.dictionaries(
        st.text(min_size=1, max_size=5),
        st.integers() | st.text(max_size=5) | st.lists(st.integers(), max_size=3),
        max_size=4,
    ),
    lambda children: st.dictionaries(
        st.text(min_size=1, max_size=5), children, max_size=4
    ),
    max_leaves=8,
)

# Alias map: dotted-path keys mapping to alias-name values.
alias_map_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=10),
    values=st.text(min_size=1, max_size=10),
    max_size=6,
)


@given(nested=nested_configs, alias_map=alias_map_strategy)
def test_flatten_result_keys_are_alias_values(nested, alias_map):
    """Every key in the result is a value from alias_map (no-extra-keys)."""
    result = flatten_config(copy.deepcopy(nested), alias_map)
    alias_values = set(alias_map.values())
    assert result.keys() <= alias_values


@given(nested=nested_configs)
def test_flatten_empty_alias_map_returns_empty(nested):
    """No alias_map → no output."""
    assert flatten_config(copy.deepcopy(nested), {}) == {}


@given(nested=nested_configs, alias_map=alias_map_strategy)
def test_flatten_dict_valued_result_stopping_rule(nested, alias_map):
    """A dict-valued alias emitted by flatten_config is not re-flattened.

    Feed the result back through flatten_config with the same alias_map:
    any dict-valued entry is emitted as-is (stopping rule), so the second
    pass produces identical output for those entries.  If the alias itself
    is not a key in alias_map the stopping rule doesn't apply — but at
    minimum the returned dicts are unchanged between passes.
    """
    result = flatten_config(copy.deepcopy(nested), alias_map)
    re_result = flatten_config(copy.deepcopy(result), alias_map)
    for key, value in re_result.items():
        if isinstance(value, dict):
            assert isinstance(result.get(key), dict)
            assert result[key] == value


@given(nested=nested_configs)
def test_flatten_identity_alias_map_idempotent(nested):
    """Flattening twice with an identity alias_map yields the same result."""

    def collect_paths(d: dict, prefix: str = "") -> dict[str, str]:
        paths: dict[str, str] = {}
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            paths[full] = full
            if isinstance(v, dict):
                paths.update(collect_paths(v, full))
        return paths

    identity_map = collect_paths(nested)
    if not identity_map:
        return  # empty input is a trivial case
    result = flatten_config(copy.deepcopy(nested), identity_map)
    result2 = flatten_config(copy.deepcopy(result), identity_map)
    assert result == result2


@given(nested=nested_configs)
def test_flatten_reachable_mapped_keys_appear(nested):
    """If alias_map contains a path that exists in nested, the alias appears."""

    def collect_leaves(d: dict, prefix: str = "") -> list[str]:
        leaves: list[str] = []
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                leaves.extend(collect_leaves(v, full))
            else:
                leaves.append(full)
        return leaves

    leaves = collect_leaves(nested)
    if not leaves:
        return
    reachable_path = random.choice(leaves)
    alias_map = {reachable_path: "target_alias"}
    result = flatten_config(copy.deepcopy(nested), alias_map)
    assert "target_alias" in result
    assert result["target_alias"] is not None


@given(nested=nested_configs)
def test_flatten_unreachable_mapped_keys_absent(nested):
    """If alias_map keys don't exist in nested, they produce no output."""
    unreachable_map = {"this.path.does.not.exist.at.all": "unreachable"}
    result = flatten_config(copy.deepcopy(nested), unreachable_map)
    assert result == {}
