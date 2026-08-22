"""Enables ``python -m robotsix_config`` — forwards the exit code."""

from __future__ import annotations

import sys

from .cli import main

sys.exit(main())
