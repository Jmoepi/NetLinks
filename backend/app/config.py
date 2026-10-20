"""Application settings loaded from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Confidence below this threshold is treated as low confidence (needs SME confirmation).
LOW_CONFIDENCE = 0.6

# Per-embedding-model calibration for the capability semantic score:
# calibrated = clamp((cosine - floor) / (ceil - floor), 0, 1)
EMBEDDING_CALIBRATION: dict[str, dict[str, float]] = {
    "local-lexicon-v1": {"floor": 0.0, "ceil": 0.9},
    "amazon.titan-embed-text-v2:0": {"floor": 0.2, "ceil": 0.75},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://netlinks:netlinks@db:5432/netlinks"
    test_database_url: str = "postgresql+psycopg://netlinks:netlinks@db:5432/netlinks_test"

    ai_cache_dir: str = "/ai-cache"
    demo_assets_dir: str = "/demo-assets"
    upload_dir: str = "/data/uploads"

    cors_origins: str = "http://localhost:3000"

    bedrock_region: str = "af-south-1"
    bedrock_extraction_model_id: str = ""
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_profile: str = ""

    storage_backend: str = "local"  # local | s3
    s3_bucket: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
