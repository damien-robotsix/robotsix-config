"""CLI for robotsix-config — generate and check config JSON Schemas.

Usage::

    robotsix-config schema myapp.config:Settings
    robotsix-config schema --check myapp.config:Settings
    robotsix-config config --check-keys myapp.config:Settings --config config.json
"""

from __future__ import annotations

import argparse
import difflib
import importlib
import json
import sys
from pathlib import Path
from typing import NoReturn

from pydantic import BaseModel

from .config import config_schema_json


def _import_model(dotted_path: str) -> type[BaseModel]:
    """Import a Pydantic model class from a ``pkg.module.Cls`` string."""
    module_path, _, class_name = dotted_path.rpartition(".")
    if not module_path:
        raise ValueError(
            f"Expected a dotted path like 'pkg.module.Cls', got {dotted_path!r}"
        )
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ImportError(
            f"Could not import module {module_path!r}: {exc}"
        ) from exc
    try:
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise AttributeError(
            f"Module {module_path!r} has no attribute {class_name!r}"
        ) from exc
    if not isinstance(cls, type) or not issubclass(cls, BaseModel):
        raise TypeError(
            f"{dotted_path!r} is not a pydantic BaseModel subclass "
            f"(got {type(cls).__name__})"
        )
    return cls


def _schema_generate(
    model_cls: type[BaseModel],
    output_path: Path,
) -> None:
    """Write the JSON Schema to *output_path* and print a notice."""
    content = config_schema_json(model_cls)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote schema to '{output_path}'")


def _schema_check(
    model_cls: type[BaseModel],
    output_path: Path,
) -> None:
    """Compare the committed file against freshly generated schema."""
    new_content = config_schema_json(model_cls)
    old_content = (
        output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
    )

    if new_content == old_content:
        print(f"Schema file '{output_path}' is in sync with the model.")
        return

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=str(output_path),
            tofile=str(output_path),
        )
    )

    reason = "missing" if not old_content else "out of sync"
    print(
        f"Schema file '{output_path}' is {reason} with the model."
        "\nRe-run without --check to regenerate, then commit the updated file."
        "\n\nDiff:"
    )
    print(diff)
    sys.exit(1)


def _config_check_keys(
    model_cls: type[BaseModel],
    config_path: Path,
) -> None:
    """Validate the config JSON's key set against the model's fields."""
    if not config_path.is_file():
        print(f"Config file '{config_path}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in '{config_path}': {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(config_data, dict):
        print(
            f"Config in '{config_path}' must be a JSON object.", file=sys.stderr
        )
        sys.exit(1)

    model_fields = set(model_cls.model_fields.keys())
    config_keys = set(config_data.keys())

    missing = model_fields - config_keys
    unknown = config_keys - model_fields

    ok = True
    if missing:
        print(
            f"Config at '{config_path}' is missing keys: "
            f"{_fmt_keys(missing)}",
            file=sys.stderr,
        )
        ok = False
    if unknown:
        print(
            f"Config at '{config_path}' has unknown keys: "
            f"{_fmt_keys(unknown)}",
            file=sys.stderr,
        )
        ok = False

    if ok:
        print(
            f"Config keys in '{config_path}' match the model fields of "
            f"{model_cls.__name__}."
        )
    else:
        sys.exit(1)


def _fmt_keys(keys: set[str]) -> str:
    return ", ".join(sorted(keys))


def _die(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``robotsix-config`` console script."""
    parser = argparse.ArgumentParser(
        prog="robotsix-config",
        description="Generate, check, and validate config JSON Schemas.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- schema ----
    schema_parser = subparsers.add_parser(
        "schema",
        help="Generate or check a config JSON Schema from a Pydantic model.",
        description="Generate a JSON Schema from a pydantic model and write it "
        "to disk, or check that the committed schema matches the model.",
    )
    schema_parser.add_argument(
        "model",
        help="Dotted Python path to a pydantic model class "
        "(e.g. myapp.config.Settings).",
    )
    schema_parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Compare the committed file against a freshly generated schema "
        "(exit 1 on drift).",
    )
    schema_parser.add_argument(
        "--output",
        default="config/config.schema.json",
        help="Path for the JSON Schema file (default: config/config.schema.json).",
    )

    # ---- config ----
    config_parser = subparsers.add_parser(
        "config",
        help="Validate config JSON keys against model fields.",
        description="Check that the config JSON file's top-level keys match "
        "the model's declared fields.",
    )
    config_parser.add_argument(
        "--check-keys",
        required=True,
        dest="check_keys_model",
        help="Dotted Python path to a pydantic model class.",
    )
    config_parser.add_argument(
        "--config",
        required=True,
        dest="config_path",
        help="Path to the config JSON file to validate.",
    )

    args = parser.parse_args(argv)

    try:
        if args.command == "schema":
            try:
                model_cls = _import_model(args.model)
            except (ValueError, ImportError, AttributeError, TypeError) as exc:
                _die(str(exc))

            output_path = Path(args.output)
            if args.check:
                _schema_check(model_cls, output_path)
            else:
                _schema_generate(model_cls, output_path)

        elif args.command == "config":
            try:
                model_cls = _import_model(args.check_keys_model)
            except (ValueError, ImportError, AttributeError, TypeError) as exc:
                _die(str(exc))

            _config_check_keys(model_cls, Path(args.config_path))
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1

    return 0