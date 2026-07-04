from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def write_config():
    """Write a Python dict as pretty-printed JSON to *path*, return *path*."""
    def _write(path: Path, obj) -> Path:
        path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
        return path
    return _write
