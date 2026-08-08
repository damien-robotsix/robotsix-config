Add the missing `[tool.uv.sources]` git pin for `robotsix-modules` (not on PyPI) and regenerate `uv.lock` — `uv sync` failed to resolve the dev extra in CI once the workflow parsed again.
