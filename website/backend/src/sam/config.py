import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SAM (Software Asset Management) Backend"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://sam_user:sam_password@localhost:5432/sam_db"
    )

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sam_secret_jwt_key_enterprise_default_key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR.parent.parent / "data")))

    # SAM logic
    ZOMBIE_THRESHOLD_DAYS: int = 60
    AUTO_SEED: bool = True

    # OpenAI / LLM
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.giga.chat/v1"
    OPENAI_MODEL: str = "GigaChat-3-Ultra"
    OPENAI_EMBEDDING_MODEL: str = "EmbeddingsGigaR"
    EMBEDDING_DIM: int = 1536

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=(
            str(Path(__file__).resolve().parent.parent.parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
        ),
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
