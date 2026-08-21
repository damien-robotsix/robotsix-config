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
     "changed_keys": ["langfuse (secret)"], "data": {...}}

Append-only matters: a rollback writes a *new* entry restoring older values
rather than deleting the entries after it, so the history can always explain how
the current file came to look the way it does.

**Secret values are never written to the history** — only the fact that a
secret-bearing key changed, via the ``" (secret)"`` suffix in ``changed_keys``.
An append-only file accumulates forever; a credential recorded in it outlives
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
MASKED_SECRET_SENTINEL = "**********"  # noqa: S105 # nosec B105 — a mask, not a credential

#: Stands in for one path segment whose name is data rather than schema — a
#: key of an open-ended ``dict[str, X]`` or an index of a ``list[X]``. The
#: model cannot name those segments, so :func:`secret_paths` emits this and
#: :func:`_is_secret` matches any single segment against it.
PATH_WILDCARD = "*"

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


def strip_secrets(
    data: dict[str, Any],
    model_cls: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Return a copy of *data* with every secret value removed entirely.

    Not masked — **removed**. The history is a long-lived, append-only file;
    a credential written into it survives every later rotation of that
    credential and is readable by anything that can read the sidecar. Storing
    a mask instead would be almost as bad, because a rollback would then write
    the literal mask back into the live config as if it were the secret.

    The consequence, by design, is that :func:`rollback` cannot restore a
    previous secret. It restores everything else and leaves secrets at their
    current values.
    """
    known = secret_paths(model_cls) if model_cls is not None else None

    def walk(node: Any, prefix: tuple[str, ...]) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for key, value in node.items():
                path = (*prefix, key)
                if isinstance(value, (dict, list, tuple)):
                    out[key] = walk(value, path)
                elif _is_secret(path, known):
                    continue
                else:
                    out[key] = deepcopy(value)
            return out
        if isinstance(node, (list, tuple)):
            kept: list[Any] = []
            for index, item in enumerate(node):
                path = (*prefix, str(index))
                if isinstance(item, (dict, list, tuple)):
                    kept.append(walk(item, path))
                elif _is_secret(path, known):
                    continue
                else:
                    kept.append(deepcopy(item))
            return type(node)(kept)
        return deepcopy(node)

    return walk(data, ())


def record_version(
    data: dict[str, Any],
    changed_keys: list[str],
    model_cls: type[BaseModel],
    config_path: str | os.PathLike[str] | None = None,
) -> int:
    """Append one entry to the history and return its version number.

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
        # codeql[py/clear-text-storage-sensitive-data] -- `redacted` has every
        # SecretStr-declared field removed by strip_secrets() above; this is
        # the mitigation, not a violation. See config-ownership.md.
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    with contextlib.suppress(OSError):
        path.chmod(0o600)  # best-effort; 0600 is a POSIX-only guarantee
    return version


def compute_changed_keys(
    before: dict[str, Any],
    after: dict[str, Any],
    model_cls: type[BaseModel] | None = None,
) -> list[str]:
    """Return the sorted top-level keys whose values differ.

    Nested changes are reported as the top-level key containing them.

    A top-level key whose change is (or contains) a secret is reported as
    ``"<key> (secret)"``. The history stores no secret values, so this suffix
    is the only trace that a credential rotated — which is exactly what an
    operator asking "when did this key change?" needs.
    """
    known = secret_paths(model_cls) if model_cls is not None else None
    changed: list[str] = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) == after.get(key):
            continue
        if _touches_secret(key, before.get(key), after.get(key), known):
            changed.append(f"{key} (secret)")
        else:
            changed.append(key)
    return changed


