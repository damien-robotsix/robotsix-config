"""Config models shared by the ``robotsix_config.history`` test modules."""

from __future__ import annotations

from pydantic import BaseModel, SecretStr


class Langfuse(BaseModel):
    host: str = ""
    public_key: str = ""
    secret_key: SecretStr = SecretStr("")


class Cfg(BaseModel):
    name: str = ""
    retries: int = 3
    langfuse: Langfuse = Langfuse()


class MapCfg(BaseModel):
    """A model whose secrets sit behind segments the model cannot name.

    ``projects`` keys and ``replicas`` indices are data, not schema, so a
    secret under them has no fixed path. This is the canonical fleet shape —
    ``langfuse.projects.<project-name>.secret_key``.
    """

    name: str = ""
    projects: dict[str, Langfuse] = {}
    replicas: list[Langfuse] = []
    tokens: dict[str, SecretStr] = {}


class ListSecretsCfg(BaseModel):
    """A model with a bare ``list[SecretStr]`` — the list *is* the secret."""

    name: str = ""
    secrets: list[SecretStr] = []
    names: list[str] = []
