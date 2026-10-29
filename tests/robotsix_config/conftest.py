"""Fixtures shared by the ``robotsix_config.history`` test modules."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def cfg_path(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "name": "svc",
                "retries": 3,
                "langfuse": {
                    "host": "https://lf.example",
                    "public_key": "pk-real",
                    "secret_key": "sk-real",
                },
            }
        ),
        encoding="utf-8",
    )
    return p
