# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class Asset(Base):
    __tablename__ = 'assets'
    SCHEMA_NAME = 'Asset'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'round_id', 'creative_plan_id', 'creative_plan_version', 'file_id', 'asset_type', 'origin', 'model_name', 'source_job_id', 'width', 'height', 'duration_sec', 'review_status', 'reviewed_by', 'reviewed_at', 'review_remark', 'version_no', 'parent_asset_id', 'execution_mode', 'usage_scene', 'score', 'tags', 'remark')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=False, index=True)
    creative_plan_id = mapped_column(Uuid(as_uuid=True), ForeignKey('creative_plans.id'), nullable=True, index=True)
    creative_plan_version = mapped_column(Integer, nullable=True)
    file_id = mapped_column(Uuid(as_uuid=True), ForeignKey('files.id'), nullable=False, index=True)
    asset_type = mapped_column(Text, nullable=False)
    origin = mapped_column(Text, nullable=False)
    model_name = mapped_column(String(200), nullable=True)
    source_job_id = mapped_column(Uuid(as_uuid=True), ForeignKey('generation_jobs.id'), nullable=True, index=True)
    width = mapped_column(Integer, nullable=False)
    height = mapped_column(Integer, nullable=False)
    duration_sec = mapped_column(Integer, nullable=True)
    review_status = mapped_column(Text, nullable=False)
    reviewed_by = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    reviewed_at = mapped_column(DateTime(timezone=True), nullable=True)
    review_remark = mapped_column(String(4000), nullable=True)
    version_no = mapped_column(Integer, nullable=False)
    parent_asset_id = mapped_column(Uuid(as_uuid=True), ForeignKey('assets.id'), nullable=True, index=True)
    execution_mode = mapped_column(Text, nullable=False)
    usage_scene = mapped_column(Text, nullable=False)
    score = mapped_column(Integer, nullable=True)
    tags = mapped_column(JSONB, nullable=False, default=list)
    remark = mapped_column(String(4000), nullable=True)
    output_index = mapped_column(Integer, nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint('creative_plan_version >= 1', name='creative_plan_version_minimum'),
        CheckConstraint('creative_plan_version <= 2147483647', name='creative_plan_version_maximum'),
        CheckConstraint("asset_type IN ('image', 'video')", name='asset_type_enum'),
        CheckConstraint("origin IN ('generated', 'uploaded')", name='origin_enum'),
        CheckConstraint('width >= 1', name='width_minimum'),
        CheckConstraint('width <= 2147483647', name='width_maximum'),
        CheckConstraint('height >= 1', name='height_minimum'),
        CheckConstraint('height <= 2147483647', name='height_maximum'),
        CheckConstraint('duration_sec >= 1', name='duration_sec_minimum'),
        CheckConstraint('duration_sec <= 2147483647', name='duration_sec_maximum'),
        CheckConstraint("review_status IN ('pending', 'approved', 'rejected')", name='review_status_enum'),
        CheckConstraint('version_no >= 1', name='version_no_minimum'),
        CheckConstraint('version_no <= 2147483647', name='version_no_maximum'),
        CheckConstraint("execution_mode IN ('real', 'demo')", name='execution_mode_enum'),
        CheckConstraint("usage_scene IN ('main_image', 'detail_image', 'short_video', 'ad_creative', 'other')", name='usage_scene_enum'),
        CheckConstraint('score >= 1', name='score_minimum'),
        CheckConstraint('score <= 5', name='score_maximum'),
        UniqueConstraint('source_job_id', 'output_index', name='uq_asset_job_output'),
        CheckConstraint('output_index IS NULL OR output_index >= 0', name='output_index_nonnegative'),
        CheckConstraint('(creative_plan_id IS NULL) = (creative_plan_version IS NULL)', name='creative_ref_complete'),
    )

