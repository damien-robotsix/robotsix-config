"""Execute the fenced Python examples in the package's docs.

`docs/robotsix_config/index.md` is the canonical home of the quick-start
example (the README was reduced to a tagline + install + link), and nothing
ran it — so renaming or removing a public symbol like `config_schema_json`
would have left the canonical example silently broken until a reader hit it.

Deliberately no doc-test plugin: the example is one self-contained block, and
`pytest-markdown-docs` / `mktestdocs` would add a dev dependency that also has
to be threaded through this repo's `deptry` DEP002 allowlist. Extracting the
fences here is ~20 lines and keeps the dependency surface unchanged.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

_DOCS = Path(__file__).resolve().parents[2] / "docs" / "robotsix_config" / "index.md"

_FENCE_RE = re.compile(r"^```python\n(.*?)^```", re.DOTALL | re.MULTILINE)


def _python_blocks(markdown: Path) -> list[str]:
    """Return every fenced ``python`` block in *markdown*, in order."""
    return _FENCE_RE.findall(markdown.read_text(encoding="utf-8"))


def test_docs_file_exists() -> None:
    """Guard the guard: a moved docs file must not silently skip the checks."""
    assert _DOCS.is_file(), f"canonical docs page not found at {_DOCS}"


def test_at_least_one_example_is_collected() -> None:
    """A docs page that stops declaring ``python`` fences must not pass vacuously."""
    assert _python_blocks(_DOCS), "no fenced python block found — nothing was tested"


@pytest.fixture(autouse=True)
def _in_tmp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each example in a throwaway cwd.

    The quick-start calls ``dump_config``, which writes ``config/config.json``
    **relative to the cwd** and enforces ``0600``/``0700`` on it. Without this
    the test would create (or repermission) a real ``config/`` in whatever
    directory pytest was invoked from.
    """
    monkeypatch.chdir(tmp_path)


def test_docs_python_examples_execute() -> None:
    """Every fenced example runs against the real API.

    A failure here means the docs and the public API have drifted: the block
    references a symbol that no longer exists, or one whose signature changed.
    """
    blocks = _python_blocks(_DOCS)
    for index, source in enumerate(blocks, start=1):
        name = f"_docs_example_{index}"
        compiled = compile(source, f"{_DOCS.name}#python-block-{index}", "exec")
        # A real module registered in sys.modules, not a bare dict: the
        # example declares a ConfigModel subclass, and pydantic resolves a
        # model's annotations through its __module__. Exec'd into an
        # unregistered namespace it cannot, and model construction fails with
        # PydanticUserError "class not fully defined" — an artefact of the
        # harness rather than any drift in the docs.
        module = types.ModuleType(name)
        sys.modules[name] = module
        try:
            exec(compiled, module.__dict__)  # noqa: S102 — the "code" is our own docs
        finally:
            sys.modules.pop(name, None)
