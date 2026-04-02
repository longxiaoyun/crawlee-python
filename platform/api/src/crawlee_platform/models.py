"""ORM models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Not a DB FK: avoids ambiguous ORM paths between tasks.id<->task_versions (task_id + production pointer).
    production_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # Console-only JSON: webhooks, visibility notes, etc. (SQLite stores as TEXT)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    versions: Mapped[list['TaskVersion']] = relationship(back_populates='task')
    runs: Mapped[list['Run']] = relationship('Run', back_populates='task')


class TaskVersion(Base):
    __tablename__ = 'task_versions'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('tasks.id'), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    requirements_txt: Mapped[str] = mapped_column(Text, default='')
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String(128), default='system')

    task: Mapped[Task] = relationship(back_populates='versions')


class Run(Base):
    __tablename__ = 'runs'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('tasks.id'), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('task_versions.id'), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # debug | production
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='queued')
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[Task] = relationship('Task', back_populates='runs')
    log_lines: Mapped[list['RunLogLine']] = relationship(
        back_populates='run',
        order_by='RunLogLine.line_no',
    )
    dataset_items: Mapped[list['RunDatasetItem']] = relationship(
        back_populates='run',
        order_by='RunDatasetItem.seq',
        cascade='all, delete-orphan',
    )


class RunLogLine(Base):
    __tablename__ = 'run_log_lines'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('runs.id'), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[Run] = relationship('Run', back_populates='log_lines')


class RunDatasetItem(Base):
    """Crawlee default filesystem dataset items copied into the control-plane DB after each run."""

    __tablename__ = 'run_dataset_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('runs.id', ondelete='CASCADE'), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[Run] = relationship('Run', back_populates='dataset_items')


class TaskWizardSession(Base):
    """Pre-task AI wizard: multi-turn chat before a Task row exists."""

    __tablename__ = 'task_wizard_sessions'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list['TaskWizardMessage']] = relationship(
        back_populates='session',
        order_by='TaskWizardMessage.created_at',
        cascade='all, delete-orphan',
    )


class TaskWizardMessage(Base):
    __tablename__ = 'task_wizard_messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey('task_wizard_sessions.id', ondelete='CASCADE'), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[TaskWizardSession] = relationship(back_populates='messages')


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('tasks.id'), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkerHeartbeat(Base):
    __tablename__ = 'worker_heartbeats'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False, default='default')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
