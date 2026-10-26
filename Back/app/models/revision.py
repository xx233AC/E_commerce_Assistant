# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class ResourceRevision(Base):
    __tablename__ = 'resource_revisions'
    SCHEMA_NAME = 'ResourceRevision'
    __dto_fields__ = ('revision_id', 'resource_type', 'resource_id', 'version', 'created_at', 'created_by', 'change_reason', 'resource')
    __pk_field__ = 'revision_id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    revision_id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    resource_type = mapped_column(Text, nullable=False)
    resource_id = mapped_column(Uuid(as_uuid=True), nullable=False)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    change_reason = mapped_column(String(4000), nullable=True)
    resource = mapped_column(JSONB, nullable=False)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=True, index=True)
    __table_args__ = (
        CheckConstraint("resource_type IN ('diagnosis', 'creative_plan', 'ad_recommendation', 'review_report')", name='resource_type_enum'),
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        UniqueConstraint('resource_type', 'resource_id', 'version', name='uq_resource_revision_version'),
    )

