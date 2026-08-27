`load_config` now calls an optional `migrate_legacy_config(data) -> dict` classmethod on the model
**before** stripping unknown keys, so a consumer can carry a removed key's value to its canonical home
instead of losing it. Without this, a migration written as a pydantic `@model_validator(mode="before")`
never sees the value: the loader strips the key first and the validator runs afterwards.
