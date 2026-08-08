#!/usr/bin/env python3
r"""Check that the built wheel includes the ``py.typed`` marker file.

Builds the wheel with the PEP 517 ``build`` frontend, then asserts
that ``robotsix_config/py.typed`` is present in the zipfile namelist.
Exits non-zero if the marker is missing — this guards against a
packaging regression that would silently strip type information from
downstream consumers.

Usage::

    python scripts/check_py_typed.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Build the wheel and verify ``py.typed`` is included."""
    repo_root = Path(__file__).resolve().parent.parent

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(  # noqa: S603
            [  # noqa: S607
                "uvx",
                "--from",
                "build",
                "pyproject-build",
                "--wheel",
                "--outdir",
                tmpdir,
            ],
            cwd=repo_root,
            check=True,
        )
        wheels = list(Path(tmpdir).glob("*.whl"))
        if not wheels:
            print(
                "No wheel produced by build — check pyproject.toml",
                file=sys.stderr,
            )
            sys.exit(1)

        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as zf:
            namelist = zf.namelist()

        expected = "robotsix_config/py.typed"
        if expected not in namelist:
            print(
                f"py.typed marker ({expected!r}) not found in wheel {wheel.name}",
                file=sys.stderr,
            )
            print("Wheel contents:", file=sys.stderr)
            for name in sorted(namelist):
                print(f"  {name}", file=sys.stderr)
            sys.exit(1)

        print(f"py.typed marker confirmed in wheel {wheel.name}")


if __name__ == "__main__":
    main()
