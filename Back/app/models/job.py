# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class GenerationJob(Base):
    __tablename__ = 'generation_jobs'
    SCHEMA_NAME = 'GenerationJob'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'round_id', 'creative_plan_id', 'job_kind', 'job_status', 'dispatch_status', 'execution_mode', 'attempts', 'max_attempts', 'cancellation_requested', 'result_resources', 'error_code', 'error_message', 'next_run_at', 'started_at', 'finished_at', 'progress', 'creative_plan_version', 'model_config_id', 'source_url', 'submitted_by', 'queued_at', 'deadline_at', 'model_config_version')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=True, index=True)
    creative_plan_id = mapped_column(Uuid(as_uuid=True), ForeignKey('creative_plans.id'), nullable=True, index=True)
    job_kind = mapped_column(Text, nullable=False)
    job_status = mapped_column(Text, nullable=False)
    dispatch_status = mapped_column(Text, nullable=False)
    execution_mode = mapped_column(Text, nullable=False)
    attempts = mapped_column(Integer, nullable=False)
    max_attempts = mapped_column(Integer, nullable=False)
    cancellation_requested = mapped_column(Boolean, nullable=False)
    result_resources = mapped_column(JSONB, nullable=False, default=list)
    error_code = mapped_column(String(100), nullable=True)
    error_message = mapped_column(String(4000), nullable=True)
    next_run_at = mapped_column(DateTime(timezone=True), nullable=True)
    started_at = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at = mapped_column(DateTime(timezone=True), nullable=True)
    progress = mapped_column(Integer, nullable=False)
    creative_plan_version = mapped_column(Integer, nullable=True)
    model_config_id = mapped_column(Uuid(as_uuid=True), ForeignKey('model_configs.id'), nullable=True, index=True)
    source_url = mapped_column(String(2048), nullable=True)
    submitted_by = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    queued_at = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at = mapped_column(DateTime(timezone=True), nullable=True)
    model_config_version = mapped_column(Integer, nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("job_kind IN ('diagnosis', 'main_image_plan', 'video_script', 'title_plan', 'image', 'video', 'ad_recommendation', 'ad_experiment', 'review_report', 'public_link_parse', 'asset_sync', 'timeout_sweep', 'competitor_monitor_sweep', 'demo_data')", name='job_kind_enum'),
        CheckConstraint("job_status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled', 'timeout')", name='job_status_enum'),
        CheckConstraint("dispatch_status IN ('awaiting_dispatch', 'queued', 'dispatched')", name='dispatch_status_enum'),
        CheckConstraint("execution_mode IN ('real', 'demo')", name='execution_mode_enum'),
        CheckConstraint('attempts >= 0', name='attempts_minimum'),
        CheckConstraint('attempts <= 2147483647', name='attempts_maximum'),
        CheckConstraint('max_attempts >= 1', name='max_attempts_minimum'),
        CheckConstraint('max_attempts <= 5', name='max_attempts_maximum'),
        CheckConstraint('progress >= 0', name='progress_minimum'),
        CheckConstraint('progress <= 100', name='progress_maximum'),
        CheckConstraint('creative_plan_version >= 1', name='creative_plan_version_minimum'),
        CheckConstraint('creative_plan_version <= 2147483647', name='creative_plan_version_maximum'),
        CheckConstraint('model_config_version >= 1', name='model_config_version_minimum'),
        CheckConstraint('model_config_version <= 2147483647', name='model_config_version_maximum'),
    )


class JobEvent(Base):
    __tablename__ = 'job_events'
    SCHEMA_NAME = 'JobEvent'
    __dto_fields__ = ('id', 'job_id', 'sequence', 'attempt', 'event_type', 'event_message', 'created_at')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id = mapped_column(Uuid(as_uuid=True), ForeignKey('generation_jobs.id'), nullable=False, index=True)
    sequence = mapped_column(Integer, nullable=False)
    attempt = mapped_column(Integer, nullable=False)
    event_type = mapped_column(Text, nullable=False)
    event_message = mapped_column(String(4000), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        CheckConstraint('sequence >= 1', name='sequence_minimum'),
        CheckConstraint('sequence <= 2147483647', name='sequence_maximum'),
        CheckConstraint('attempt >= 0', name='attempt_minimum'),
        CheckConstraint('attempt <= 2147483647', name='attempt_maximum'),
        CheckConstraint("event_type IN ('enqueued', 'running', 'succeeded', 'failed', 'retry_scheduled', 'retry_requested', 'cancellation_requested', 'cancelled', 'timeout', 'progress', 'late_result_ignored')", name='event_type_enum'),
        UniqueConstraint('job_id', 'sequence', name='uq_job_event_sequence'),
    )

