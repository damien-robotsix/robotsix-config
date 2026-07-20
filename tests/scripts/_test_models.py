"""Trivial Pydantic models used by test_check_schema_freshness."""

from __future__ import annotations

from pydantic import BaseModel


class SimpleModel(BaseModel):
    name: str = "default"
