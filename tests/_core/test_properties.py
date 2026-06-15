"""Property-based tests for deep_merge and load_yaml_cascade."""

from __future__ import annotations

import copy
import functools

import pytest
import yaml

from robotsix_yaml_config import deep_merge, load_yaml_cascade

# hypothesis is a dev-only test dependency (declared in
# [project.optional-dependencies].dev).  Skip the whole module cleanly when it
# is unavailable so the rest of the suite still collects.
hypothesis = pytest.importorskip("hypothesis")
given = hypothesis.given
settings = hypothesis.settings
HealthCheck = hypothesis.HealthCheck
st = pytest.importorskip("hypothesis.strategies")

# A recursive strategy producing nested dicts.  The top-level value is always
# a dict, which is what deep_merge requires.
configs = st.recursive(
    st.dictionaries(
        st.text(max_size=5),
        st.integers() | st.text(max_size=5) | st.lists(st.integers(), max_size=3),
        max_size=4,
    ),
    lambda children: st.dictionaries(st.text(max_size=5), children, max_size=4),
    max_leaves=8,
)

# A YAML-safe strategy: printable lowercase-ASCII keys avoid lone surrogates
# that yaml.safe_dump cannot encode.
yaml_text = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=5,
)
yaml_configs = st.recursive(
    st.dictionaries(
        yaml_text,
        st.integers() | yaml_text | st.lists(st.integers(), max_size=3),
        max_size=4,
    ),
    lambda children: st.dictionaries(yaml_text, children, max_size=4),
    max_leaves=8,
)


@given(d=configs)
def test_deep_merge_idempotent(d):
    assert deep_merge(copy.deepcopy(d), copy.deepcopy(d)) == d


@given(d=configs)
def test_deep_merge_right_identity(d):
    assert deep_merge(copy.deepcopy(d), {}) == d


@given(d=configs)
def test_deep_merge_left_identity(d):
    assert deep_merge({}, copy.deepcopy(d)) == d


@given(base=configs, overlay=configs)
def test_deep_merge_returns_base(base, overlay):
    result = deep_merge(base, overlay)
    assert result is base


@given(base=configs, overlay=configs)
def test_deep_merge_overlay_isolated_from_base(base, overlay):
    result = deep_merge(copy.deepcopy(base), overlay)
    snapshot = copy.deepcopy(result)
    overlay.clear()
    assert result == snapshot


@given(base=configs, overlay=configs)
def test_deep_merge_last_layer_wins_for_non_dict(base, overlay):
    result = deep_merge(copy.deepcopy(base), copy.deepcopy(overlay))
    for key, value in overlay.items():
        if not isinstance(value, dict):
            assert result[key] == value


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(layer_dicts=st.lists(yaml_configs, max_size=4))
def test_load_yaml_cascade_is_left_fold(layer_dicts, tmp_path):
    # tmp_path is function-scoped but Hypothesis re-runs the body many times,
    # so isolate each example's files in a fresh uniquely-named subdirectory.
    sub = tmp_path / f"ex_{len(layer_dicts)}_{abs(hash(tmp_path)) % 1000}"
    counter = 0
    while sub.exists():
        counter += 1
        sub = tmp_path / f"ex_{len(layer_dicts)}_{counter}"
    sub.mkdir()

    layers = []
    for i, d in enumerate(layer_dicts):
        path = sub / f"layer_{i}.yaml"
        path.write_text(yaml.safe_dump(d), encoding="utf-8")
        layers.append((path, True))

    expected = functools.reduce(deep_merge, [copy.deepcopy(d) for d in layer_dicts], {})
    assert load_yaml_cascade(layers) == expected
