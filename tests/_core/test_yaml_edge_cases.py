"""Edge-case tests for ``read_yaml_file`` covering YAML format features
that are otherwise untested: anchors, tags, type coercion, null handling,
Unicode, multi-document streams, block scalars, and flow style.
"""

from __future__ import annotations

import pytest

from robotsix_yaml_config import read_yaml_file

# -- helpers ------------------------------------------------------------------


def _wr(path, content: str) -> None:
    """Write *content* (with dedented leading whitespace) to *path*."""
    path.write_text(content, encoding="utf-8")


# -- anchors & aliases --------------------------------------------------------


@pytest.mark.parametrize(
    ("yaml_content", "expected"),
    [
        # Basic anchor / alias
        (
            "defaults: &d\n  x: 1\n  y: 2\noverlay:\n  <<: *d\n  z: 3\n",
            {"defaults": {"x": 1, "y": 2}, "overlay": {"x": 1, "y": 2, "z": 3}},
        ),
        # Multiple aliases to same anchor
        (
            "a: &anchor\n  k: v\nb: *anchor\nc: *anchor\n",
            {"a": {"k": "v"}, "b": {"k": "v"}, "c": {"k": "v"}},
        ),
    ],
)
def test_read_yaml_file_anchors_aliases(yaml_content, expected, tmp_path):
    p = tmp_path / "anchors.yaml"
    _wr(p, yaml_content)
    assert read_yaml_file(p) == expected


# -- tags ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("yaml_content", "expected"),
    [
        # !!str forces string representation
        ("a: !!str 123\n", {"a": "123"}),
        ("a: !!str true\n", {"a": "true"}),
        # !!null
        ("a: !!null null\n", {"a": None}),
    ],
)
def test_read_yaml_file_tags(yaml_content, expected, tmp_path):
    p = tmp_path / "tags.yaml"
    _wr(p, yaml_content)
    assert read_yaml_file(p) == expected


# -- type coercion ------------------------------------------------------------


@pytest.mark.parametrize(
    ("yaml_content", "expected"),
    [
        # Boolean coercion (yes/no/true/false/on/off)
        (
            "a: yes\nb: true\nc: no\nd: false\ne: on\nf: off\n",
            {"a": True, "b": True, "c": False, "d": False, "e": True, "f": False},
        ),
        # Float coercion (1e3 is NOT coerced by safe_load — YAML 1.2)
        ("a: 3.14\nb: -0.5\n", {"a": 3.14, "b": -0.5}),
        # Integer vs quoted string
        ("a: 1\nb: '1'\nc: 0\n", {"a": 1, "b": "1", "c": 0}),
        # Hex integer (octal 0o77 is NOT coerced by safe_load)
        ("a: 0xFF\n", {"a": 255}),
    ],
)
def test_read_yaml_file_type_coercion(yaml_content, expected, tmp_path):
    p = tmp_path / "coercion.yaml"
    _wr(p, yaml_content)
    assert read_yaml_file(p) == expected


# -- null values --------------------------------------------------------------


@pytest.mark.parametrize(
    ("yaml_content", "expected"),
    [
        # Explicit nulls
        (
            "a: ~\nb: null\nc: Null\nd: NULL\n",
            {"a": None, "b": None, "c": None, "d": None},
        ),
        # Empty value (key with no value)
        ("a:\nb: 1\n", {"a": None, "b": 1}),
        # Empty value nested
        ("outer:\n  inner:\n", {"outer": {"inner": None}}),
    ],
)
def test_read_yaml_file_null_values(yaml_content, expected, tmp_path):
    p = tmp_path / "nulls.yaml"
    _wr(p, yaml_content)
    assert read_yaml_file(p) == expected


# -- unicode keys & values ----------------------------------------------------


@pytest.mark.parametrize(
    ("yaml_content", "expected"),
    [
        # Non-ASCII keys
        ("café: 1\nпривет: 2\n", {"café": 1, "привет": 2}),
        # Emoji values
        ("greeting: 👋\nflag: 🏳️‍🌈\n", {"greeting": "👋", "flag": "🏳️‍🌈"}),
        # CJK keys
        ("設定: value\n", {"設定": "value"}),
        # Zero-width characters in values
        ("zwsp: '​'\n", {"zwsp": "\u200b"}),
    ],
)
def test_read_yaml_file_unicode(yaml_content, expected, tmp_path):
    p = tmp_path / "unicode.yaml"
    _wr(p, yaml_content)
    assert read_yaml_file(p) == expected


# -- multi-document streams ---------------------------------------------------


@pytest.mark.parametrize(
    "yaml_content",
    [
        # Two documents separated by ---
        "a: 1\n---\nb: 2\n",
        # Three documents with ... terminator
        "a: 1\n...\n---\nb: 2\n",
    ],
)
def test_read_yaml_file_multi_document_raises(yaml_content, tmp_path):
    """safe_load uses get_single_data(), which rejects multiple documents."""
    from robotsix_yaml_config import YamlParseError

    p = tmp_path / "multi.yaml"
    _wr(p, yaml_content)
    with pytest.raises(YamlParseError, match="YAML parse error"):
        read_yaml_file(p)


def test_read_yaml_file_single_doc_with_leading_separator(tmp_path):
    """A single document prefixed with --- is fine."""
    p = tmp_path / "single.yaml"
    _wr(p, "---\na: 1\n")
    assert read_yaml_file(p) == {"a": 1}


# -- block scalars ------------------------------------------------------------


@pytest.mark.parametrize(
    ("yaml_content", "expected"),
    [
        # Literal block scalar preserves newlines
        ("a: |\n  line one\n  line two\n", {"a": "line one\nline two\n"}),
        # Literal with strip chomping indicator
        ("a: |-\n  one\n  two\n", {"a": "one\ntwo"}),
        # Folded block scalar folds newlines to spaces
        ("a: >\n  line one\n  line two\n", {"a": "line one line two\n"}),
        # Folded with strip
        ("a: >-\n  one\n  two\n", {"a": "one two"}),
    ],
)
def test_read_yaml_file_block_scalars(yaml_content, expected, tmp_path):
    p = tmp_path / "scalars.yaml"
    _wr(p, yaml_content)
    assert read_yaml_file(p) == expected


# -- flow style ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("yaml_content", "expected"),
    [
        # Flow mapping
        ("a: {x: 1, y: 2}\n", {"a": {"x": 1, "y": 2}}),
        # Flow sequence
        ("items: [1, 2, 3]\n", {"items": [1, 2, 3]}),
        # Nested flow
        ("a: {b: {c: 1}}\n", {"a": {"b": {"c": 1}}}),
    ],
)
def test_read_yaml_file_flow_style(yaml_content, expected, tmp_path):
    p = tmp_path / "flow.yaml"
    _wr(p, yaml_content)
    assert read_yaml_file(p) == expected
