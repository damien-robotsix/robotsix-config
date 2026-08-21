# robotsix-config

[![CI](https://img.shields.io/github/actions/workflow/status/damien-robotsix/robotsix-config/ci.yml?branch=main&label=CI)](https://github.com/damien-robotsix/robotsix-config/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/damien-robotsix/robotsix-config/docs.yml?branch=main&label=Docs)](https://github.com/damien-robotsix/robotsix-config/actions/workflows/docs.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Typed configuration for the robotsix stack — **one JSON file**, **one pydantic model**,
**one JSON Schema** for the deploy UI.

See the **[full documentation](https://damien-robotsix.github.io/robotsix-config)**.

## Installation

```bash
uv add robotsix-config
```

Requires Python 3.14+.

## CLI

```bash
# Generate or check a config JSON Schema
robotsix-config schema myapp.config:Settings
robotsix-config schema --check myapp.config:Settings
robotsix-config schema --output path/to/schema.json myapp.config:Settings

# Validate config JSON keys against model fields
robotsix-config config --check-keys myapp.config:Settings --config config/config.json
```

Or via ``python -m robotsix_config`` (same behaviour):

```bash
python -m robotsix_config schema myapp.config:Settings
```

## Standards

This repo follows the [robotsix stack standards](https://github.com/damien-robotsix/robotsix-standards).

## Development

```sh
uv sync --extra dev
uv run pytest
```
