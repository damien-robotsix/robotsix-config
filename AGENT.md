## Type Distribution

Type-aware packages must include a `py.typed` marker per PEP 561 to
enable downstream consumers to type-check imports without `# type:
ignore` suppressions.

## Testing conventions

When adding an optional dev dependency to
`[project.optional-dependencies].dev` in `pyproject.toml`, guard any
module-level import of that dependency in test files with
`pytest.importorskip("<module>")` (or a conditional import) so the
test module remains collectible even when the optional dependency is
not installed. `pytest` imports every test module during collection,
before any test runs, so an unguarded module-level import defers no
failure — it breaks collection outright. Guarding the import defers
the dependency check to test execution time, letting the affected
tests skip cleanly rather than failing the whole run.

For example, an unguarded module-level `import hypothesis` in a test
file caused CI collection to fail with `ModuleNotFoundError` when the
optional dependency was absent.
