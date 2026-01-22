from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    env: str
    jwt_secret: str
    rate_limit_enabled: bool
    rate_limit_requests: int
    rate_limit_window_seconds: int


def load_settings() -> Settings:
    env = (os.getenv("ENV", "dev") or "dev").strip().lower()

    jwt_secret = (os.getenv("JWT_SECRET", "") or "").strip()
    if env != "dev" and not jwt_secret:
        raise RuntimeError("JWT_SECRET is required when ENV is not 'dev'")

    # In dev, allow missing JWT_SECRET so non-auth pages can still work.
    if env == "dev" and not jwt_secret:
        jwt_secret = ""

    rate_limit_enabled = str(os.getenv("RATE_LIMIT_ENABLED", "1")).strip().lower() not in {"0", "false"}

    try:
        rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
    except ValueError:
        rate_limit_requests = 120

    try:
        rate_limit_window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    except ValueError:
        rate_limit_window_seconds = 60

    return Settings(
        env=env,
        jwt_secret=jwt_secret,
        rate_limit_enabled=rate_limit_enabled,
        rate_limit_requests=rate_limit_requests,
        rate_limit_window_seconds=rate_limit_window_seconds,
    )
