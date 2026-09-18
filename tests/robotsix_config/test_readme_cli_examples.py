"""Execute the CLI examples documented in README.md.

The README's ``CLI`` section is the canonical quick-start for the
``robotsix-config`` console script — a stale model-path syntax, a renamed
flag, or a broken argument order leaves readers with a first run that
fails.  This module parses every ``robotsix-config`` / ``python -m
robotsix_config`` line inside the README's bash fences and runs it
end-to-end (with the reader-facing placeholder ``myapp.config.Settings``
model substituted for a real, importable test model), so the documented
behaviour cannot drift from the implementation.

Deliberately in-process: the console script and ``python -m`` entry
points both forward to :func:`robotsix_config.cli.main`, and running it
directly is hermetic (no shell, no subprocess, no network).
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from robotsix_config.cli import main
from robotsix_config.config import config_schema_json
from tests.config.scripts._test_cli_models import AppSettings

_README = Path(__file__).resolve().parents[2] / "README.md"

_BASH_FENCE_RE = re.compile(r"^```bash\n(.*?)^```", re.DOTALL | re.MULTILINE)
_CLI_LINE_RE = re.compile(r"^(?:robotsix-config|python -m robotsix_config)\s+(.+)$")
_MODEL_RE = re.compile(r"\bmyapp\.config\.Settings\b")
_TEST_MODEL = "tests.config.scripts._test_cli_models.AppSettings"


def _cli_lines() -> list[str]:
    """Return the argument lists of every documented CLI invocation, in order."""
    lines: list[str] = []
    for fence in _BASH_FENCE_RE.findall(_README.read_text(encoding="utf-8")):
        for line in fence.splitlines():
            match = _CLI_LINE_RE.match(line.strip())
            if match:
                lines.append(match.group(1))
    return lines


@pytest.fixture(autouse=True)
def _in_tmp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each example in a throwaway cwd.

    The examples write schemas and configs **relative to the cwd**
    (``config/config.schema.json``, ``config/config.json``,
    ``path/to/schema.json``), so a temp cwd keeps the run hermetic.
    """
    monkeypatch.chdir(tmp_path)


def test_docs_file_exists() -> None:
    """Guard the guard: a moved README must not silently skip the checks."""
    assert _README.is_file(), f"README not found at {_README}"


def test_at_least_one_example_is_collected() -> None:
    """A README that stops showing CLI examples must not pass vacuously."""
    assert _cli_lines(), "no documented CLI invocation found — nothing was tested"


def test_no_colon_separated_model_paths() -> None:
    """Documented CLI model paths must be dotted (``pkg.module.Cls``).

    The ``module:Class`` form is not supported by
    :func:`robotsix_config.cli._import_model`, which splits on the last
    dot — a colon lands inside the attribute name and the import fails
    with ``Module 'myapp' has no attribute 'config:Settings'``.
    """
    for invocation in _cli_lines():
        for token in shlex.split(invocation):
            assert not re.fullmatch(r"[\w.]+:[\w.]+", token), (
                f"colon-separated model path {token!r} in README CLI "
                f"example: {invocation!r}"
            )


def test_documented_cli_examples_execute() -> None:
    """Every documented CLI invocation runs successfully.

    ``myapp.config.Settings`` is a reader-facing placeholder, so it is
    substituted with a real importable test model; ``--check`` and
    ``--config`` examples get their prerequisite files pre-seeded.
    """
    for invocation in _cli_lines():
        args = shlex.split(_MODEL_RE.sub(_TEST_MODEL, invocation))
        assert args, f"empty CLI invocation in README: {invocation!r}"

        if "--check" in args:
            _seed_schema(args)
        if "--config" in args:
            _seed_config(args)

        exit_code = main(args)
        assert exit_code == 0, f"README CLI example exited {exit_code}: {invocation!r}"


def _seed_schema(args: list[str]) -> None:
    """Pre-write the schema a ``--check`` example compares against."""
    output = _arg_value(args, "--output") or "config/config.schema.json"
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config_schema_json(AppSettings), encoding="utf-8")


def _seed_config(args: list[str]) -> None:
    """Pre-write the config JSON a ``config --check-keys`` example needs."""
    output = _arg_value(args, "--config") or "config/config.json"
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"api_key": "secret", "endpoint": "https://x", "retries": 5}\n',
        encoding="utf-8",
    )


def _arg_value(args: list[str], flag: str) -> str | None:
    """Return the value following *flag* in *args*, if present."""
    if flag in args:
        return args[args.index(flag) + 1]
    return None
