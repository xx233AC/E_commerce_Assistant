# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class PerformanceRecord(Base):
    __tablename__ = 'performance_records'
    SCHEMA_NAME = 'PerformanceRecord'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'round_id', 'granularity', 'record_date', 'experiment_id', 'source', 'impressions', 'clicks', 'conversions', 'spend', 'revenue', 'notes', 'creative_plan', 'generated_asset', 'promotion_link_id', 'ctr', 'conversion_rate', 'roas', 'cpa', 'roi', 'import_id', 'voided', 'void_reason')
    __pk_field__ = 'id'
    __ref_fields__ = {'creative_plan': ('creative_plan_id', 'creative_plan_version'), 'generated_asset': ('generated_asset_id', 'generated_asset_version')}
    __money_fields__ = ('spend', 'revenue', 'cpa')
    __ratio_fields__ = ('ctr', 'conversion_rate', 'roas')
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=False, index=True)
    granularity = mapped_column(Text, nullable=False)
    record_date = mapped_column(Date, nullable=False)
    experiment_id = mapped_column(Uuid(as_uuid=True), ForeignKey('ad_experiments.id'), nullable=True, index=True)
    source = mapped_column(Text, nullable=False)
    impressions = mapped_column(BigInteger, nullable=False)
    clicks = mapped_column(BigInteger, nullable=False)
    conversions = mapped_column(BigInteger, nullable=False)
    spend = mapped_column(Numeric(14, 2), nullable=False)
    revenue = mapped_column(Numeric(14, 2), nullable=False)
    notes = mapped_column(String(4000), nullable=True)
    creative_plan_id = mapped_column(Uuid(as_uuid=True), ForeignKey('creative_plans.id'), nullable=True, index=True)
    creative_plan_version = mapped_column(Integer, nullable=True)
    generated_asset_id = mapped_column(Uuid(as_uuid=True), ForeignKey('assets.id'), nullable=True, index=True)
    generated_asset_version = mapped_column(Integer, nullable=True)
    promotion_link_id = mapped_column(Uuid(as_uuid=True), ForeignKey('promotion_links.id'), nullable=True, index=True)
    ctr = mapped_column(Numeric(18, 6), nullable=True)
    conversion_rate = mapped_column(Numeric(18, 6), nullable=True)
    roas = mapped_column(Numeric(18, 6), nullable=True)
    cpa = mapped_column(Numeric(14, 2), nullable=True)
    roi = mapped_column(Numeric(18, 6), nullable=True)
    import_id = mapped_column(Uuid(as_uuid=True), ForeignKey('import_batches.id'), nullable=True, index=True)
    voided = mapped_column(Boolean, nullable=False)
    void_reason = mapped_column(String(4000), nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("granularity IN ('product_day', 'experiment_day')", name='granularity_enum'),
        CheckConstraint("source IN ('manual', 'import')", name='source_enum'),
        CheckConstraint('impressions >= 0', name='impressions_minimum'),
        CheckConstraint('impressions <= 9007199254740991', name='impressions_maximum'),
        CheckConstraint('clicks >= 0', name='clicks_minimum'),
        CheckConstraint('clicks <= 9007199254740991', name='clicks_maximum'),
        CheckConstraint('conversions >= 0', name='conversions_minimum'),
        CheckConstraint('conversions <= 9007199254740991', name='conversions_maximum'),
        CheckConstraint('spend >= 0', name='spend_nonnegative'),
        CheckConstraint('revenue >= 0', name='revenue_nonnegative'),
        CheckConstraint('creative_plan_version >= 1', name='creative_plan_version_positive'),
        CheckConstraint('(creative_plan_id IS NULL) = (creative_plan_version IS NULL)', name='creative_plan_ref_complete'),
        CheckConstraint('generated_asset_version >= 1', name='generated_asset_version_positive'),
        CheckConstraint('(generated_asset_id IS NULL) = (generated_asset_version IS NULL)', name='generated_asset_ref_complete'),
        CheckConstraint('ctr >= 0', name='ctr_nonnegative'),
        CheckConstraint('conversion_rate >= 0', name='conversion_rate_nonnegative'),
        CheckConstraint('roas >= 0', name='roas_nonnegative'),
        CheckConstraint('cpa >= 0', name='cpa_nonnegative'),
        CheckConstraint('roi IS NULL', name='roi_reserved_null'),
        Index('uq_performance_product_day', 'product_id', 'record_date', unique=True, postgresql_where=text("NOT voided AND granularity = 'product_day'")),
        Index('uq_performance_experiment_day', 'experiment_id', 'record_date', unique=True, postgresql_where=text("NOT voided AND granularity = 'experiment_day'")),
        CheckConstraint("(granularity = 'product_day' AND experiment_id IS NULL) OR (granularity = 'experiment_day' AND experiment_id IS NOT NULL)", name='granularity_reference'),
    )

