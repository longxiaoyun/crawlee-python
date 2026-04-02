"""Pydantic API schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ''


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    settings: dict[str, Any] | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    production_version_id: uuid.UUID | None
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}

    @field_validator('settings', mode='before')
    @classmethod
    def _settings_dict(cls, v: Any) -> dict[str, Any]:
        return v if isinstance(v, dict) else {}


class TaskListRowOut(TaskOut):
    """Task row for console list (build/run aggregates + last run summary)."""

    total_builds: int = 0
    total_runs: int = 0
    default_build_display: str = ''
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_run_duration_sec: float | None = None


class TaskVersionCreate(BaseModel):
    source_code: str
    requirements_txt: str = ''
    meta: dict[str, Any] = Field(default_factory=dict)
    created_by: str = 'user'


class TaskVersionOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    version_number: int
    source_code: str
    requirements_txt: str
    meta: dict[str, Any]
    created_at: datetime
    created_by: str

    model_config = {'from_attributes': True}


class PromoteBody(BaseModel):
    version_id: uuid.UUID


class DeployRequest(BaseModel):
    version_id: uuid.UUID | None = None
    environment: str = Field(default='production', pattern='^(production|staging)$')


class DeployOut(BaseModel):
    task_id: uuid.UUID
    version_id: uuid.UUID
    environment: str
    runtime: str
    entrypoint: str
    deployed_at: datetime
    status: str
    image_ref: str | None = None
    remote_host: str | None = None
    remote_ok: bool | None = None
    detail: str | None = None


class DeployInfoOut(BaseModel):
    """Non-secret deploy targets for the console (from Settings + platform.deploy.json)."""

    docker_deploy_enabled: bool
    acr_registry: str
    acr_namespace: str
    acr_repository: str
    image_repository: str
    deploy_ssh_host: str
    deploy_ssh_user: str
    deploy_ssh_port: int
    deploy_container_name: str
    deploy_skip_ssh: bool


class RunCreate(BaseModel):
    version_id: uuid.UUID
    kind: str = Field(pattern='^(debug|production)$')


class RunOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    version_id: uuid.UUID
    kind: str
    status: str
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {'from_attributes': True}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
    correlation_id: str
    model_id: str | None


class OverviewOut(BaseModel):
    worker_heartbeat_at: datetime | None
    worker_stale: bool
    recent_success_ratio: float
    queued_runs: int
    running_runs: int


class WizardSessionCreateOut(BaseModel):
    session_id: uuid.UUID


class WizardSessionMetaOut(BaseModel):
    """Single wizard session metadata (for UI: readonly vs active)."""

    session_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime


class WizardSessionListItem(BaseModel):
    """Row for GET /api/ai/task-wizard/sessions history list."""

    session_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    preview: str = ''
    message_count: int = 0


class WizardMessageBody(BaseModel):
    message: str = Field(min_length=1)


class WizardMessageOut(BaseModel):
    reply: str
    draft: dict[str, Any] | None = None


class WizardFinalizeBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ''
    source_code: str = Field(min_length=1)
    requirements_txt: str = ''
    settings: dict[str, Any] = Field(default_factory=dict)


class WizardFinalizeOut(BaseModel):
    task_id: uuid.UUID
    version_id: uuid.UUID
