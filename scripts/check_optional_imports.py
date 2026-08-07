r"""Check that optional dev-dependency imports in test files are guarded.

Reads ``pyproject.toml`` to discover the packages listed under
``[project.optional-dependencies].dev``, then scans every ``.py`` file
under ``tests/`` for module-level imports of those packages.  An import
is considered *guarded* when it is preceded by a
``pytest.importorskip("<module>")`` call or is wrapped inside a
``try: … except ImportError: …`` block.  Unguarded imports cause a
non-zero exit and a human-readable report — the CI or pre-commit hook
can then block the change.

Usage::

    python scripts/check_optional_imports.py
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
TESTS_DIR = REPO_ROOT / "tests"

# Optional dev-dependency package names whose module-level imports are
# *always* safe because the package is required to run the test suite at
# all (e.g. ``pytest`` itself).  Guarding ``import pytest`` with
# ``pytest.importorskip("pytest")`` would be circular.
ALWAYS_SAFE: frozenset[str] = frozenset({"pytest"})


class Violation(NamedTuple):
    """A single unguarded optional-dev-dep import in a test file."""

    file: Path
    lineno: int
    module: str


def _parse_optional_dev_deps(pyproject: Path) -> frozenset[str]:
    """Return the set of optional dev-dependency package names from *pyproject*.

    Strips PEP 508 version specifiers and extras brackets so that
    ``"hypothesis>=6"`` → ``"hypothesis"`` and
    ``"mkdocstrings[python]>=0.25"`` → ``"mkdocstrings"``.
    """
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)

    raw: list[str] = (
        data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    )
    names: set[str] = set()
    for spec in raw:
        # Strip extras: "mkdocstrings[python]>=0.25" → "mkdocstrings>=0.25"
        bracket = spec.find("[")
        if bracket != -1:
            close = spec.find("]", bracket)
            spec = spec[:bracket] + spec[close + 1 :] if close != -1 else spec[:bracket]
        # Strip version specifiers: "mkdocstrings>=0.25" → "mkdocstrings"
        for sep in ("~=", "!=", ">=", "<=", "==", ">", "<"):
            idx = spec.find(sep)
            if idx != -1:
                spec = spec[:idx]
                break
        name = spec.strip()
        if name:
            names.add(name)
    return frozenset(names)


def _top_level_module(import_name: str) -> str:
    """Return the top-level package name from a dotted import.

    ``"hypothesis.strategies"`` → ``"hypothesis"``,
    ``"hypothesis"`` → ``"hypothesis"``.
    """
    return import_name.partition(".")[0]


def _preceded_by_importorskip(body: list[ast.stmt], module: str) -> bool:
    """Check whether any statement in *body* is an importorskip for *module*."""
    for stmt in body:
        if not isinstance(stmt, ast.Expr):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        # Match pytest.importorskip("module") or importorskip("module")
        match func:
            case ast.Attribute(value=ast.Name(id="pytest"), attr="importorskip"):
                pass
            case ast.Name(id="importorskip"):
                pass
            case _:
                continue
        # Check the first positional argument matches the module name
        if (
            stmt.value.args
            and isinstance(stmt.value.args[0], ast.Constant)
            and stmt.value.args[0].value == module
        ):
            return True
    return False


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    """Return ``True`` when *handler* catches ``ImportError``."""
    if handler.type is None:
        return False  # bare except — does not count as an import guard
    if isinstance(handler.type, ast.Name) and handler.type.id == "ImportError":
        return True
    if isinstance(handler.type, ast.Tuple):
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name) and elt.id == "ImportError":
                return True
    return False


def _inside_try_import_error(body: list[ast.stmt]) -> bool:
    """Check whether any ``Try`` in *body* has an ``ImportError`` handler."""
    for stmt in body:
        if isinstance(stmt, ast.Try):
            for handler in stmt.handlers:
                if _handler_catches_import_error(handler):
                    return True
    return False


def _collect_module_imports(
    body: list[ast.stmt],
    opt_deps: frozenset[str],
) -> list[tuple[int, str, bool]]:
    """Return ``(lineno, module, inside_try)`` for every optional-dep import.

    *inside_try* is ``True`` when the import is nested inside a ``try:`` block
    (regardless of whether the handler catches ``ImportError``).
    """
    results: list[tuple[int, str, bool]] = []

    def _walk(stmts: list[ast.stmt], inside_try: bool) -> None:
        for stmt in stmts:
            module: str | None = None
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    top = _top_level_module(alias.name)
                    if top in opt_deps and top not in ALWAYS_SAFE:
                        module = top
                        break
            elif isinstance(stmt, ast.ImportFrom):
                if stmt.module is not None:
                    top = _top_level_module(stmt.module)
                    if top in opt_deps and top not in ALWAYS_SAFE:
                        module = top
            elif isinstance(stmt, ast.Try):
                # Recurse into the try body so we can detect imports that
                # are wrapped in a try/except that does *not* catch
                # ImportError.
                _walk(stmt.body, inside_try=True)
                continue
            elif isinstance(
                stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                # Skip imports inside functions / classes — those are
                # executed at test time, not during collection.
                continue

            if module is not None:
                results.append((stmt.lineno, module, inside_try))

    _walk(body, inside_try=False)
    return results


def _check_file(file_path: Path, opt_deps: frozenset[str]) -> list[Violation]:
    """Return unguarded-import violations found in *file_path*."""
    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []  # Non-parseable file — let the test suite report it.

    violations: list[Violation] = []
    for lineno, module, inside_try in _collect_module_imports(tree.body, opt_deps):
        if _preceded_by_importorskip(tree.body, module):
            continue
        if inside_try and _inside_try_import_error(tree.body):
            continue

        violations.append(Violation(file_path, lineno, module))

    return violations


def main(argv: list[str] | None = None) -> None:
    """Run the optional-import guard check.

    Returns exit code 0 when every import is properly guarded.
    """
    if not PYPROJECT_PATH.is_file():
        print(f"error: {PYPROJECT_PATH} not found", file=sys.stderr)
        sys.exit(1)

    opt_deps = _parse_optional_dev_deps(PYPROJECT_PATH)
    if not opt_deps:
        print("No optional dev dependencies found — nothing to check.")
        return

    all_violations: list[Violation] = []
    for py_file in sorted(TESTS_DIR.rglob("*.py")):
        all_violations.extend(_check_file(py_file, opt_deps))

    if not all_violations:
        print("All optional-dev-dependency imports in test files are guarded.")
        return

    print(f"Found {len(all_violations)} unguarded optional-dev-dependency import(s):\n")
    for v in all_violations:
        rel = v.file.relative_to(REPO_ROOT)
        print(
            f"  {rel}:{v.lineno} — '{v.module}' imported without "
            f"pytest.importorskip('{v.module}') guard"
        )

    print(
        "\nGuard each import with:\n"
        '    pytest.importorskip("module")\n'
        "    import module\n"
        "\nor wrap it in a try/except ImportError block."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
