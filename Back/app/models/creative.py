# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class CreativePlan(Base):
    __tablename__ = 'creative_plans'
    SCHEMA_NAME = 'CreativePlan'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'round_id', 'plan_type', 'title', 'content', 'rationale_text', 'status', 'diagnosis', 'snapshot_id', 'provenance')
    __pk_field__ = 'id'
    __ref_fields__ = {'diagnosis': ('diagnosis_id', 'diagnosis_version')}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=False, index=True)
    plan_type = mapped_column(Text, nullable=False)
    title = mapped_column(String(200), nullable=False)
    content = mapped_column(JSONB, nullable=False)
    rationale_text = mapped_column(String(4000), nullable=False)
    status = mapped_column(Text, nullable=False)
    diagnosis_id = mapped_column(Uuid(as_uuid=True), ForeignKey('diagnoses.id'), nullable=False, index=True)
    diagnosis_version = mapped_column(Integer, nullable=False)
    snapshot_id = mapped_column(Uuid(as_uuid=True), ForeignKey('round_snapshots.id'), nullable=False, index=True)
    provenance = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("plan_type IN ('main_image', 'video_script', 'title')", name='plan_type_enum'),
        CheckConstraint("status IN ('draft', 'selected', 'archived')", name='status_enum'),
        CheckConstraint('diagnosis_version >= 1', name='diagnosis_version_positive'),
        Index('uq_plan_selected_kind', 'round_id', 'plan_type', unique=True, postgresql_where=text("status = 'selected'")),
    )

