"""Service configuration. The only module that reads the process environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised at startup when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated runtime configuration for the payouts service."""

    database_url: str
    webhook_secret: str
    service_token: str
    encryption_key: str
    signature_tolerance_seconds: int = 300


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE file. Values already in the environment take precedence."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def _required(values: dict[str, str], key: str, min_length: int = 32) -> str:
    value = values.get(key, "")
    if len(value) < min_length:
        raise ConfigError(f"{key} must be set to at least {min_length} characters.")
    return value


def load_config(env_file: Path = Path(".env")) -> Config:
    """Build configuration from the environment, falling back to a local .env file."""
    values = {**_load_env_file(env_file), **os.environ}
    return Config(
        database_url=values.get("PAYOUTS_DATABASE_URL", "sqlite:///.local/payouts.sqlite"),
        webhook_secret=_required(values, "PAYOUTS_WEBHOOK_SECRET"),
        service_token=_required(values, "PAYOUTS_SERVICE_TOKEN"),
        encryption_key=_required(values, "PAYOUTS_ENCRYPTION_KEY", min_length=44),
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the process-wide configuration, validated once."""
    return load_config()
