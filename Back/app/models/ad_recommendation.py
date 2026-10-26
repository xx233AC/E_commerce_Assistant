# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class AdRecommendation(Base):
    __tablename__ = 'ad_recommendations'
    SCHEMA_NAME = 'AdRecommendation'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'round_id', 'diagnosis', 'content', 'budget_cap', 'daily_cap', 'duration_days', 'confirm_status', 'latest_confirmation', 'provenance')
    __pk_field__ = 'id'
    __ref_fields__ = {'diagnosis': ('diagnosis_id', 'diagnosis_version')}
    __money_fields__ = ('budget_cap', 'daily_cap')
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=False, index=True)
    diagnosis_id = mapped_column(Uuid(as_uuid=True), ForeignKey('diagnoses.id'), nullable=False, index=True)
    diagnosis_version = mapped_column(Integer, nullable=False)
    content = mapped_column(JSONB, nullable=False)
    budget_cap = mapped_column(Numeric(14, 2), nullable=False)
    daily_cap = mapped_column(Numeric(14, 2), nullable=False)
    duration_days = mapped_column(Integer, nullable=False)
    confirm_status = mapped_column(Text, nullable=False)
    latest_confirmation = mapped_column(JSONB, nullable=True)
    provenance = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint('diagnosis_version >= 1', name='diagnosis_version_positive'),
        CheckConstraint('budget_cap >= 0', name='budget_cap_nonnegative'),
        CheckConstraint('daily_cap >= 0', name='daily_cap_nonnegative'),
        CheckConstraint('duration_days >= 1', name='duration_days_minimum'),
        CheckConstraint('duration_days <= 90', name='duration_days_maximum'),
        CheckConstraint("confirm_status IN ('pending', 'confirmed', 'rejected')", name='confirm_status_enum'),
    )


class Confirmation(Base):
    __tablename__ = 'confirmations'
    SCHEMA_NAME = 'Confirmation'
    __dto_fields__ = ('id', 'resource_version', 'decision', 'operator_id', 'remark', 'created_at')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    resource_version = mapped_column(Integer, nullable=False)
    decision = mapped_column(Text, nullable=False)
    operator_id = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    remark = mapped_column(String(2000), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    recommendation_id = mapped_column(Uuid(as_uuid=True), ForeignKey('ad_recommendations.id'), nullable=False, index=True)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=True, index=True)
    __table_args__ = (
        CheckConstraint('resource_version >= 1', name='resource_version_minimum'),
        CheckConstraint('resource_version <= 2147483647', name='resource_version_maximum'),
        CheckConstraint("decision IN ('confirmed', 'rejected')", name='decision_enum'),
    )

