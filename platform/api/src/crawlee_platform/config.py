"""Application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration."""

    model_config = SettingsConfigDict(env_prefix='PLATFORM_', extra='ignore')

    database_url: str = 'sqlite+aiosqlite:///./platform.db'
    api_key: str = 'dev-api-key'

    debug_run_timeout_sec: int = 300
    prod_run_timeout_sec: int = 86400
    debug_max_pip_packages: int = 20

    openai_api_key: str | None = None
    openai_base_url: str = 'https://api.openai.com/v1'
    openai_model: str = 'gpt-4o-mini'

    log_retention_days: int = 30
    metrics_retention_days: int = 90
    worker_heartbeat_stale_sec: int = 120

    cors_origins: str = (
        'http://localhost:3333,http://127.0.0.1:3333,'
        'http://localhost:5173,http://127.0.0.1:5173'
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(',') if o.strip()]
