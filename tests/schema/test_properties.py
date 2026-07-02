"""Property-based tests for the schema submodule."""

from __future__ import annotations

import json
import string

import pytest
import yaml
from pydantic import BaseModel, SecretStr, create_model

from robotsix_yaml_config.schema import (
    emit_deploy_schema,
    emit_deploy_schema_json,
    emit_deploy_template,
)

# hypothesis is a dev-only test dependency (declared in
# [project.optional-dependencies].dev).  Skip the whole module cleanly when it
# is unavailable so the rest of the suite still collects.
hypothesis = pytest.importorskip("hypothesis")
given = hypothesis.given
st = pytest.importorskip("hypothesis.strategies")

# --------------------------------------------------------------------------- #
#  Strategies                                                                 #
# --------------------------------------------------------------------------- #

_ID_ALPHABET = string.ascii_lowercase
_MODEL_NAME_ALPHABET = string.ascii_letters

_field_names = st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=8)

# Strategy for a (type, default) pair for scalar fields.
_scalar_fields = st.one_of(
    st.tuples(st.just(str), st.text(max_size=10)).map(lambda t: (t[0], t[1])),
    st.tuples(st.just(int), st.integers(-100, 100)).map(lambda t: (t[0], t[1])),
    st.tuples(
        st.just(float),
        st.floats(-100, 100, allow_nan=False, allow_infinity=False),
    ).map(lambda t: (t[0], t[1])),
    st.tuples(st.just(bool), st.booleans()).map(lambda t: (t[0], t[1])),
)

# Strategy for a (SecretStr, default) pair.
_secret_fields = st.text(max_size=10).map(lambda s: (SecretStr, SecretStr(s)))


@st.composite
def _field_specs(draw, *, min_fields: int = 1, max_fields: int = 6):
    """Generate a dict of field-name → (type, default) for create_model."""
    n = draw(st.integers(min_value=min_fields, max_value=max_fields))
    names = draw(st.lists(_field_names, min_size=n, max_size=n, unique=True))
    fields: dict[str, tuple[type, object]] = {}
    for name in names:
        # Mix scalar fields (with default), secret fields, and required scalar fields.
        kind = draw(
            st.sampled_from(["scalar_default", "secret_default", "scalar_required"])
        )
        if kind == "scalar_default":
            typ, default = draw(_scalar_fields)
        elif kind == "secret_default":
            typ, default = draw(_secret_fields)
        else:
            typ = draw(st.sampled_from([str, int, float, bool]))
            default = ...
        fields[name] = (typ, default)
    return fields


@st.composite
def pydantic_models(draw):
    """Generate a pydantic model class with a mix of field types."""
    fields = draw(_field_specs())
    name = "M" + draw(st.text(alphabet=_MODEL_NAME_ALPHABET, min_size=1, max_size=10))
    return create_model(name, **fields)


# --------------------------------------------------------------------------- #
#  emit_deploy_schema                                                         #
# --------------------------------------------------------------------------- #


@given(model_cls=pydantic_models())
def test_deploy_schema_has_object_structure(model_cls):
    """The emitted schema describes a JSON object."""
    schema = emit_deploy_schema(model_cls)
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
    assert "properties" in schema


@given(model_cls=pydantic_models())
def test_deploy_schema_fields_appear_in_properties(model_cls):
    """Every model field has a corresponding entry in schema properties."""
    schema = emit_deploy_schema(model_cls)
    props = schema["properties"]
    for name in model_cls.model_fields:
        assert name in props, f"Field {name!r} missing from schema properties"


@given(model_cls=pydantic_models())
def test_deploy_schema_secret_fields_marked(model_cls):
    """SecretStr fields are rendered as password/writeOnly."""
    schema = emit_deploy_schema(model_cls)
    props = schema["properties"]
    for name, field in model_cls.model_fields.items():
        # Check if the annotation is SecretStr (or contains it via Optional etc.)
        from typing import get_args

        ann = field.annotation
        is_secret = ann is SecretStr or SecretStr in get_args(ann)
        if is_secret:
            entry = props[name]
            assert entry.get("format") == "password", (
                f"Secret field {name!r} missing format=password"
            )
            assert entry.get("writeOnly") is True, (
                f"Secret field {name!r} missing writeOnly=True"
            )


@given(model_cls=pydantic_models())
def test_deploy_schema_required_fields_listed(model_cls):
    """Fields without defaults appear in the required list."""
    schema = emit_deploy_schema(model_cls)
    required = schema.get("required", [])
    for name, field in model_cls.model_fields.items():
        if field.is_required():
            assert name in required, f"Required field {name!r} missing from 'required'"


# --------------------------------------------------------------------------- #
#  emit_deploy_schema_json                                                    #
# --------------------------------------------------------------------------- #


@given(model_cls=pydantic_models())
def test_deploy_schema_json_roundtrip(model_cls):
    """Parsing the JSON output recovers the dict from emit_deploy_schema."""
    text = emit_deploy_schema_json(model_cls)
    assert json.loads(text) == emit_deploy_schema(model_cls)


@given(model_cls=pydantic_models())
def test_deploy_schema_json_trailing_newline(model_cls):
    """The JSON string ends with a single newline."""
    text = emit_deploy_schema_json(model_cls)
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


# --------------------------------------------------------------------------- #
#  emit_deploy_template                                                       #
# --------------------------------------------------------------------------- #


@given(model_cls=pydantic_models())
def test_deploy_template_yaml_parseable(model_cls):
    """The emitted YAML is valid and parseable to a dict."""
    text = emit_deploy_template(model_cls)
    data = yaml.safe_load(text)
    assert isinstance(data, dict)


@given(model_cls=pydantic_models())
def test_deploy_template_all_fields_present(model_cls):
    """Every model field appears in the emitted template."""
    data = yaml.safe_load(emit_deploy_template(model_cls))
    for name in model_cls.model_fields:
        assert name in data, f"Field {name!r} missing from template"


@given(model_cls=pydantic_models())
def test_deploy_template_secrets_are_empty_strings(model_cls):
    """SecretStr fields are rendered as empty strings in the template."""
    from typing import get_args

    data = yaml.safe_load(emit_deploy_template(model_cls))
    for name, field in model_cls.model_fields.items():
        ann = field.annotation
        is_secret = ann is SecretStr or SecretStr in get_args(ann)
        if is_secret:
            assert data[name] == "", (
                f"Secret field {name!r} not masked as empty string, got {data[name]!r}"
            )


@given(model_cls=pydantic_models())
def test_deploy_template_non_secret_defaults_preserved(model_cls):
    """Fields with non-SecretStr defaults are rendered with coerced defaults."""
    from enum import Enum
    from typing import get_args

    data = yaml.safe_load(emit_deploy_template(model_cls))
    for name, field in model_cls.model_fields.items():
        ann = field.annotation
        is_secret = ann is SecretStr or SecretStr in get_args(ann)
        if field.is_required():
            continue  # required fields get placeholders, not defaults
        if is_secret:
            continue  # secrets are always "" — tested separately
        default = field.get_default(call_default_factory=True)
        if isinstance(default, Enum):
            expected = default.value
        elif isinstance(default, BaseModel):
            # Nested model default: template renders nested dict; check type.
            assert isinstance(data[name], dict), (
                f"Nested model field {name!r} not rendered as dict"
            )
            continue
        elif isinstance(default, SecretStr):
            continue  # shouldn't happen without _is_secret, but be safe
        else:
            expected = default
        assert data[name] == expected, (
            f"Non-secret default {name!r}: expected {expected!r}, got {data[name]!r}"
        )