def _touches_secret(
    key: str,
    before: Any,
    after: Any,
    known: set[tuple[str, ...]] | None,
) -> bool:
    """Return whether the change under *key* involves any secret field."""

    def walk(b: Any, a: Any, path: tuple[str, ...]) -> bool:
        if _is_secret(path, known) and b != a:
            return True
        if isinstance(a, dict) or isinstance(b, dict):
            bd = b if isinstance(b, dict) else {}
            ad = a if isinstance(a, dict) else {}
            return any(
                walk(bd.get(k), ad.get(k), (*path, k)) for k in set(bd) | set(ad)
            )
        if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
            bl = b if isinstance(b, (list, tuple)) else ()
            al = a if isinstance(a, (list, tuple)) else ()
            return any(
                walk(
                    bl[i] if i < len(bl) else None,
                    al[i] if i < len(al) else None,
                    (*path, str(i)),
                )
                for i in range(max(len(bl), len(al)))
            )
        return False

    return walk(before, after, (key,))


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

    A segment the model cannot name — the key of a ``dict[str, X]`` or the
    index of a ``list[X]`` — is emitted as :data:`PATH_WILDCARD`. Without
    descending past those, a secret nested inside an open-ended map is
    invisible to every caller of :func:`_is_secret`: it is returned unmasked
    over HTTP, and then overwritten with the mask on the next save.

    Returns:
        A set of path tuples, e.g. ``{("langfuse", "secret_key")}``, or
        ``{("langfuse_projects", "*", "secret_key")}`` for a map of models.
    """
    schema = model_cls.model_json_schema()
    defs = schema.get("$defs", {})
    found: set[tuple[str, ...]] = set()

    def is_secret_node(node: dict[str, Any]) -> bool:
        return bool(node.get("writeOnly") or node.get("format") == "password")

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
            if is_secret_node(sub):
                found.add((*prefix, key))
            walk(sub, (*prefix, key), seen)
        # Data-named segments: dict keys and list indices. `additionalProperties`
        # is `True`/`False` for a plain open dict, and a schema only when the
        # value type is declared, which is the case that can hide a secret.
        for child in (node.get("additionalProperties"), node.get("items")):
            if not isinstance(child, dict):
                continue
            if is_secret_node(child):
                found.add((*prefix, PATH_WILDCARD))
            walk(child, (*prefix, PATH_WILDCARD), seen)

    walk(schema, (), frozenset())
    return found


def _is_secret(path: tuple[str, ...], known: set[tuple[str, ...]] | None) -> bool:
    """Return whether *path* names a secret field.

    *path* is concrete — every segment is a real key from the config document.
    *known* may contain :data:`PATH_WILDCARD` segments standing for a map key
    or a list index, so membership alone is not enough.
    """
    if known is None:
        return path[-1].endswith(SECRET_KEY_SUFFIXES)
    if path in known:
        return True
    return any(
        len(pattern) == len(path)
        and all(p in (PATH_WILDCARD, seg) for seg, p in zip(path, pattern, strict=True))
        for pattern in known
        if PATH_WILDCARD in pattern
    )


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

    def walk(node: Any, prefix: tuple[str, ...]) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for key, value in node.items():
                path = (*prefix, key)
                if isinstance(value, (dict, list, tuple)):
                    out[key] = walk(value, path)
                elif _is_secret(path, known) and isinstance(value, str) and value:
                    out[key] = MASKED_SECRET_SENTINEL
                else:
                    out[key] = deepcopy(value)
            return out
        if isinstance(node, (list, tuple)):
            kept: list[Any] = []
            for index, item in enumerate(node):
                path = (*prefix, str(index))
                if isinstance(item, (dict, list, tuple)):
                    kept.append(walk(item, path))
                elif _is_secret(path, known) and isinstance(item, str) and item:
                    kept.append(MASKED_SECRET_SENTINEL)
                else:
                    kept.append(deepcopy(item))
            return type(node)(kept)
        return deepcopy(node)

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
        m: Any,
        e: Any,
        u: Any,
        prefix: tuple[str, ...],
    ) -> None:
        if isinstance(m, dict):
            e = e if isinstance(e, dict) else {}
            u = u if isinstance(u, dict) else {}
            for key in list(m):
                path = (*prefix, key)
                submitted = u.get(key)
                if _is_secret(path, known) and submitted in (
                    MASKED_SECRET_SENTINEL,
                    "",
                ):
                    if key in e:
                        m[key] = deepcopy(e[key])
                    continue
                mv = m.get(key)
                ev = e.get(key)
                if (
                    isinstance(mv, dict)
                    and isinstance(ev, dict)
                    and isinstance(submitted, dict)
                ):
                    walk(mv, ev, submitted, path)
                elif isinstance(mv, (list, tuple)):
                    walk(mv, ev, submitted, path)
            return
        if isinstance(m, (list, tuple)):
            e = e if isinstance(e, (list, tuple)) else ()
            u = u if isinstance(u, (list, tuple)) else ()
            for index in range(len(m)):
                path = (*prefix, str(index))
                submitted = u[index] if index < len(u) else None
                if _is_secret(path, known) and submitted in (
                    MASKED_SECRET_SENTINEL,
                    "",
                ):
                    if index < len(e):
                        m[index] = deepcopy(e[index])
                    continue
                mv = m[index]
                ev = e[index] if index < len(e) else None
                if (
                    isinstance(mv, dict)
                    and isinstance(ev, dict)
                    and isinstance(submitted, dict)
                ):
                    walk(mv, ev, submitted, path)
                elif isinstance(mv, (list, tuple)):
                    walk(mv, ev, submitted, path)

    walk(merged, existing, update, ())
    return merged


def _carry_secrets_forward(
    restored: dict[str, Any],
    live: dict[str, Any],
    known: set[tuple[str, ...]],
) -> dict[str, Any]:
    """Copy live secret values into *restored*, which has none.

    The history omits secrets, so a restored snapshot arrives with every
    secret field missing. Writing it as-is would wipe live credentials.
    """

    def walk(r: Any, live_node: Any, prefix: tuple[str, ...]) -> None:
        if isinstance(live_node, dict):
            for key, value in live_node.items():
                path = (*prefix, key)
                if _is_secret(path, known):
                    if key not in r:
                        r[key] = deepcopy(value)
                elif isinstance(value, dict):
                    target = r.get(key)
                    if isinstance(target, dict):
                        walk(target, value, path)
                elif isinstance(value, (list, tuple)):
                    target = r.get(key)
                    if isinstance(target, (list, tuple)):
                        walk(target, value, path)
        elif isinstance(live_node, (list, tuple)):
            for index, value in enumerate(live_node):
                path = (*prefix, str(index))
                if _is_secret(path, known):
                    if index >= len(r):
                        r.append(deepcopy(value))
                elif isinstance(value, dict):
                    if index < len(r) and isinstance(r[index], dict):
                        walk(r[index], value, path)
                elif isinstance(value, (list, tuple)):
                    if index < len(r) and isinstance(r[index], (list, tuple)):
                        walk(r[index], value, path)

    walk(restored, live, ())
    return restored


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

    The history is never truncated: rolling back from version 5 to 2 produces
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


def load_with_history(
    model_cls: type[BaseModel],
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[BaseModel, int]:
    """Load the config and return it with its current version number.

    Convenience for a ``GET /config`` handler, which needs both.

    Self-healing (key stripping) is handled by :func:`load_config` — see its
    docstring for details.
    """
    model = load_config(model_cls, config_path)
    return model, current_version(config_path)
