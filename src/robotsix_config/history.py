"""Append-only version history for a component's own config file.

**Each component owns its settings *and* their history.** The deploy plane does
not keep a mirror of component config — it reads the component's file when it
needs a value. So the record of "what changed, when, and what it was before"
has to live next to the config file itself, and every component has to keep it
the same way. This module is that one way.

The history is a JSONL sidecar at ``<config>.versions`` — one JSON object per
line, appended; only the newest :func:`max_versions` entries are kept (default
10, ``ROBOTSIX_CONFIG_MAX_VERSIONS``; ``0`` keeps everything):

.. code-block:: json

    {"version": 3, "timestamp": "2026-08-07T22:03:27+00:00",
     "changed_keys": ["langfuse (secret)"], "data": {...}}

Append matters: a rollback writes a *new* entry restoring older values rather
than deleting the entries after it, so the retained history always explains how
the current file came to look the way it does. Rotation only drops the OLDEST
entries — version numbers keep increasing, and a version that has rotated out
can no longer be rolled back to (2026-09-09: unbounded sidecars grew to 50+
full config snapshots per component; the operator default is 10).

**Secret values are never written to the history** — only the fact that a
secret-bearing key changed, via the ``" (secret)"`` suffix in ``changed_keys``.
A history file outlives the moment it was written; a credential recorded in it outlives
every later rotation of that credential. The deliberate consequence is that
:func:`rollback` restores everything *except* secrets, carrying the live ones
forward instead.

- :func:`read_versions` / :func:`current_version` — inspect the history.
- :func:`apply_update` — the whole of ``PUT /config``: deep-merge, preserve
  secrets the caller did not resubmit, validate, write, record.
- :func:`rollback` — restore an earlier version as a new version.
- :func:`mask_secrets` — mask before returning config over HTTP.

Why :func:`apply_update` is one call rather than four: partial config updates
have a failure mode that has cost this fleet credentials more than once. A UI
renders a secret as a masked placeholder, the operator edits an unrelated field,
the form posts every field back, and the masked placeholder overwrites the real
secret with ``"**********"`` — or with ``""``. Any component hand-rolling
merge-then-write will eventually reintroduce it, so the merge and the secret
preservation are not separable steps.

Secrets are identified from the model itself — fields declared
:class:`pydantic.SecretStr` are marked ``writeOnly`` in the JSON Schema, and
that marking is authoritative. Callers with no model can fall back to
:data:`SECRET_KEY_SUFFIXES` name matching, which is a heuristic and is only a
fallback.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ._errors import InvalidConfigError
from ._history_merge import compute_changed_keys, deep_merge
from ._history_secrets import (
    MASKED_SECRET_SENTINEL,
    SECRET_KEY_SUFFIXES,
    _carry_secrets_forward,
    _preserve_secrets,
    mask_secrets,
    secret_paths,
)
from ._history_secrets import (
    PATH_WILDCARD as PATH_WILDCARD,  # noqa: PLC0414 -- explicit re-export
)
from ._history_secrets import (
    strip_secrets as strip_secrets,  # noqa: PLC0414 -- explicit re-export
)
from ._history_store import (
    DEFAULT_MAX_VERSIONS,
    MAX_VERSIONS_ENV,
    current_version,
    max_versions,
    read_versions,
    record_version,
    versions_path,
)
from .config import _atomic_replace, load_config, resolve_config_path

__all__ = [
    "DEFAULT_MAX_VERSIONS",
    "MASKED_SECRET_SENTINEL",
    "MAX_VERSIONS_ENV",
    "SECRET_KEY_SUFFIXES",
    "apply_update",
    "compute_changed_keys",
    "current_version",
    "deep_merge",
    "mask_secrets",
    "max_versions",
    "read_versions",
    "record_version",
    "rollback",
    "secret_paths",
    "versions_path",
]


def _read_raw(path: Path) -> dict[str, Any]:
    """Return the config file's raw contents, or ``{}`` when absent."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidConfigError(f"Config in {path} is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise InvalidConfigError(f"Config in {path} must be a JSON object")
    return loaded


