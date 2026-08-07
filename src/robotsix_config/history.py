"""Append-only version history for a component's own config file.

**Each component owns its settings *and* their history.** The deploy plane does
not keep a mirror of component config — it reads the component's file when it
needs a value. So the record of "what changed, when, and what it was before"
has to live next to the config file itself, and every component has to keep it
the same way. This module is that one way.

The history is a JSONL sidecar at ``<config>.versions`` — one JSON object per
line, appended, never rewritten:

.. code-block:: json

    {"version": 3, "timestamp": "2026-08-07T22:03:27+00:00",
     "changed_keys": ["langfuse"], "data": {...}}

Append-only matters: a rollback writes a *new* entry restoring older values
rather than deleting the entries after it, so the history can always explain how
the current file came to look the way it does.

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

import json
import logging
import os
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ._errors import InvalidConfigError
from .config import _atomic_replace, load_config, resolve_config_path

__all__ = [
    "MASKED_SECRET_SENTINEL",
    "SECRET_KEY_SUFFIXES",
    "apply_update",
    "compute_changed_keys",
    "current_version",
    "deep_merge",
    "mask_secrets",
    "read_versions",
    "record_version",
    "rollback",
    "secret_paths",
    "versions_path",
]

logger = logging.getLogger("robotsix_config.history")

#: What a UI shows in place of a stored secret. A caller posting this value
#: back means "unchanged", not "set the secret to these asterisks".
MASKED_SECRET_SENTINEL = "**********"  # noqa: S105 — a mask, not a credential

#: Fallback secret detection for callers that pass no model. Matched as a
#: **suffix** of the key name. Prefer passing ``model_cls`` — the model knows.
SECRET_KEY_SUFFIXES: tuple[str, ...] = (
    "api_key",
    "api_token",
    "access_token",
    "auth_token",
    "password",
    "private_key",
    "secret",
    "secret_key",
    "token",
)


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


def record_version(
    data: dict[str, Any],
    changed_keys: list[str],
    config_path: str | os.PathLike[str] | None = None,
) -> int:
    """Append one entry to the history and return its version number.

    Args:
        data: The full config snapshot this version represents.
        changed_keys: Top-level keys that differ from the previous version.
        config_path: The config file. Defaults to :func:`resolve_config_path`.

    Returns:
        The new version number.
    """
    path = versions_path(config_path)
    version = current_version(config_path) + 1
    entry = {
        "version": version,
        "timestamp": datetime.now(UTC).isoformat(),
        "changed_keys": changed_keys,
        "data": deepcopy(data),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    try:
        path.chmod(0o600)
    except OSError:
        pass  # best-effort; 0600 is a POSIX-only guarantee
    return version


def compute_changed_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return the sorted top-level keys whose values differ.

    Nested changes are reported as the top-level key containing them. The
    history records the full snapshot, so this is a readable index into a
    change rather than a complete description of it.
    """
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def deep_merge(existing: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *update* into *existing*, returning a new dict.

    Nested dicts merge; every other type is replaced wholesale. Neither
    argument is mutated.

    A key absent from *update* keeps its existing value — that is what makes a
    partial update partial, and it is why a caller can send one field without
    having to echo the entire config back.
    """
    result = deepcopy(existing)
    for key, value in update.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def secret_paths(model_cls: type[BaseModel]) -> set[tuple[str, ...]]:
    """Return the dotted paths of every secret field in *model_cls*.

    Secrets are those the model marks ``writeOnly`` in its JSON Schema, which
    is what :class:`pydantic.SecretStr` produces. Reading the schema rather
    than the annotations means ``$ref``-ed submodels resolve naturally.

    Returns:
        A set of path tuples, e.g. ``{("langfuse", "secret_key")}``.
    """
    schema = model_cls.model_json_schema()
    defs = schema.get("$defs", {})
    found: set[tuple[str, ...]] = set()

    def walk(
        node: dict[str, Any], prefix: tuple[str, ...], seen: frozenset[str]
    ) -> None:
        ref = node.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", 1)[-1]
            if name in seen:  # a self-referential model would otherwise recurse forever
                return
            target = defs.get(name)
            if isinstance(target, dict):
                walk(target, prefix, seen | {name})
            return
        for key, sub in (node.get("properties") or {}).items():
            if not isinstance(sub, dict):
                continue
            if sub.get("writeOnly") or sub.get("format") == "password":
                found.add((*prefix, key))
            walk(sub, (*prefix, key), seen)

    walk(schema, (), frozenset())
    return found


def _is_secret(path: tuple[str, ...], known: set[tuple[str, ...]] | None) -> bool:
    """Return whether *path* names a secret field."""
    if known is not None:
        return path in known
    return path[-1].endswith(SECRET_KEY_SUFFIXES)


def mask_secrets(
    data: dict[str, Any],
    model_cls: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Return a copy of *data* with secret values replaced by the sentinel.

    Call this before returning config over HTTP. Only non-empty strings are
    masked — masking an unset field would tell the caller a secret exists
    where none does, and would then be posted back as "unchanged".

    Args:
        data: The config values.
        model_cls: The config model. Strongly preferred — without it, secrets
            are guessed from key names via :data:`SECRET_KEY_SUFFIXES`.
    """
    known = secret_paths(model_cls) if model_cls is not None else None

    def walk(node: dict[str, Any], prefix: tuple[str, ...]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in node.items():
            path = (*prefix, key)
            if isinstance(value, dict):
                out[key] = walk(value, path)
            elif _is_secret(path, known) and isinstance(value, str) and value:
                out[key] = MASKED_SECRET_SENTINEL
            else:
                out[key] = deepcopy(value)
        return out

    return walk(data, ())


def _preserve_secrets(
    merged: dict[str, Any],
    existing: dict[str, Any],
    update: dict[str, Any],
    known: set[tuple[str, ...]] | None,
) -> dict[str, Any]:
    """Restore on-disk secrets the caller did not genuinely change.

    A secret submitted as the mask sentinel or as an empty string means
    "unchanged" — the caller is echoing back what it was shown, not asking to
    erase the value. Treating either literally is how a form save silently
    destroys a credential.
    """

    def walk(
        m: dict[str, Any],
        e: dict[str, Any],
        u: dict[str, Any],
        prefix: tuple[str, ...],
    ) -> None:
        for key in list(m):
            path = (*prefix, key)
            submitted = u.get(key)
            if _is_secret(path, known) and submitted in (MASKED_SECRET_SENTINEL, ""):
                if key in e:
                    m[key] = deepcopy(e[key])
                continue
            if (
                isinstance(m.get(key), dict)
                and isinstance(e.get(key), dict)
                and isinstance(submitted, dict)
            ):
                walk(m[key], e[key], submitted, path)

    walk(merged, existing, update, ())
    return merged


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
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass  # best-effort; 0600 is a POSIX-only guarantee
        _atomic_replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
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

    changed = compute_changed_keys(existing, merged)
    if not changed:
        return merged, [], current_version(path)

    if not read_versions(path, include_data=False) and existing:
        # Record where we started, so the first real change has a "before".
        record_version(existing, ["initial"], path)

    _write_raw(path, merged)
    version = record_version(merged, changed, path)
    return merged, changed, version


def rollback(
    model_cls: type[BaseModel],
    target_version: int,
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[dict[str, Any], list[str], int]:
    """Restore *target_version*'s values as a **new** version.

    The history is never truncated: rolling back from version 5 to 2 produces
    version 6 whose contents equal version 2's. The intervening versions stay
    readable, which is the point of keeping a history at all.

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

    restored = deepcopy(match.get("data") or {})
    try:
        model_cls.model_validate(restored)
    except Exception as exc:
        raise InvalidConfigError(
            f"Version {target_version} no longer validates against the "
            f"current model:\n{exc}"
        ) from exc

    existing = _read_raw(path)
    changed = compute_changed_keys(existing, restored)
    if not changed:
        return restored, [], current_version(path)

    _write_raw(path, restored)
    version = record_version(restored, changed, path)
    return restored, changed, version


def load_with_history(
    model_cls: type[BaseModel],
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[BaseModel, int]:
    """Load the config and return it with its current version number.

    Convenience for a ``GET /config`` handler, which needs both.
    """
    model = load_config(model_cls, config_path)
    return model, current_version(config_path)
