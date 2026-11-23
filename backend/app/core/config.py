from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMIND_", env_file=BACKEND_DIR / ".env", extra="ignore"
    )

    data_dir: Path = Path("data")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    max_pdf_pages: int = Field(default=500, ge=1, le=5000)
    chunk_size: int = Field(default=800, ge=100, le=4000)
    chunk_overlap: int = Field(default=120, ge=0)
    embedding_batch_size: int = Field(default=16, ge=1, le=128)
    search_top_k: int = Field(default=5, ge=1, le=30)
    offline: bool = False
    model_cache_dir: Path | None = None
    llm_model: str = "google/flan-t5-base"
    llm_max_new_tokens: int = Field(default=48, ge=4, le=128)
    llm_timeout_seconds: float = Field(default=90, gt=0, le=600)
    llm_cpu_threads: int = Field(default=4, ge=1, le=8)
    chat_min_similarity: float = Field(default=0.30, ge=0, le=1)

    @model_validator(mode="after")
    def validate_overlap(self) -> Self:
        if self.chunk_overlap >= self.chunk_size // 2:
            raise ValueError("chunk_overlap must be less than half of chunk_size")
        return self

    @property
    def storage_dir(self) -> Path:
        return BACKEND_DIR / self.data_dir

    @property
    def database_path(self) -> Path:
        return self.storage_dir / "documind.sqlite3"
