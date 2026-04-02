"""Application settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import JsonConfigSettingsSource


def _platform_deploy_json_path() -> Path | None:
    """`platform/config/platform.deploy.json` (next to `platform/api`)."""
    here = Path(__file__).resolve()
    platform_root = here.parents[3]
    candidate = platform_root / 'config' / 'platform.deploy.json'
    return candidate if candidate.is_file() else None


class Settings(BaseSettings):
    """Environment-driven configuration; JSON file overrides defaults (env overrides JSON)."""

    model_config = SettingsConfigDict(env_prefix='PLATFORM_', extra='ignore')

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Merge order (later overrides earlier): init < env < JSON file < Docker secrets."""
        path = _platform_deploy_json_path()
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        if path is not None:
            sources.append(JsonConfigSettingsSource(settings_cls, json_file=path))
        sources.append(file_secret_settings)
        return tuple(sources)

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

    enable_smart_task_wizard: bool = True

    # --- Docker image push (Aliyun ACR) + optional SSH deploy on target host ---
    # Defaults here; override via platform/config/platform.deploy.json (recommended for these knobs).
    # Env PLATFORM_* still overrides JSON (tests set PLATFORM_DOCKER_DEPLOY_ENABLED=false).
    # Password: MYSELF_ACR_PASSWORD or PLATFORM_ACR_PASSWORD (never commit).
    docker_deploy_enabled: bool = False
    acr_registry: str = 'registry.cn-hangzhou.aliyuncs.com'
    acr_namespace: str = 'goose-spider'
    acr_repository: str = 'goose-spider'
    acr_username: str = 'long1048799454@163.com'
    deploy_ssh_host: str = '1.2.3.4'
    deploy_ssh_user: str = 'root'
    deploy_ssh_port: int = 22
    deploy_ssh_key_path: str | None = None
    deploy_container_name: str = 'goose-spider-runtime'
    deploy_skip_ssh: bool = False
    docker_build_timeout_sec: int = 600
    docker_push_timeout_sec: int = 600
    deploy_ssh_timeout_sec: int = 300

    @model_validator(mode='after')
    def _expand_deploy_ssh_key_path(self) -> Settings:
        if self.deploy_ssh_key_path:
            expanded = str(Path(self.deploy_ssh_key_path).expanduser())
            object.__setattr__(self, 'deploy_ssh_key_path', expanded)
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(',') if o.strip()]
