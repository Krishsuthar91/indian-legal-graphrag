"""Project settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


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
    QDRANT_TIMEOUT_SECONDS: float = 5.0

    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_FORCE_DETERMINISTIC: bool = False

    HYBRID_WEIGHTS_DENSE: float = 0.40
    HYBRID_WEIGHTS_GRAPH: float = 0.35
    HYBRID_WEIGHTS_HIERARCHY: float = 0.25

    # Ranking weights (Phase 3): used ONLY to order retrieved evidence. They
    # are independent of HYBRID_WEIGHTS_* (which set the reported per-signal
    # scores) so retrieval and confidence scores stay unchanged. Sums to 1.
    RANKING_WEIGHT_DENSE: float = 0.35
    RANKING_WEIGHT_GRAPH: float = 0.25
    RANKING_WEIGHT_HIERARCHY: float = 0.15
    RANKING_WEIGHT_KEYWORD: float = 0.15
    RANKING_WEIGHT_CITATION: float = 0.10

    # LLM / Answer Generation (Module 7)
    # mock | openai | llama | mistral | qwen | gemini | nvidia
    LLM_PROVIDER: str = "mock"
    # e.g. gpt-4o-mini, llama-3.1-8b, mistral-small, Qwen/Qwen2.5-7B-Instruct,
    # meta/llama-3.3-70b-instruct
    LLM_MODEL: str = ""
    LLM_BASE_URL: str = ""      # OpenAI-compatible endpoint for llama/qwen/nvidia serving
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 800
    LLM_TIMEOUT_SECONDS: float = 25.0
    # Transient (5xx / connection / read-timeout) retries per LLM call. The
    # LLM honors the caller's deadline (see OpenAICompatClient.complete), so
    # backoff is truncated to whatever time remains before the deadline.
    LLM_MAX_RETRIES: int = 3

    # Gemini (optional — only used when LLM_PROVIDER=gemini)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"

    # NVIDIA NIM (only used when LLM_PROVIDER=nvidia).
    # Generic LLM_* settings take precedence when set; NVIDIA_* are the
    # provider-specific fallback (per the LLM config priority in docs).
    NVIDIA_API_KEY: str = ""
    NVIDIA_MODEL: str = "meta/llama-3.3-70b-instruct"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Document upload (Module 8 frontend integration)
    DOCUMENT_UPLOAD_MAX_BYTES: int = 20971520  # 20 MB

    # QA / Retrieval (Module 7)
    QA_TOP_K: int = 5
    QA_CONFIDENCE_THRESHOLD: float = 0.45
    QA_PROVENANCE_DIR: str = "data/provenance"
    QA_INDEX_IN_MEMORY: bool = True
    # When True, /query validates retrieval first and, if the evidence is
    # insufficient, returns the grounded guard answer without calling the LLM.
    QA_REQUIRE_SUFFICIENT_EVIDENCE: bool = True
    # Adaptive retrieval (Phase 3): when a caller does not supply top_k, the
    # engine classifies the query intent and picks an evidence budget from the
    # QA_TOP_K_{EASY,MEDIUM,COMPLEX} buckets below.
    QA_ADAPTIVE_TOP_K: bool = True
    QA_TOP_K_EASY: int = 4
    QA_TOP_K_MEDIUM: int = 7
    QA_TOP_K_COMPLEX: int = 12
    # Upper bound for a single /query, /explain, or /provenance request.
    # Must be >= LLM_TIMEOUT_SECONDS so a slow-but-alive LLM still gets its turn.
    QA_REQUEST_TIMEOUT_SECONDS: float = 30.0

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

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / "deploy" / "env" / ".env.development"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Diagnostics: which .env file pydantic was pointed at, and whether it existed.
# These are module-level so any component (e.g. the app startup log) can report
# the exact env-file source without importing the settings instance again.
ENV_FILE_PATH = Path(Settings.model_config["env_file"])
ENV_FILE_LOADED = ENV_FILE_PATH.is_file()
