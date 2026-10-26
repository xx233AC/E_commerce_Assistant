# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class OperatingRound(Base):
    __tablename__ = 'operating_rounds'
    SCHEMA_NAME = 'OperatingRound'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'name', 'objective', 'round_no', 'previous_round_id', 'source_review', 'adopted_action_ids', 'selected_diagnosis', 'status', 'stage', 'started_at', 'closed_at', 'close_remark')
    __pk_field__ = 'id'
    __ref_fields__ = {'source_review': ('source_review_id', 'source_review_version'), 'selected_diagnosis': ('selected_diagnosis_id', 'selected_diagnosis_version')}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    name = mapped_column(String(100), nullable=False)
    objective = mapped_column(String(4000), nullable=False)
    round_no = mapped_column(Integer, nullable=False)
    previous_round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=True, index=True)
    source_review_id = mapped_column(Uuid(as_uuid=True), ForeignKey('review_reports.id', use_alter=True), nullable=True, index=True)
    source_review_version = mapped_column(Integer, nullable=True)
    adopted_action_ids = mapped_column(JSONB, nullable=False, default=list)
    selected_diagnosis_id = mapped_column(Uuid(as_uuid=True), ForeignKey('diagnoses.id', use_alter=True), nullable=True, index=True)
    selected_diagnosis_version = mapped_column(Integer, nullable=True)
    status = mapped_column(Text, nullable=False)
    stage = mapped_column(Text, nullable=False)
    started_at = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at = mapped_column(DateTime(timezone=True), nullable=True)
    close_remark = mapped_column(String(4000), nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint('round_no >= 1', name='round_no_minimum'),
        CheckConstraint('round_no <= 2147483647', name='round_no_maximum'),
        CheckConstraint('source_review_version >= 1', name='source_review_version_positive'),
        CheckConstraint('(source_review_id IS NULL) = (source_review_version IS NULL)', name='source_review_ref_complete'),
        CheckConstraint('selected_diagnosis_version >= 1', name='selected_diagnosis_version_positive'),
        CheckConstraint('(selected_diagnosis_id IS NULL) = (selected_diagnosis_version IS NULL)', name='selected_diagnosis_ref_complete'),
        CheckConstraint("status IN ('active', 'completed', 'cancelled')", name='status_enum'),
        CheckConstraint("stage IN ('draft', 'diagnosing', 'creative', 'generating', 'reviewing', 'planning', 'executing', 'analyzing', 'completed', 'cancelled')", name='stage_enum'),
        UniqueConstraint('product_id', 'round_no', name='uq_round_product_number'),
        Index('uq_round_active_product', 'product_id', unique=True, postgresql_where=text("status = 'active'")),
    )


class RoundSnapshot(Base):
    __tablename__ = 'round_snapshots'
    SCHEMA_NAME = 'RoundSnapshot'
    __dto_fields__ = ('id', 'round_id', 'product', 'skus', 'competitors', 'captured_at')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=False, index=True)
    product = mapped_column(JSONB, nullable=False)
    skus = mapped_column(JSONB, nullable=False, default=list)
    competitors = mapped_column(JSONB, nullable=False, default=list)
    captured_at = mapped_column(DateTime(timezone=True), nullable=False)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True)

