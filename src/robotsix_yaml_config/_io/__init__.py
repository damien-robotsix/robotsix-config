"""Writing a config file with restrictive ``0600``/``0700`` permissions.

Backend-agnostic: operates on a plain dict, so it belongs in the core (no
pydantic). Enforcing the permission in shared code — rather than per-repo or
in docstrings only — is what makes the "secrets on disk are ``0600``"
guarantee real across the stack.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

import yaml

_FILE_MODE = 0o600
_DIR_MODE = 0o700


def write_config_file(path: str | os.PathLike[str], data: dict[str, Any]) -> Path:
    """Write *data* as YAML to *path* with ``0600`` perms in a ``0700`` dir.

    The parent directory is created if needed and tightened to ``0700``; the
    file is created with an explicit ``0600`` mode *before* any content is
    written, so the secret bytes never briefly exist under a laxer mode. A
    pre-existing file with laxer permissions is tightened after the write.

    Returns the resolved :class:`~pathlib.Path`.
    """
    target = Path(path)
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    # Tightening may fail on shared/mounted dirs or Windows — best effort.
    with contextlib.suppress(PermissionError, NotImplementedError):
        parent.chmod(_DIR_MODE)

    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _FILE_MODE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)
    finally:
        # If the file pre-existed with a laxer mode, O_CREAT won't fix it.
        with contextlib.suppress(PermissionError, NotImplementedError):
            target.chmod(_FILE_MODE)
    return target
