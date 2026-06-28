"""Property-based tests for overlay_env_vars."""

from __future__ import annotations

import copy

import pytest

from robotsix_yaml_config import overlay_env_vars

hypothesis = pytest.importorskip("hypothesis")
given = hypothesis.given
settings = hypothesis.settings
st = pytest.importorskip("hypothesis.strategies")

# A strategy producing flat (non-nested) dicts with string values —
# overlay_env_vars does not recurse into nested dicts.
flat_configs = st.dictionaries(
    keys=st.text(min_size=1, max_size=8),
    values=(
        st.integers()
        | st.text(max_size=10)
        | st.floats(allow_nan=False, allow_infinity=False)
    ),
    max_size=6,
)


@given(cfg=flat_configs)
def test_overlay_env_vars_idempotent(cfg):
    """Running overlay_env_vars twice is a no-op on the second call."""
    from _pytest.monkeypatch import MonkeyPatch

    with MonkeyPatch().context():
        # Set no env vars — no overlay should occur.
        result = overlay_env_vars(copy.deepcopy(cfg), "NOPREFIX")
        # Run a second time.
        result2 = overlay_env_vars(result, "NOPREFIX")
        assert result2 == result


@given(cfg=flat_configs)
def test_overlay_env_vars_preserves_keys(cfg):
    """No keys are removed from config."""
    original = copy.deepcopy(cfg)
    result = overlay_env_vars(cfg, "NOPREFIX")
    assert set(result.keys()) == set(original.keys())


@given(cfg=flat_configs)
def test_overlay_env_vars_no_env_vars_is_identity(cfg):
    """If no matching env vars exist, config is unchanged."""
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    with mp.context():
        # Clear all vars with the prefix.
        for key in cfg:
            mp.delenv(f"TESTPRE_{key.upper()}", raising=False)
        result = overlay_env_vars(copy.deepcopy(cfg), "TESTPRE")
        assert result == cfg


@given(cfg=flat_configs)
def test_overlay_env_vars_type_coercion_str(cfg):
    """Str type hint leaves string env values unchanged (default)."""
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    with mp.context():
        env_vals = {k: f"env_{k}" for k in cfg}
        for k, v in env_vals.items():
            mp.setenv(f"APP_{k.upper()}", v)
        result = overlay_env_vars(copy.deepcopy(cfg), "APP")
        for k in cfg:
            if isinstance(env_vals[k], str):
                assert isinstance(result[k], str)


@given(cfg=flat_configs)
def test_overlay_env_vars_returns_original(cfg):
    """overlay_env_vars mutates and returns config."""
    from _pytest.monkeypatch import MonkeyPatch

    with MonkeyPatch().context():
        result = overlay_env_vars(cfg, "NOPREFIX")
        assert result is cfg
