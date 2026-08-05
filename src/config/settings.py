"""Project settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment / .env file."""

    APP_NAME: str = "explaintool"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_LOG_LEVEL: str = "INFO"

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    REDIS_URL: str = "redis://localhost:6379/0"

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_IN_MEMORY: bool = False

    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_FORCE_DETERMINISTIC: bool = False

    HYBRID_WEIGHTS_DENSE: float = 0.40
    HYBRID_WEIGHTS_GRAPH: float = 0.35
    HYBRID_WEIGHTS_HIERARCHY: float = 0.25

    # LLM / Answer Generation (Module 7)
    LLM_PROVIDER: str = "mock"  # mock | openai | llama | mistral | qwen
    LLM_MODEL: str = ""         # e.g. gpt-4o-mini, llama-3.1-8b, mistral-small, Qwen/Qwen2.5-7B-Instruct
    LLM_BASE_URL: str = ""      # OpenAI-compatible endpoint for llama/qwen local serving
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 800
    LLM_TIMEOUT_SECONDS: float = 60.0

    # QA / Retrieval (Module 7)
    QA_TOP_K: int = 5
    QA_CONFIDENCE_THRESHOLD: float = 0.45
    QA_PROVENANCE_DIR: str = "data/provenance"
    QA_INDEX_IN_MEMORY: bool = True

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Security middleware (Module 9)
    API_KEY_AUTH_ENABLED: bool = False
    API_KEY: str = ""
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_PER_MINUTE: int = 120
    REQUEST_MAX_BODY_BYTES: int = 1048576

    # Logging rotation (Module 9)
    LOG_ROTATION_ENABLED: bool = False
    LOG_MAX_BYTES: int = 52428800
    LOG_BACKUP_COUNT: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
