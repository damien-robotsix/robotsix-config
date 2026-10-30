"""The append-only version sidecar for :mod:`robotsix_config.history`.

Private module: import the public names from :mod:`robotsix_config.history`.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ._history_secrets import strip_secrets
from .config import _atomic_write_text, resolve_config_path

# Same logger name as before the split, so log filters keep matching.
logger = logging.getLogger("robotsix_config.history")

#: Environment variable that overrides :data:`DEFAULT_MAX_VERSIONS`.
MAX_VERSIONS_ENV = "ROBOTSIX_CONFIG_MAX_VERSIONS"
#: How many history entries the sidecar keeps by default.
DEFAULT_MAX_VERSIONS = 10


def versions_path(config_path: str | os.PathLike[str] | None = None) -> Path:
    """Return the history file's path for *config_path*.

    Args:
        config_path: The config file. Defaults to :func:`resolve_config_path`.

    Returns:
        ``<config_path>.versions`` — a sibling of the config file, so it
        travels with the same volume and the same backup.
    """
    target = Path(config_path) if config_path is not None else resolve_config_path()
    return target.with_suffix(target.suffix + ".versions")


def read_versions(
    config_path: str | os.PathLike[str] | None = None,
    *,
    include_data: bool = True,
) -> list[dict[str, Any]]:
    """Return every recorded version, oldest first.

    A missing history file is not an error — a component that has never been
    reconfigured simply has no history yet.

    Corrupt lines are skipped with a warning rather than raising. The history
    is a diagnostic aid; one bad line written by a killed process must not make
    the remaining history unreadable.

    Args:
        config_path: The config file. Defaults to :func:`resolve_config_path`.
        include_data: When ``False``, omit each entry's ``data`` payload.
            Listing versions in a UI needs the metadata but not every full
            config snapshot.

    Returns:
        A list of entries with ``version``, ``timestamp``, ``changed_keys``
        and (unless suppressed) ``data``.
    """
    try:
        raw = versions_path(config_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    entries: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            logger.warning(
                "skipping corrupt version line in %s", versions_path(config_path)
            )
            continue
        if not isinstance(entry, dict) or "version" not in entry:
            logger.warning(
                "skipping malformed version entry in %s", versions_path(config_path)
            )
            continue
        if not include_data:
            entry = {k: v for k, v in entry.items() if k != "data"}
        entries.append(entry)
    return entries


def current_version(config_path: str | os.PathLike[str] | None = None) -> int:
    """Return the newest recorded version number, or ``0`` when there is none."""
    entries = read_versions(config_path, include_data=False)
    if not entries:
        return 0
    return int(entries[-1]["version"])


def max_versions() -> int:
    """How many entries the history keeps: :data:`MAX_VERSIONS_ENV` when it is
    a non-negative integer, else :data:`DEFAULT_MAX_VERSIONS`. ``0`` = unbounded.
    """
    raw = os.environ.get(MAX_VERSIONS_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_MAX_VERSIONS
    try:
        value = int(raw.strip())
    except ValueError:
        logger.warning(
            "%s=%r is not an integer; keeping the default of %d versions",
            MAX_VERSIONS_ENV,
            raw,
            DEFAULT_MAX_VERSIONS,
        )
        return DEFAULT_MAX_VERSIONS
    if value < 0:
        logger.warning(
            "%s=%d is negative; keeping the default of %d versions",
            MAX_VERSIONS_ENV,
            value,
            DEFAULT_MAX_VERSIONS,
        )
        return DEFAULT_MAX_VERSIONS
    return value


def _trim_history(path: Path, keep: int) -> None:
    """Rewrite *path* so it holds only its newest *keep* lines (no-op when
    ``keep`` is 0 or the file already fits). Atomic: written to a sibling
    temp file and renamed over the sidecar, mode 0600 preserved best-effort.
    """
    if keep <= 0:
        return
    try:
        lines = [
            ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
    except FileNotFoundError:
        return
    if len(lines) <= keep:
        return
    kept = lines[-keep:]
    _atomic_write_text(path, "\n".join(kept) + "\n")
    logger.info(
        "trimmed %s to its newest %d version(s) (dropped %d)",
        path,
        keep,
        len(lines) - keep,
    )


def record_version(
    data: dict[str, Any],
    changed_keys: list[str],
    model_cls: type[BaseModel],
    config_path: str | os.PathLike[str] | None = None,
) -> int:
    """Append one entry to the history and return its version number.

    After appending, the sidecar is trimmed to its newest :func:`max_versions`
    entries (oldest dropped; numbering continues).

    Secret values are stripped from the stored snapshot (see
    :func:`strip_secrets`). ``changed_keys`` still names a changed secret, so
    the history records *that* a credential moved without recording what it
    became.

    ``model_cls`` is **required**, not optional. Without it, secret detection
    falls back to matching key names, which misses any secret whose field name
    is not in :data:`SECRET_KEY_SUFFIXES` — and this function writes to a
    long-lived append-only file, so a miss is permanent. The model always
    knows; make the caller supply it.

    Args:
        data: The config snapshot this version represents.
        changed_keys: Top-level keys that differ from the previous version.
        model_cls: The config model. Identifies which fields are secret.
        config_path: The config file. Defaults to :func:`resolve_config_path`.

    Returns:
        The new version number.
    """
    path = versions_path(config_path)
    version = current_version(config_path) + 1
    redacted = strip_secrets(data, model_cls)
    entry = {
        "version": version,
        "timestamp": datetime.now(UTC).isoformat(),
        "changed_keys": changed_keys,
        "data": redacted,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        # `redacted` has every SecretStr-declared field removed by
        # strip_secrets() above; this is the mitigation, not a violation.
        # See config-ownership.md.
        # codeql[py/clear-text-storage-sensitive-data]
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    with contextlib.suppress(OSError):
        path.chmod(0o600)  # best-effort; 0600 is a POSIX-only guarantee
    _trim_history(path, max_versions())
    return version
