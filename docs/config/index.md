# Config

Load, dump, and describe typed configuration — one pydantic model, one JSON file.

::: robotsix_config.config

## Keeping the schema fresh

Commit the emitted JSON Schema (e.g. `config/config.schema.json`) from the
start, and enforce freshness in CI so the schema never drifts from the model.
The repo ships a script that regenerates the schema from the model class and
fails if the committed file is stale:

```bash
python scripts/check_schema_freshness.py \
    --model myapp.config.Settings \
    --output config/config.schema.json
```

Add a CI job that runs it on every push:

```yaml
check-schema:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - uses: ./.github/actions/setup
    - name: Check schema freshness
      run: >
        PYTHONPATH=src:. python scripts/check_schema_freshness.py
        --model myapp.config.Settings
        --output config/config.schema.json
```

For local development, wire the same script into a `pre-commit` hook or a
`make check-schema` target so you catch drift before pushing.
