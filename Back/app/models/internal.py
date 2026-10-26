"""Private relational support tables; never return these DTOs to public APIs."""
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base, utcnow


class JobRuntime(Base):
    __tablename__ = 'job_runtime'
    job_id = mapped_column(Uuid(as_uuid=True), ForeignKey('generation_jobs.id'), primary_key=True)
    input = mapped_column(JSONB, nullable=False)
    lease_token = mapped_column(Uuid(as_uuid=True), nullable=True)
    lease_until = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    heartbeat_at = mapped_column(DateTime(timezone=True), nullable=True)
    provider_state = mapped_column(JSONB, nullable=False, default=dict)
    result_state = mapped_column(JSONB, nullable=False, default=dict)


class FileStorage(Base):
    __tablename__ = 'file_storage'
    file_id = mapped_column(Uuid(as_uuid=True), ForeignKey('files.id'), primary_key=True)
    bucket = mapped_column(String(255), nullable=False)
    object_name = mapped_column(String(1024), nullable=False)
    width = mapped_column(Integer, nullable=True)
    height = mapped_column(Integer, nullable=True)
    duration_seconds = mapped_column(Numeric(12, 3), nullable=True)
    checksum = mapped_column(String(64), nullable=True)
    __table_args__ = (UniqueConstraint('bucket', 'object_name', name='uq_file_storage_object'),)


class ImportState(Base):
    __tablename__ = 'import_state'
    import_id = mapped_column(Uuid(as_uuid=True), ForeignKey('import_batches.id'), primary_key=True)
    context = mapped_column(JSONB, nullable=False, default=dict)
    rows = mapped_column(JSONB, nullable=False, default=list)
    commit_options = mapped_column(JSONB, nullable=False, default=dict)


class IdempotencyRecord(Base):
    __tablename__ = 'idempotency_records'
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=False)
    method = mapped_column(String(10), nullable=False)
    path = mapped_column(String(2048), nullable=False)
    key = mapped_column(Uuid(as_uuid=True), nullable=False)
    fingerprint = mapped_column(String(64), nullable=False)
    status = mapped_column(Integer, nullable=False)
    response = mapped_column(JSONB, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    __table_args__ = (UniqueConstraint('user_id', 'method', 'path', 'key', name='uq_idempotency_scope'),)


class AuthorizationState(Base):
    __tablename__ = 'authorization_states'
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    account_id = mapped_column(Uuid(as_uuid=True), ForeignKey('platform_accounts.id'), nullable=False)
    user_id = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=False)
    login_session_id = mapped_column(Uuid(as_uuid=True), ForeignKey('login_sessions.id'), nullable=False)
    state_hash = mapped_column(String(64), nullable=False, unique=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    used_at = mapped_column(DateTime(timezone=True), nullable=True)


class ClickEvent(Base):
    __tablename__ = 'click_events'
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    link_id = mapped_column(Uuid(as_uuid=True), ForeignKey('promotion_links.id'), nullable=False, index=True)
    clicked_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    counted = mapped_column(Boolean, nullable=False, default=True)
    request_fingerprint = mapped_column(String(64), nullable=True)
    ip_hash = mapped_column(String(64), nullable=True)
    __table_args__ = (Index('ix_click_dedup_window', 'link_id', 'request_fingerprint', 'clicked_at'),)


class PerformanceRevision(Base):
    __tablename__ = 'performance_revisions'
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    record_id = mapped_column(Uuid(as_uuid=True), ForeignKey('performance_records.id'), nullable=False)
    version = mapped_column(Integer, nullable=False)
    resource = mapped_column(JSONB, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=True)
    __table_args__ = (UniqueConstraint('record_id', 'version', name='uq_performance_revision_version'),)


class JobOutput(Base):
    __tablename__ = 'job_outputs'
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id = mapped_column(Uuid(as_uuid=True), ForeignKey('generation_jobs.id'), nullable=False)
    output_index = mapped_column(Integer, nullable=False)
    resource_type = mapped_column(String(100), nullable=False)
    resource_id = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint('job_id', 'output_index', name='uq_job_output_number'),)


class MonitorDispatch(Base):
    __tablename__ = 'monitor_dispatches'
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    monitor_id = mapped_column(Uuid(as_uuid=True), ForeignKey('competitor_monitors.id'), nullable=False)
    scheduled_at = mapped_column(DateTime(timezone=True), nullable=False)
    job_id = mapped_column(Uuid(as_uuid=True), ForeignKey('generation_jobs.id'), nullable=False)
    __table_args__ = (UniqueConstraint('monitor_id', 'scheduled_at', name='uq_monitor_dispatch_time'),)


class ModelCall(Base):
    __tablename__ = 'model_calls'
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id = mapped_column(Uuid(as_uuid=True), ForeignKey('generation_jobs.id'), nullable=True, index=True)
    model_config_id = mapped_column(Uuid(as_uuid=True), ForeignKey('model_configs.id'), nullable=True)
    model_config_version = mapped_column(Integer, nullable=True)
    provider = mapped_column(String(100), nullable=False)
    model_name = mapped_column(String(200), nullable=False)
    prompt_version = mapped_column(String(100), nullable=False)
    request_id = mapped_column(String(200), nullable=True)
    input_tokens = mapped_column(Integer, nullable=True)
    output_tokens = mapped_column(Integer, nullable=True)
    duration_ms = mapped_column(Integer, nullable=True)
    outcome = mapped_column(String(32), nullable=False)
    error_code = mapped_column(String(100), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


INTERNAL_MODELS = {}
for cls in (JobRuntime, FileStorage, ImportState, IdempotencyRecord, AuthorizationState, ClickEvent, PerformanceRevision, JobOutput, MonitorDispatch, ModelCall):
    cls.SCHEMA_NAME = cls.__name__
    cls.__dto_fields__ = tuple(cls.__table__.columns.keys())
    cls.__pk_field__ = next(iter(cls.__table__.primary_key.columns)).key
    cls.__ref_fields__ = {}
    cls.__money_fields__ = ()
    cls.__ratio_fields__ = ()
    cls.__computed_fields__ = ()
    INTERNAL_MODELS[cls.__name__] = cls