def _write_raw(path: Path, data: dict[str, Any]) -> None:
    """Atomically write *data* to *path* with ``0600`` permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        suffix=".tmp", prefix=path.name + ".", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fd)
        with contextlib.suppress(OSError):
            os.chmod(tmp, 0o600)  # best-effort; 0600 is a POSIX-only guarantee
        _atomic_replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def apply_update(
    model_cls: type[BaseModel],
    update: dict[str, Any],
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[dict[str, Any], list[str], int]:
    """Apply a partial config update, then record it as a new version.

    This is the whole of ``PUT /config``, in the order that order matters:

    1. Deep-merge *update* into the file's current contents.
    2. Restore any secret submitted as masked or blank (see
       :func:`mask_secrets`).
    3. Validate the result against *model_cls* — **before** touching the file.
    4. Write atomically, then append a history entry.

    Validation precedes the write so a rejected update leaves the file exactly
    as it was. A component that writes first and validates afterwards will
    crash-loop on its next restart, having persisted config its own model
    refuses to load.

    Args:
        model_cls: The component's config model.
        update: Partial values. Keys absent here keep their current values.
        config_path: The config file. Defaults to :func:`resolve_config_path`.

    Returns:
        ``(merged, changed_keys, version)``. ``changed_keys`` is empty and no
        version is recorded when the update is a no-op.

    Raises:
        InvalidConfigError: The merged config fails validation. The file is
            unchanged.
    """
    path = Path(config_path) if config_path is not None else resolve_config_path()
    existing = _read_raw(path)

    merged = deep_merge(existing, update)
    merged = _preserve_secrets(merged, existing, update, secret_paths(model_cls))

    try:
        model_cls.model_validate(merged)
    except Exception as exc:
        raise InvalidConfigError(f"Rejected config update for {path}:\n{exc}") from exc

    changed = compute_changed_keys(existing, merged, model_cls)
    if not changed:
        return merged, [], current_version(path)

    if not read_versions(path, include_data=False) and existing:
        # Record where we started, so the first real change has a "before".
        record_version(existing, ["initial"], model_cls, path)

    _write_raw(path, merged)
    version = record_version(merged, changed, model_cls, path)
    return merged, changed, version


def rollback(
    model_cls: type[BaseModel],
    target_version: int,
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[dict[str, Any], list[str], int]:
    """Restore *target_version*'s values as a **new** version.

    A rollback never deletes later entries: rolling back from version 5 to 2 produces
    version 6 whose contents equal version 2's. The intervening versions stay
    readable, which is the point of keeping a history at all.

    **Secrets are not rolled back.** The history stores no secret values (see
    :func:`strip_secrets`), so there is nothing to restore them from. Current
    secrets are carried across unchanged, and a rollback that was meant to
    undo a credential change must be followed by setting that credential
    explicitly. Returning a config with secrets silently blanked would be the
    worse failure — it reads as success and takes the component down at its
    next restart.

    Args:
        model_cls: The component's config model.
        target_version: The version to restore.
        config_path: The config file. Defaults to :func:`resolve_config_path`.

    Returns:
        ``(restored, changed_keys, new_version)``.

    Raises:
        InvalidConfigError: No such version, or the stored values no longer
            validate — which happens when the model has since dropped a field
            that version still carries.
    """
    path = Path(config_path) if config_path is not None else resolve_config_path()
    entries = read_versions(path)
    match = next((e for e in entries if int(e["version"]) == target_version), None)
    if match is None:
        available = [int(e["version"]) for e in entries]
        raise InvalidConfigError(
            f"No version {target_version} in {versions_path(path)}; have {available}"
        )

    existing_now = _read_raw(path)
    restored = _carry_secrets_forward(
        deepcopy(match.get("data") or {}), existing_now, secret_paths(model_cls)
    )
    try:
        model_cls.model_validate(restored)
    except Exception as exc:
        raise InvalidConfigError(
            f"Version {target_version} no longer validates against the "
            f"current model:\n{exc}"
        ) from exc

    changed = compute_changed_keys(existing_now, restored, model_cls)
    if not changed:
        return restored, [], current_version(path)

    _write_raw(path, restored)
    version = record_version(restored, changed, model_cls, path)
    return restored, changed, version


def load_with_history[ModelT: BaseModel](
    model_cls: type[ModelT],
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[ModelT, int]:
    """Load the config and return it with its current version number.

    Convenience for a ``GET /config`` handler, which needs both.

    Self-healing (key stripping) is handled by :func:`load_config` — see its
    docstring for details.
    """
    model = load_config(model_cls, config_path)
    return model, current_version(config_path)
