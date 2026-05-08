from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "GlobalCart 360"
    DEBUG: bool = False
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
    
    # Auth Settings
    ADMIN_KEY: str = "admin"
    OTP_SECRET: str = "dev-secret"
    OTP_TTL_SECONDS: int = 600
    OTP_MAX_ATTEMPTS: int = 5
    DEMO_SHOW_OTP: bool = True
    
    # Database Settings
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = "postgres"
    PGDATABASE: str = "postgres"

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore")

settings = Settings()
