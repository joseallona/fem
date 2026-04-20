from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://fem:fem@localhost:5432/fem"
    REDIS_URL: str = "redis://localhost:6379/0"

    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_MODEL_REASONING: str = "deepseek-r1:14b"  # used for axis/reasoning jobs

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-reasoner"          # DeepSeek R1 — for axis reasoning
    DEEPSEEK_MODEL_FAST: str = "deepseek-chat"         # DeepSeek V3 — for summaries/scenarios

    # Per-job-type provider routing (overrides LLM_PROVIDER when set)
    # Format: comma-separated "job_type:provider" pairs
    # e.g. "summary:groq,scenario:groq,axis:deepseek"
    LLM_ROUTING: str = ""

    SECRET_KEY: str = "change-me"
    ENVIRONMENT: str = "development"

    # Path for the independent historical signal archive (SQLite)
    SIGNAL_ARCHIVE_PATH: str = "/data/signal_archive.db"


settings = Settings()


def get_runtime_setting(key: str, default: str) -> str:
    """
    Return the runtime value for a setting key.
    Checks system_settings DB table first; falls back to `default`
    (which should be the corresponding settings.* value).
    Lazy import of SessionLocal avoids circular imports at module load time.
    """
    try:
        from app.core.database import SessionLocal
        from app.models.setting import SystemSetting
        db = SessionLocal()
        try:
            row = db.get(SystemSetting, key)
            if row:
                return row.value
        finally:
            db.close()
    except Exception:
        pass
    return default
