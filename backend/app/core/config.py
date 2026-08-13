from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.db_paths import MERGED_DB_PATH, PROJECT_ROOT


class Settings(BaseSettings):
    app_env: str = "local"
    cors_origins_raw: str = Field(
        default="http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )
    dataset_dir: Path = PROJECT_ROOT / "backend" / "app" / "dataset" / "service_data"
    merged_db_path: Path = MERGED_DB_PATH
    tracking_db_path: Path = MERGED_DB_PATH
    allocation_db_path: Path = MERGED_DB_PATH

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()
