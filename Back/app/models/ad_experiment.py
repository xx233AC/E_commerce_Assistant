# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class AdExperiment(Base):
    __tablename__ = 'ad_experiments'
    SCHEMA_NAME = 'AdExperiment'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'round_id', 'experiment_name', 'target_text', 'audience_text', 'budget_amount', 'daily_cap', 'success_metric', 'target_value', 'hypothesis_text', 'related_asset', 'related_link_id', 'title_plan', 'planned_start_date', 'planned_end_date', 'recommendation', 'experiment_status', 'confirmed_by', 'confirmed_at', 'external_campaign_id', 'actual_start_at', 'actual_end_at', 'last_transition_remark', 'execution_mode')
    __pk_field__ = 'id'
    __ref_fields__ = {'related_asset': ('related_asset_id', 'related_asset_version'), 'title_plan': ('title_plan_id', 'title_plan_version'), 'recommendation': ('recommendation_id', 'recommendation_version')}
    __money_fields__ = ('budget_amount', 'daily_cap')
    __ratio_fields__ = ('target_value',)
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=False, index=True)
    experiment_name = mapped_column(String(200), nullable=False)
    target_text = mapped_column(String(4000), nullable=False)
    audience_text = mapped_column(String(4000), nullable=False)
    budget_amount = mapped_column(Numeric(14, 2), nullable=False)
    daily_cap = mapped_column(Numeric(14, 2), nullable=False)
    success_metric = mapped_column(Text, nullable=False)
    target_value = mapped_column(Numeric(18, 6), nullable=False)
    hypothesis_text = mapped_column(String(4000), nullable=False)
    related_asset_id = mapped_column(Uuid(as_uuid=True), ForeignKey('assets.id'), nullable=False, index=True)
    related_asset_version = mapped_column(Integer, nullable=False)
    related_link_id = mapped_column(Uuid(as_uuid=True), ForeignKey('promotion_links.id'), nullable=False, index=True)
    title_plan_id = mapped_column(Uuid(as_uuid=True), ForeignKey('creative_plans.id'), nullable=True, index=True)
    title_plan_version = mapped_column(Integer, nullable=True)
    planned_start_date = mapped_column(Date, nullable=False)
    planned_end_date = mapped_column(Date, nullable=False)
    recommendation_id = mapped_column(Uuid(as_uuid=True), ForeignKey('ad_recommendations.id'), nullable=False, index=True)
    recommendation_version = mapped_column(Integer, nullable=False)
    experiment_status = mapped_column(Text, nullable=False)
    confirmed_by = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    confirmed_at = mapped_column(DateTime(timezone=True), nullable=True)
    external_campaign_id = mapped_column(String(200), nullable=True)
    actual_start_at = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_transition_remark = mapped_column(String(4000), nullable=True)
    execution_mode = mapped_column(Text, nullable=False)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint('budget_amount >= 0', name='budget_amount_nonnegative'),
        CheckConstraint('daily_cap >= 0', name='daily_cap_nonnegative'),
        CheckConstraint("success_metric IN ('ctr', 'conversion_rate', 'roas', 'cpa')", name='success_metric_enum'),
        CheckConstraint('target_value >= 0', name='target_value_nonnegative'),
        CheckConstraint('related_asset_version >= 1', name='related_asset_version_positive'),
        CheckConstraint('title_plan_version >= 1', name='title_plan_version_positive'),
        CheckConstraint('(title_plan_id IS NULL) = (title_plan_version IS NULL)', name='title_plan_ref_complete'),
        CheckConstraint('recommendation_version >= 1', name='recommendation_version_positive'),
        CheckConstraint("experiment_status IN ('draft', 'confirmed', 'running', 'finished', 'cancelled')", name='experiment_status_enum'),
        CheckConstraint("execution_mode IN ('real', 'demo')", name='execution_mode_enum'),
        CheckConstraint('planned_end_date >= planned_start_date', name='planned_dates'),
        CheckConstraint('actual_end_at IS NULL OR actual_start_at IS NULL OR actual_end_at >= actual_start_at', name='actual_dates'),
    )

