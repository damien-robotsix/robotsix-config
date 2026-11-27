"""The emitted config JSON Schema is itself a well-formed schema, and real
config instances conform to it."""

from __future__ import annotations

from enum import StrEnum

import pytest

pytest.importorskip("jsonschema")
import jsonschema
from pydantic import BaseModel, SecretStr

from robotsix_config import config_schema


class LogLevel(StrEnum):
    info = "info"
    debug = "debug"


class Imap(BaseModel):
    host: str = "localhost"
    port: int = 993


class MailConfig(BaseModel):
    log_level: LogLevel = LogLevel.info
    password: SecretStr = SecretStr("")
    imap: Imap = Imap()


# -- the emitted schema is a well-formed JSON Schema --------------------------


def test_schema_is_valid_against_draft_2020_12_meta_schema():
    """``config_schema`` must emit a document that is itself a valid schema."""
    jsonschema.Draft202012Validator.check_schema(config_schema(MailConfig))


# -- real config instances conform to the schema ------------------------------


def test_serialized_config_validates_against_schema():
    """The shape ``dump_config`` produces (cleartext secrets) is accepted."""
    jsonschema.validate(
        {
            "log_level": "debug",
            "password": "hunter2",
            "imap": {"host": "mx.example.com", "port": 993},
        },
        config_schema(MailConfig),
    )


def test_invalid_config_is_rejected_by_schema():
    """The schema actually constrains: ``port`` must be an integer."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"imap": {"port": "not-an-int"}},
            config_schema(MailConfig),
        )
