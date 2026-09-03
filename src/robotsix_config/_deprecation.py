"""Runtime deprecation utilities for robotsix-config.

Provides :func:`deprecated`, a decorator that marks a callable as deprecated
and emits a :class:`DeprecationWarning` each time the wrapped callable is
invoked. The warning names the release in which the callable was deprecated,
the release in which it will be removed, and any migration guidance supplied by
the caller.

See the "Deprecation" subsection of ``CONTRIBUTING.md`` for the
deprecate-in-N / remove-in-next-major lifecycle policy this module supports.
"""

from __future__ import annotations

import functools
import warnings
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def _format_message(
    name: str,
    version: str,
    removed_in: str,
    message: str | None,
) -> str:
    """Build the human-readable ``DeprecationWarning`` text.

    Args:
        name: The qualified name of the deprecated callable.
        version: The release in which the callable became deprecated.
        removed_in: The release in which the callable will be removed.
        message: Optional migration guidance, e.g. the replacement to use.

    Returns:
        A single-line message combining all of the above.
    """
    text = (
        f"{name} is deprecated since version {version} "
        f"and will be removed in {removed_in}."
    )
    if message:
        text = f"{text} {message}"
    return text


def deprecated(
    version: str,
    removed_in: str,
    message: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Mark a callable as deprecated.

    The returned decorator wraps the target callable so that a
    :class:`DeprecationWarning` is emitted every time it is called. The
    wrapped callable otherwise behaves identically and preserves its name,
    docstring, and other metadata via :func:`functools.wraps`.

    Example:
        >>> @deprecated("0.7.0", "1.0.0", "Use new_function instead")
        ... def old_function() -> None: ...

    Args:
        version: The release in which the callable became deprecated.
        removed_in: The release in which the callable will be removed.
        message: Optional migration guidance, e.g. the replacement to use.

    Returns:
        A decorator that wraps the target callable and emits a
        ``DeprecationWarning`` each time it is called.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        warning_message = _format_message(
            func.__qualname__, version, removed_in, message
        )

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            warnings.warn(warning_message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return wrapper

    return decorator
