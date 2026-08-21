"""Test models used by the CLI tests."""

from __future__ import annotations

from pydantic import BaseModel, SecretStr


class AppSettings(BaseModel):
    """A minimal pydantic model for CLI testing."""

    api_key: SecretStr = SecretStr("")
    endpoint: str = "https://api.example.com"
    retries: int = 3


class NoFieldsModel(BaseModel):
    """A model with no fields — used to test key-completeness edge cases."""