"""Standard config-file location for the robotsix stack.

One environment variable names the YAML config file across every robotsix
service, so an operator learns the convention once.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Environment variable naming the YAML config file. One name for every service.
CONFIG_FILE_ENV = "ROBOTSIX_CONFIG_FILE"

#: Default config path when :data:`CONFIG_FILE_ENV` is unset.
DEFAULT_CONFIG_PATH = Path("config/config.yaml")


def resolve_config_path() -> Path:
    """Return the config-file path from :data:`CONFIG_FILE_ENV` or the default.

    The path is *not* required to exist — a missing file simply means the
    config resolves from defaults (and any environment overlay) alone.
    """
    raw = os.environ.get(CONFIG_FILE_ENV)
    return Path(raw) if raw else DEFAULT_CONFIG_PATH
