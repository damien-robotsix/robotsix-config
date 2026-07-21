"""Load, dump, and describe typed configuration.

**One pydantic model, one JSON file.** The file is the single source of config
values — there is no environment overlay and no CLI-merge, so config can't drift
across sources. The model's own field defaults fill anything the file omits.

- :func:`load_config` — read the one JSON file and validate it into the model.
- :func:`dump_config` — write the model back to the ``0600`` JSON file
  (secrets in cleartext, for the app to read back).
- :func:`config_schema` / :func:`config_schema_json` — the model's JSON Schema,
  for a deploy UI to render typed, validated inputs.
- :func:`resolve_config_path` — the one file's location
  (``ROBOTSIX_CONFIG_FILE`` or ``config/config.json``).

Secrets are declared with :class:`pydantic.SecretStr`: masked on read, written
in cleartext into the ``0600`` file, and marked in the JSON Schema as
``{"type": "string", "format": "password", "writeOnly": true}``.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr, ValidationError

from .._errors import InvalidConfigError


class ConfigModel(BaseModel):
    """Canonical base class for typed configuration models.

    Subclass this to define your component's configuration schema::

        class MyConfig(ConfigModel):
            api_key: SecretStr
            endpoint: str = "https://api.example.com"

    Secrets declared as :class:`pydantic.SecretStr` are automatically masked
    on read, written in cleartext into the ``0600`` config file by
    :func:`dump_config`, and marked ``writeOnly`` in the JSON Schema produced
    by :func:`config_schema`.
    """


CONFIG_FILE_ENV = "ROBOTSIX_CONFIG_FILE"
DEFAULT_CONFIG_PATH = Path("config/config.json")


def resolve_config_path() -> Path:
    """The one config file: ``ROBOTSIX_CONFIG_FILE`` or ``config/config.json``.

    This only *locates* the file (e.g. for a mounted deploy); it never carries
    config values.

    Returns:
        The resolved config file path.
    """
    env = os.environ.get(CONFIG_FILE_ENV)
    return Path(env) if env else DEFAULT_CONFIG_PATH


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise InvalidConfigError(f"Invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise InvalidConfigError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        kind = type(data).__name__
        raise InvalidConfigError(
            f"Config top level in {path} must be a JSON object, got {kind}"
        )
    return data


def load_config[ModelT: BaseModel](
    model_cls: type[ModelT],
    path: str | os.PathLike[str] | None = None,
) -> ModelT:
    """Load the one JSON config file and validate it into *model_cls*.

    Values come from exactly one file — *path* if given, else
    :func:`resolve_config_path`. There is no environment overlay and no
    CLI-merge; the model's own field defaults fill anything the file omits, so a
    missing file means "all defaults" (and errors only if a field is required and
    undefaulted). Raises :class:`InvalidConfigError` on bad JSON or a validation
    failure.
    """
    target = Path(path) if path is not None else resolve_config_path()
    data = _read_json(target)
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise InvalidConfigError(f"Config in {target} is invalid:\n{exc}") from exc


def _reveal(obj: Any) -> Any:
    """Recursively replace :class:`SecretStr` with its cleartext value."""
    if isinstance(obj, SecretStr):
        # codeql[py/clear-text-storage-sensitive-data]
        # ^^ intentional per config-standard §3
        return obj.get_secret_value()
    if isinstance(obj, dict):
        return {k: _reveal(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_reveal(v) for v in obj)
    if isinstance(obj, (set, frozenset)):
        return type(obj)(_reveal(v) for v in obj)
    return obj


def dump_config(
    model: BaseModel,
    path: str | os.PathLike[str] | None = None,
    *,
    indent: int = 2,
) -> Path:
    """Write *model* to the JSON config file with ``0600`` permissions.

    Secrets (:class:`pydantic.SecretStr`) are written in **cleartext** into the
    ``0600`` file (inside a ``0700`` directory) — the same file the app reads
    back with :func:`load_config`. Writes to *path* or :func:`resolve_config_path`.

    The write is atomic: content is written to a temporary file in the same
    directory, flushed and fsynced, then atomically renamed over the target via
    ``os.replace``.  On failure the temp file is removed and the target is left
    unchanged (or absent if it didn't exist).

    Returns the path written.
    """
    target = Path(path) if path is not None else resolve_config_path()
    # codeql[py/clear-text-storage-sensitive-data] -- intentional per config-standard §3
    data = _reveal(model.model_dump(mode="python"))
    text = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"

    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        parent.chmod(0o700)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix=target.name + ".",
        dir=str(parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fd)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

    with contextlib.suppress(OSError):
        target.chmod(0o600)
    return target


def config_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Return *model_cls*'s JSON Schema, for a deploy UI to render typed inputs.

    Encodes each field's type, whether it is required, its enum values, defaults,
    and nested structure — enough for a deploy UI to render typed, validated
    inputs (number field, checkbox, enum dropdown, masked secret) and reject
    wrong types before deploy. Secret fields (:class:`pydantic.SecretStr`) appear
    as ``{"type": "string", "format": "password", "writeOnly": true}``.

    Commit the emitted schema as ``config/config.schema.json`` and keep it in
    sync with the model in CI.

    Args:
        model_cls: The Pydantic model class to generate a schema for.

    Returns:
        The JSON Schema for *model_cls* as a Python dict.
    """
    return model_cls.model_json_schema()


def config_schema_json(model_cls: type[BaseModel], *, indent: int = 2) -> str:
    """Serialize :func:`config_schema` to a JSON string.

    Args:
        model_cls: The Pydantic model class to generate a schema for.
        indent: Number of spaces per indentation level in the JSON output.

    Returns:
        The JSON Schema as a string with a trailing newline, suitable for
        writing to ``config/config.schema.json``.
    """
    return json.dumps(config_schema(model_cls), indent=indent) + "\n"


__all__ = [
    "CONFIG_FILE_ENV",
    "DEFAULT_CONFIG_PATH",
    "ConfigModel",
    "resolve_config_path",
    "load_config",
    "dump_config",
    "config_schema",
    "config_schema_json",
]
