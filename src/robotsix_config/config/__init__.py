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
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr, ValidationError

from .._errors import InvalidConfigError

logger = logging.getLogger(__name__)


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
    """Read and parse a JSON config file.

    Returns an empty dict when *path* does not exist (so the caller
    can fall back to model defaults). Raises :class:`InvalidConfigError`
    on malformed JSON, unreadable files, or a non-dict top-level value.
    """
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


def _strip_unknown_keys(
    data: dict[str, Any],
    model_cls: type[BaseModel],
) -> dict[str, Any]:
    """Return a copy of *data* with keys not declared on *model_cls* removed.

    Calls itself recursively for nested dict values whose model type is
    known from the JSON Schema ``$defs``.  Each removed key produces a
    ``logging.WARNING`` record naming the full dotted path.

    This is the self-healing mechanism: a persisted ``config.json`` that
    carries a key the current model no longer declares (e.g. a removed
    feature's config block) is silently cleaned before validation, so the
    service does not crash-loop at startup.
    """
    schema = model_cls.model_json_schema()
    properties = schema.get("properties") or {}
    defs = schema.get("$defs", {})

    def _walk(
        node: dict[str, Any],
        known_props: dict[str, Any],
        known_defs: dict[str, Any],
        prefix: tuple[str, ...],
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in node.items():
            path = (*prefix, key)
            if key not in known_props:
                dotted = ".".join(path)
                logger.warning(
                    "Stripping unknown config key %r — the field no longer "
                    "exists on the model %s",
                    dotted,
                    model_cls.__name__,
                )
                continue
            prop_schema = known_props.get(key, {})
            ref = prop_schema.get("$ref")
            if isinstance(value, dict) and ref is not None:
                # Only recurse into submodels ($ref) to strip their unknown
                # keys.  Plain dict-typed fields (e.g. dict[str, Any]) accept
                # arbitrary keys and must be preserved as-is.
                ref_name = ref.rsplit("/", 1)[-1]
                sub_schema = known_defs.get(ref_name, {})
                sub_props = sub_schema.get("properties") or {}
                out[key] = _walk(value, sub_props, known_defs, path)
            else:
                out[key] = value
        return out

    return _walk(data, properties, defs, ())


def _run_legacy_migration(
    data: dict[str, Any], model_cls: type[BaseModel]
) -> dict[str, Any]:
    """Apply *model_cls*'s optional pre-strip legacy migration to *data*.

    Consumers declare ``migrate_legacy_config(cls, data) -> dict`` to move a
    removed key's value somewhere the current model still accepts.  It runs
    before :func:`_strip_unknown_keys` — that ordering is the whole point, see
    :func:`load_config`.

    Best-effort by design: a raising or non-conforming hook must not stop a
    config from loading, since the alternative is a component that cannot
    start.  The failure is logged at ``WARNING`` and the original data is used.
    """
    migrate = getattr(model_cls, "migrate_legacy_config", None)
    if not callable(migrate):
        return data
    try:
        migrated = migrate(data)
    except Exception:
        logger.warning(
            "%s.migrate_legacy_config raised — loading the unmigrated config",
            model_cls.__name__,
            exc_info=True,
        )
        return data
    if not isinstance(migrated, dict):
        logger.warning(
            "%s.migrate_legacy_config returned %s, expected dict — "
            "loading the unmigrated config",
            model_cls.__name__,
            type(migrated).__name__,
        )
        return data
    return migrated


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

    **Self-healing.** If the persisted file contains keys that the current model
    does not declare (e.g. a removed feature's config block), those keys are
    silently stripped before validation.  Each stripped key produces a
    ``WARNING`` log record.  The model itself is never relaxed — the loader
    removes the offending keys rather than expecting the model to accept them.

    **Legacy migration.** A model may declare a
    ``migrate_legacy_config(data) -> dict`` classmethod; when present it is
    called on the raw file contents **before** stripping, so a consumer can
    move a removed key's *value* to its canonical home instead of losing it.
    Without this hook the ordering defeats consumer migrations written as
    pydantic ``@model_validator(mode="before")``: those run inside
    ``model_validate``, which the loader reaches only after the unknown key has
    already been stripped — so the value is gone before the migration can read
    it, silently.  Migrations must be idempotent: the loader persists the
    cleaned result, so the hook sees already-migrated data on the next load.

    After stripping, the cleaned config is persisted through the versioned/
    append-only write path (see :func:`robotsix_config.history.apply_update`) —
    a new version entry is appended whose ``changed_keys`` lists the stripped
    legacy keys, so the heal is auditable and rollback-able.  If no unknown keys
    were found, no write occurs.
    """
    target = Path(path) if path is not None else resolve_config_path()
    data = _read_json(target)
    if data:
        data = _run_legacy_migration(data, model_cls)
        cleaned = _strip_unknown_keys(data, model_cls)
        if cleaned != data:
            # Lazy import to avoid circular dependency: history.py imports
            # from this module, so we import it only at call time.
            from ..history import (
                _write_raw,
                compute_changed_keys,
                read_versions,
                record_version,
            )

            # Record the pre-heal state as an "initial" entry so the stale
            # version is visible in history and rollback-able.
            if not read_versions(target, include_data=False):
                record_version(data, ["initial"], model_cls, target)

            changed = compute_changed_keys(data, cleaned, model_cls)
            _write_raw(target, cleaned)
            record_version(cleaned, changed, model_cls, target)
            data = cleaned
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
        return [_reveal(v) for v in obj]
    return obj


def _atomic_replace(
    src: str,
    dst: Path,
    *,
    attempts: int = 5,
    delay: float = 0.05,
) -> None:
    """Atomically rename *src* over *dst*, retrying on PermissionError.

    On Windows, ``os.replace`` can fail with ``PermissionError`` when the
    target file is held open by another process (e.g. antivirus scanner,
    backup agent, or a leaked handle).  This helper retries with a short
    back-off, mirroring the pattern used by filelock, python-dotenv, and
    tomlkit.
    """
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay)


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

    .. note::

        The ``0600`` permission guarantee is **POSIX-only**.  On Windows,
        ``os.chmod`` only toggles the read-only attribute bit — the file will
        not be restricted to the owner in the POSIX sense.  The ``chmod``
        calls are best-effort and will not raise on platforms where the mode
        cannot be fully enforced.

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
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass  # best-effort: 0600 is a POSIX-only guarantee
        _atomic_replace(tmp_path, target)
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
    "config_schema",
    "config_schema_json",
    "dump_config",
    "load_config",
    "resolve_config_path",
]
