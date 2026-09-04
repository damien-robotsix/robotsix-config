r"""Check that a committed JSON Schema file matches a Pydantic model.

Regenerates the JSON Schema from the model and compares it against the
file on disk.  If the file is missing or its content differs, the script
writes the fresh schema and exits non-zero with a unified diff — the
caller (human or CI) can then commit the updated file.

Usage::

    python scripts/check_schema_freshness.py \\
        --model myapp.config.Settings \\
        --output config/config.schema.json

This is a thin wrapper over :func:`robotsix_config.cli._import_model` and
:func:`robotsix_config.cli.schema_check`, which are the single source of
truth for importing a model and checking schema freshness.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from robotsix_config.cli import _import_model, schema_check


def _die(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    """Regenerate the JSON Schema from a model and check it against disk."""
    parser = argparse.ArgumentParser(
        description="Check that a committed JSON Schema file is fresh."
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Dotted Python path to a Pydantic model class "
        "(e.g. myapp.config.Settings).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Filesystem path to write the JSON Schema to "
        "(e.g. config/config.schema.json).",
    )
    args = parser.parse_args(argv)

    try:
        model_cls = _import_model(args.model)
    except (ValueError, ImportError, AttributeError, TypeError) as exc:
        _die(str(exc))

    # CI expects the fresh schema to be written on drift (so it can be
    # committed) in addition to the non-zero exit.
    schema_check(model_cls, Path(args.output), write_on_drift=True)


if __name__ == "__main__":
    main()
