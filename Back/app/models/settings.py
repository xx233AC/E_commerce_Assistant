# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class ModelConfig(Base):
    __tablename__ = 'model_configs'
    SCHEMA_NAME = 'ModelConfig'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'name', 'provider', 'base_url', 'model_name', 'capabilities', 'enabled', 'execution_mode', 'request_timeout_sec', 'secret_env_name', 'secret_configured')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ('secret_configured',)
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    name = mapped_column(String(100), nullable=False)
    provider = mapped_column(Text, nullable=False)
    base_url = mapped_column(String(2048), nullable=False)
    model_name = mapped_column(String(200), nullable=False)
    capabilities = mapped_column(JSONB, nullable=False)
    enabled = mapped_column(Boolean, nullable=False)
    execution_mode = mapped_column(Text, nullable=False)
    request_timeout_sec = mapped_column(Integer, nullable=False)
    secret_env_name = mapped_column(Text, nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("provider IN ('openai_compatible', 'image_provider', 'video_provider', 'demo')", name='provider_enum'),
        CheckConstraint("execution_mode IN ('real', 'demo')", name='execution_mode_enum'),
        CheckConstraint('request_timeout_sec >= 10', name='request_timeout_sec_minimum'),
        CheckConstraint('request_timeout_sec <= 1800', name='request_timeout_sec_maximum'),
    )


class SystemSettings(Base):
    __tablename__ = 'system_settings'
    SCHEMA_NAME = 'SystemSettings'
    __dto_fields__ = ('version', 'text_model_config_id', 'image_model_config_id', 'video_model_config_id', 'demo_generation_enabled', 'demo_data_enabled', 'max_upload_image_bytes', 'max_upload_video_bytes', 'max_import_rows', 'updated_at')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=lambda: UUID('00000000-0000-0000-0000-000000000001'))
    version = mapped_column(Integer, nullable=False, default=1)
    text_model_config_id = mapped_column(Uuid(as_uuid=True), ForeignKey('model_configs.id'), nullable=True, index=True)
    image_model_config_id = mapped_column(Uuid(as_uuid=True), ForeignKey('model_configs.id'), nullable=True, index=True)
    video_model_config_id = mapped_column(Uuid(as_uuid=True), ForeignKey('model_configs.id'), nullable=True, index=True)
    demo_generation_enabled = mapped_column(Boolean, nullable=False, default=False)
    demo_data_enabled = mapped_column(Boolean, nullable=False, default=False)
    max_upload_image_bytes = mapped_column(Integer, nullable=False)
    max_upload_video_bytes = mapped_column(Integer, nullable=False)
    max_import_rows = mapped_column(Integer, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint('max_upload_image_bytes >= 1', name='max_upload_image_bytes_minimum'),
        CheckConstraint('max_upload_image_bytes <= 20971520', name='max_upload_image_bytes_maximum'),
        CheckConstraint('max_upload_video_bytes >= 1', name='max_upload_video_bytes_minimum'),
        CheckConstraint('max_upload_video_bytes <= 524288000', name='max_upload_video_bytes_maximum'),
        CheckConstraint('max_import_rows >= 1', name='max_import_rows_minimum'),
        CheckConstraint('max_import_rows <= 10000', name='max_import_rows_maximum'),
        CheckConstraint("id = '00000000-0000-0000-0000-000000000001'", name='singleton'),
    )


class QueueSettings(Base):
    __tablename__ = 'queue_settings'
    SCHEMA_NAME = 'QueueSettings'
    __dto_fields__ = ('version', 'text_concurrency', 'image_concurrency', 'video_concurrency', 'max_attempts', 'job_timeout_sec', 'updated_at')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=lambda: UUID('00000000-0000-0000-0000-000000000001'))
    version = mapped_column(Integer, nullable=False, default=1)
    text_concurrency = mapped_column(Integer, nullable=False)
    image_concurrency = mapped_column(Integer, nullable=False)
    video_concurrency = mapped_column(Integer, nullable=False)
    max_attempts = mapped_column(Integer, nullable=False)
    job_timeout_sec = mapped_column(Integer, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint('text_concurrency >= 1', name='text_concurrency_minimum'),
        CheckConstraint('text_concurrency <= 10', name='text_concurrency_maximum'),
        CheckConstraint('image_concurrency >= 1', name='image_concurrency_minimum'),
        CheckConstraint('image_concurrency <= 10', name='image_concurrency_maximum'),
        CheckConstraint('video_concurrency >= 1', name='video_concurrency_minimum'),
        CheckConstraint('video_concurrency <= 5', name='video_concurrency_maximum'),
        CheckConstraint('max_attempts >= 1', name='max_attempts_minimum'),
        CheckConstraint('max_attempts <= 5', name='max_attempts_maximum'),
        CheckConstraint('job_timeout_sec >= 60', name='job_timeout_sec_minimum'),
        CheckConstraint('job_timeout_sec <= 7200', name='job_timeout_sec_maximum'),
        CheckConstraint("id = '00000000-0000-0000-0000-000000000001'", name='singleton'),
    )

