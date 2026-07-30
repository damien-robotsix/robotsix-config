"""Property-based tests for config serialization invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("hypothesis")
from hypothesis import given  # type: ignore[import-not-found]
from hypothesis import strategies as st
from pydantic import BaseModel, SecretStr

from robotsix_config import dump_config, load_config
from robotsix_config.config import _reveal

# -- _reveal() property tests ------------------------------------------------


@given(st.text())
def test_reveal_identity_for_plain_strings(s: str) -> None:
    """``_reveal`` returns plain strings unchanged."""
    assert _reveal(s) is s


@given(st.integers())
def test_reveal_identity_for_ints(n: int) -> None:
    """``_reveal`` returns plain ints unchanged."""
    assert _reveal(n) is n


@given(st.text(max_size=200))
def test_reveal_secretstr(text: str) -> None:
    """``_reveal`` unwraps ``SecretStr`` to its cleartext value."""
    assert _reveal(SecretStr(text)) == text


@given(st.dictionaries(st.text(max_size=10), st.text(max_size=20)))
def test_reveal_dict_passthrough(d: dict[str, str]) -> None:
    """``_reveal`` preserves plain dicts with no SecretStr values."""
    assert _reveal(d) == d


@given(st.lists(st.text(max_size=20)))
def test_reveal_list_passthrough(lst: list[str]) -> None:
    """``_reveal`` preserves plain lists with no SecretStr values."""
    assert _reveal(lst) == lst


def test_reveal_set_of_secretstr() -> None:
    """``_reveal`` unwraps ``SecretStr`` inside a set (order-independent)."""
    s = {SecretStr("a"), SecretStr("b"), SecretStr("c")}
    values = _reveal(s)
    assert values == {"a", "b", "c"}


def test_reveal_frozenset_of_secretstr() -> None:
    """``_reveal`` unwraps ``SecretStr`` inside a frozenset."""
    fs = frozenset({SecretStr("x"), SecretStr("y")})
    values = _reveal(fs)
    assert values == frozenset({"x", "y"})


def test_reveal_tuple_of_secretstr() -> None:
    """``_reveal`` preserves tuple type while unwrapping SecretStr."""
    t = (SecretStr("a"), SecretStr("b"))
    result = _reveal(t)
    assert isinstance(result, tuple)
    assert result == ("a", "b")


def test_reveal_list_of_secretstr() -> None:
    """``_reveal`` preserves list type while unwrapping SecretStr."""
    lst = [SecretStr("x"), SecretStr("y")]
    result = _reveal(lst)
    assert isinstance(result, list)
    assert result == ["x", "y"]


# -- Container type preservation ---------------------------------------------


def test_reveal_empty_set_type() -> None:
    """``_reveal`` returns an empty set unchanged."""
    s: set[str] = set()
    result = _reveal(s)
    assert isinstance(result, set)
    assert len(result) == 0


def test_reveal_empty_frozenset_type() -> None:
    """``_reveal`` returns an empty frozenset unchanged."""
    fs: frozenset[str] = frozenset()
    result = _reveal(fs)
    assert isinstance(result, frozenset)
    assert len(result) == 0


def test_reveal_empty_tuple_type() -> None:
    """``_reveal`` returns an empty tuple unchanged."""
    result = _reveal(())
    assert isinstance(result, tuple)
    assert len(result) == 0


def test_reveal_empty_list_type() -> None:
    """``_reveal`` returns an empty list unchanged."""
    result = _reveal([])
    assert isinstance(result, list)
    assert len(result) == 0


# -- Nested structures -------------------------------------------------------


def test_reveal_deeply_nested_dict() -> None:
    """``_reveal`` unwraps SecretStr at arbitrary depth."""
    obj = {
        "outer": {
            "inner": {
                "secret": SecretStr("deep"),
                "plain": "visible",
                "nested_list": [
                    SecretStr("l1"),
                    SecretStr("l2"),
                ],
            }
        }
    }
    result = _reveal(obj)
    assert result["outer"]["inner"]["secret"] == "deep"
    assert result["outer"]["inner"]["plain"] == "visible"
    assert result["outer"]["inner"]["nested_list"] == ["l1", "l2"]


# -- Round-trip: dump_config → load_config -----------------------------------


class RoundTripModel(BaseModel):
    name: str = "default"
    count: int = 42
    flag: bool = False


def test_dump_load_round_trip(tmp_path: Path) -> None:
    """``dump_config`` followed by ``load_config`` yields the same config."""

    @given(cfg=st.builds(RoundTripModel))
    def check(cfg: RoundTripModel) -> None:
        target = tmp_path / "config.json"
        dump_config(cfg, target)
        back = load_config(RoundTripModel, target)
        assert back.model_dump() == cfg.model_dump()

    check()


# -- Round-trip with SecretStr ------------------------------------------------


class SecretRoundTripModel(BaseModel):
    api_key: SecretStr = SecretStr("")
    name: str = "svc"


def test_secret_round_trip(tmp_path: Path) -> None:
    """Config with ``SecretStr`` fields round-trips through dump/load."""

    @given(cfg=st.builds(SecretRoundTripModel))
    def check(cfg: SecretRoundTripModel) -> None:
        target = tmp_path / "config.json"
        dump_config(cfg, target)
        back = load_config(SecretRoundTripModel, target)
        assert back.model_dump() == cfg.model_dump()

    check()
