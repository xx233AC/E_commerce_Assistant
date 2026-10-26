# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class ImportBatch(Base):
    __tablename__ = 'import_batches'
    SCHEMA_NAME = 'ImportBatch'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'import_type', 'file_id', 'store_id', 'product_id', 'round_id', 'status', 'total_rows', 'valid_rows', 'invalid_rows', 'succeeded_rows', 'failed_rows', 'preview_token', 'preview_expires_at', 'errors_count', 'error_message')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    import_type = mapped_column(Text, nullable=False)
    file_id = mapped_column(Uuid(as_uuid=True), ForeignKey('files.id'), nullable=False, index=True)
    store_id = mapped_column(Uuid(as_uuid=True), ForeignKey('stores.id'), nullable=False, index=True)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True)
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=True, index=True)
    status = mapped_column(Text, nullable=False)
    total_rows = mapped_column(Integer, nullable=False)
    valid_rows = mapped_column(Integer, nullable=False)
    invalid_rows = mapped_column(Integer, nullable=False)
    succeeded_rows = mapped_column(Integer, nullable=False)
    failed_rows = mapped_column(Integer, nullable=False)
    preview_token = mapped_column(String(200), nullable=True)
    preview_expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    errors_count = mapped_column(Integer, nullable=False)
    error_message = mapped_column(String(4000), nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("import_type IN ('products', 'sku_inventory', 'performance_records', 'platform_mappings')", name='import_type_enum'),
        CheckConstraint("status IN ('validating', 'preview_ready', 'committing', 'succeeded', 'partially_succeeded', 'failed', 'expired')", name='status_enum'),
        CheckConstraint('total_rows >= 0', name='total_rows_minimum'),
        CheckConstraint('total_rows <= 2147483647', name='total_rows_maximum'),
        CheckConstraint('valid_rows >= 0', name='valid_rows_minimum'),
        CheckConstraint('valid_rows <= 2147483647', name='valid_rows_maximum'),
        CheckConstraint('invalid_rows >= 0', name='invalid_rows_minimum'),
        CheckConstraint('invalid_rows <= 2147483647', name='invalid_rows_maximum'),
        CheckConstraint('succeeded_rows >= 0', name='succeeded_rows_minimum'),
        CheckConstraint('succeeded_rows <= 2147483647', name='succeeded_rows_maximum'),
        CheckConstraint('failed_rows >= 0', name='failed_rows_minimum'),
        CheckConstraint('failed_rows <= 2147483647', name='failed_rows_maximum'),
        CheckConstraint('errors_count >= 0', name='errors_count_minimum'),
        CheckConstraint('errors_count <= 2147483647', name='errors_count_maximum'),
    )

