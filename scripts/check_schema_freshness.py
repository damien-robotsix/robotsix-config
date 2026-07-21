#!/usr/bin/env python3
r"""Check that a committed JSON Schema file matches a Pydantic model.

Regenerates the JSON Schema from the model and compares it against the
file on disk.  If the file is missing or its content differs, the script
writes the fresh schema and exits non-zero with a unified diff — the
caller (human or CI) can then commit the updated file.

Usage::

    python scripts/check_schema_freshness.py \\
        --model myapp.config.Settings \\
        --output config/config.schema.json
"""

from __future__ import annotations

import argparse
import difflib
import importlib
import json
import sys
from pathlib import Path
from typing import cast

from pydantic import BaseModel


def _import_model(dotted_path: str) -> type[BaseModel]:
    """Import a Pydantic model class from a ``pkg.module.Cls`` string."""
    module_path, _, class_name = dotted_path.rpartition(".")
    if not module_path:
        raise ValueError(
            f"Expected a dotted path like 'pkg.module.Cls', got {dotted_path!r}"
        )
    module = importlib.import_module(module_path)
    try:
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise AttributeError(
            f"Module {module_path!r} has no attribute {class_name!r}"
        ) from exc
    return cast(type[BaseModel], cls)


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

    model_cls = _import_model(args.model)
    schema = model_cls.model_json_schema()
    new_content = json.dumps(schema, indent=2) + "\n"

    output_path = Path(args.output)
    old_content = (
        output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
    )

    if new_content == old_content:
        print(f"Schema file '{output_path}' is fresh.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(new_content, encoding="utf-8")

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

    reason = "missing" if not old_content else "stale"
    print(
        f"Schema file '{output_path}' is {reason} — "
        "regenerated content differs from the committed version.\n"
        "Re-run the script and commit the updated file.\n"
        "\nDiff:"
    )
    print(diff)
    sys.exit(1)


if __name__ == "__main__":
    main()
