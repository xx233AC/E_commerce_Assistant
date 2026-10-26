# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class FileObject(Base):
    __tablename__ = 'files'
    SCHEMA_NAME = 'FileObject'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'file_name', 'content_type', 'byte_size', 'sha256', 'purpose', 'storage_status', 'execution_mode')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True)
    file_name = mapped_column(String(255), nullable=False)
    content_type = mapped_column(Text, nullable=False)
    byte_size = mapped_column(Integer, nullable=False)
    sha256 = mapped_column(Text, nullable=False)
    purpose = mapped_column(Text, nullable=False)
    storage_status = mapped_column(Text, nullable=False)
    execution_mode = mapped_column(Text, nullable=False)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("content_type IN ('image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')", name='content_type_enum'),
        CheckConstraint('byte_size >= 1', name='byte_size_minimum'),
        CheckConstraint('byte_size <= 524288000', name='byte_size_maximum'),
        CheckConstraint("purpose IN ('product_image', 'reference', 'media', 'import')", name='purpose_enum'),
        CheckConstraint("storage_status IN ('available', 'quarantined')", name='storage_status_enum'),
        CheckConstraint("execution_mode IN ('real', 'demo')", name='execution_mode_enum'),
    )

