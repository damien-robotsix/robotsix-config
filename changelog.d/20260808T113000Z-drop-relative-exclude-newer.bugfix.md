Removed `exclude-newer = "7d"` from `[tool.uv]`. A relative cutoff is resolved to an absolute timestamp on every invocation, so the window slid between the run that wrote `uv.lock` and any run that verified it — uv then re-resolved and `uv sync --locked` failed, taking out all 12 CI jobs immediately after the 0.2.0 release. `uv.lock` itself needed no change.

Also registered `changelog.d/**/*` as a glob in `modules.yaml` instead of an individual fragment filename — towncrier deletes every fragment at release time, so a named path there fails module registration on the next release.
