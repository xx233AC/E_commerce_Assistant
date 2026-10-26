# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class ReviewReport(Base):
    __tablename__ = 'review_reports'
    SCHEMA_NAME = 'ReviewReport'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'round_id', 'period_start', 'period_end', 'granularity', 'experiment_ids', 'performance_record_refs', 'metric_snapshot', 'content', 'provenance')
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
    period_start = mapped_column(Date, nullable=False)
    period_end = mapped_column(Date, nullable=False)
    granularity = mapped_column(Text, nullable=False)
    experiment_ids = mapped_column(JSONB, nullable=False, default=list)
    performance_record_refs = mapped_column(JSONB, nullable=False, default=list)
    metric_snapshot = mapped_column(JSONB, nullable=False)
    content = mapped_column(JSONB, nullable=False)
    provenance = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("granularity IN ('product_day', 'experiment_day')", name='granularity_enum'),
        CheckConstraint('period_end >= period_start', name='period_dates'),
    )

