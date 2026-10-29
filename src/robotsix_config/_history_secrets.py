"""Secret detection and masking for :mod:`robotsix_config.history`.

Private module: import the public names from :mod:`robotsix_config.history`.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from pydantic import BaseModel

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

    return cast("dict[str, Any]", walk(data, ()))


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

    return cast("dict[str, Any]", walk(data, ()))


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
                ) or isinstance(mv, (list, tuple)):
                    walk(mv, ev, submitted, path)
            return
        if isinstance(m, list):
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
                ) or isinstance(mv, (list, tuple)):
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
                elif (
                    isinstance(value, (list, tuple))
                    and index < len(r)
                    and isinstance(r[index], (list, tuple))
                ):
                    walk(r[index], value, path)

    walk(restored, live, ())
    return restored
