from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "세이프리스"
    debug: bool = False
    cookie_secure: bool = False

    # auto: Supabase 설정이 있으면 Supabase, 없으면 로컬 SQLite를 사용합니다.
    persistence_backend: str = "auto"
    database_url: str = f"sqlite:///{PROJECT_DIR / 'runtime' / 'safelease.db'}"
    supabase_url: str = ""
    supabase_secret_key: str = ""
    supabase_timeout_seconds: float = 10.0

    processed_dir: Path = PROJECT_DIR / "data" / "processed"
    geojson_dir: Path = PROJECT_DIR / "data" / "geojson"
    project_dir: Path = PROJECT_DIR

    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_secret_key.strip())


settings = Settings()
