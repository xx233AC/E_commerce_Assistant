# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    SCHEMA_NAME = 'AuditLog'
    __dto_fields__ = ('id', 'actor_id', 'action', 'resource_type', 'resource_id', 'resource_version', 'request_id', 'outcome', 'summary', 'created_at')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_id = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    action = mapped_column(String(100), nullable=False)
    resource_type = mapped_column(String(100), nullable=False)
    resource_id = mapped_column(Uuid(as_uuid=True), nullable=True)
    resource_version = mapped_column(Integer, nullable=True)
    request_id = mapped_column(Uuid(as_uuid=True), nullable=False)
    outcome = mapped_column(Text, nullable=False)
    summary = mapped_column(String(4000), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        CheckConstraint('resource_version >= 1', name='resource_version_minimum'),
        CheckConstraint('resource_version <= 2147483647', name='resource_version_maximum'),
        CheckConstraint("outcome IN ('succeeded', 'rejected', 'failed')", name='outcome_enum'),
    )

