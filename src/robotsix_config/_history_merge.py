"""Deep merge and change detection for :mod:`robotsix_config.history`.

Private module: import the public names from :mod:`robotsix_config.history`.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel

from ._history_secrets import _is_secret, secret_paths


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
