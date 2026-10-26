# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class Competitor(Base):
    __tablename__ = 'competitors'
    SCHEMA_NAME = 'Competitor'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'name', 'platform', 'url', 'price', 'sales_hint', 'title', 'main_image_file_id', 'selling_points', 'review_keywords', 'status')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ('price',)
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    name = mapped_column(String(200), nullable=False)
    platform = mapped_column(Text, nullable=False)
    url = mapped_column(String(2048), nullable=True)
    price = mapped_column(Numeric(14, 2), nullable=True)
    sales_hint = mapped_column(String(500), nullable=True)
    title = mapped_column(String(500), nullable=True)
    main_image_file_id = mapped_column(Uuid(as_uuid=True), ForeignKey('files.id'), nullable=True, index=True)
    selling_points = mapped_column(JSONB, nullable=False, default=list)
    review_keywords = mapped_column(JSONB, nullable=False, default=list)
    status = mapped_column(Text, nullable=False)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')", name='platform_enum'),
        CheckConstraint('price >= 0', name='price_nonnegative'),
        CheckConstraint("status IN ('active', 'archived')", name='status_enum'),
    )


class CompetitorMonitor(Base):
    __tablename__ = 'competitor_monitors'
    SCHEMA_NAME = 'CompetitorMonitor'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'competitor_id', 'monitor_status', 'interval_minutes', 'next_run_at', 'last_error')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    competitor_id = mapped_column(Uuid(as_uuid=True), ForeignKey('competitors.id'), nullable=False, index=True)
    monitor_status = mapped_column(Text, nullable=False)
    interval_minutes = mapped_column(Integer, nullable=False)
    next_run_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_error = mapped_column(String(4000), nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("monitor_status IN ('active', 'paused')", name='monitor_status_enum'),
        CheckConstraint('interval_minutes >= 60', name='interval_minutes_minimum'),
        CheckConstraint('interval_minutes <= 2147483647', name='interval_minutes_maximum'),
        UniqueConstraint('competitor_id', name='uq_monitor_competitor'),
    )


class MonitorSnapshot(Base):
    __tablename__ = 'monitor_snapshots'
    SCHEMA_NAME = 'MonitorSnapshot'
    __dto_fields__ = ('id', 'monitor_id', 'competitor_id', 'price', 'sales_hint', 'selling_points', 'source_url', 'captured_at', 'completeness', 'warnings')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ('price',)
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    monitor_id = mapped_column(Uuid(as_uuid=True), ForeignKey('competitor_monitors.id'), nullable=False, index=True)
    competitor_id = mapped_column(Uuid(as_uuid=True), ForeignKey('competitors.id'), nullable=False, index=True)
    price = mapped_column(Numeric(14, 2), nullable=True)
    sales_hint = mapped_column(String(500), nullable=True)
    selling_points = mapped_column(JSONB, nullable=False, default=list)
    source_url = mapped_column(String(2048), nullable=False)
    captured_at = mapped_column(DateTime(timezone=True), nullable=False)
    completeness = mapped_column(Text, nullable=False)
    warnings = mapped_column(JSONB, nullable=False, default=list)
    __table_args__ = (
        CheckConstraint('price >= 0', name='price_nonnegative'),
        CheckConstraint("completeness IN ('complete', 'partial')", name='completeness_enum'),
    )


class ParseResult(Base):
    __tablename__ = 'parse_results'
    SCHEMA_NAME = 'ParseResult'
    __dto_fields__ = ('source_url', 'name', 'title', 'price', 'sales_hint', 'selling_points', 'candidate_image_urls', 'missing_fields', 'warnings', 'captured_at')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ('price',)
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_url = mapped_column(String(2048), nullable=False)
    name = mapped_column(String(200), nullable=True)
    title = mapped_column(String(500), nullable=True)
    price = mapped_column(Numeric(14, 2), nullable=True)
    sales_hint = mapped_column(String(500), nullable=True)
    selling_points = mapped_column(JSONB, nullable=False, default=list)
    candidate_image_urls = mapped_column(JSONB, nullable=False, default=list)
    missing_fields = mapped_column(JSONB, nullable=False, default=list)
    warnings = mapped_column(JSONB, nullable=False, default=list)
    captured_at = mapped_column(DateTime(timezone=True), nullable=False)
    job_id = mapped_column(Uuid(as_uuid=True), ForeignKey('generation_jobs.id'), nullable=False, unique=True)
    __table_args__ = (
        CheckConstraint('price >= 0', name='price_nonnegative'),
    )

