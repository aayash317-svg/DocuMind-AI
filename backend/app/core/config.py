from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DocuMind AI Application Settings."""
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Ollama settings
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:1.5b"

    # Embeddings & Vector Store
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    QDRANT_PATH: str = "./data/qdrant"
    QDRANT_COLLECTION: str = "documind_chunks"

    # Ingestion settings
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_MB: int = 15

    # Retrieval and Agent settings
    RETRIEVAL_TOP_K: int = 10
    RERANK_TOP_K: int = 5
    RRF_K: int = 60
    MAX_AGENT_STEPS: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def setup_directories(self) -> None:
        """Ensure necessary data directories exist."""
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.QDRANT_PATH).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.setup_directories()

