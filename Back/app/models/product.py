# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class Product(Base):
    __tablename__ = 'products'
    SCHEMA_NAME = 'Product'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'store_id', 'platform', 'name', 'category', 'price', 'cost', 'target_audience', 'selling_points', 'product_url', 'image_file_ids', 'status', 'last_diagnosis_at', 'last_review_at')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ('price', 'cost')
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    store_id = mapped_column(Uuid(as_uuid=True), ForeignKey('stores.id'), nullable=False, index=True)
    platform = mapped_column(Text, nullable=False)
    name = mapped_column(String(200), nullable=False)
    category = mapped_column(String(100), nullable=False)
    price = mapped_column(Numeric(14, 2), nullable=False)
    cost = mapped_column(Numeric(14, 2), nullable=False)
    target_audience = mapped_column(String(4000), nullable=False)
    selling_points = mapped_column(JSONB, nullable=False)
    product_url = mapped_column(String(2048), nullable=True)
    image_file_ids = mapped_column(JSONB, nullable=False, default=list)
    status = mapped_column(Text, nullable=False)
    last_diagnosis_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_review_at = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')", name='platform_enum'),
        CheckConstraint('price >= 0', name='price_nonnegative'),
        CheckConstraint('cost >= 0', name='cost_nonnegative'),
        CheckConstraint("status IN ('draft', 'active', 'inactive')", name='status_enum'),
    )


class PlatformMapping(Base):
    __tablename__ = 'platform_mappings'
    SCHEMA_NAME = 'PlatformMapping'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'platform', 'platform_product_id', 'sku_id', 'platform_sku_id', 'mapping_status')
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
    platform = mapped_column(Text, nullable=False)
    platform_product_id = mapped_column(String(100), nullable=False)
    sku_id = mapped_column(Uuid(as_uuid=True), ForeignKey('skus.id'), nullable=True, index=True)
    platform_sku_id = mapped_column(String(100), nullable=True)
    mapping_status = mapped_column(Text, nullable=False)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')", name='platform_enum'),
        CheckConstraint("mapping_status IN ('active', 'inactive')", name='mapping_status_enum'),
        CheckConstraint('(sku_id IS NULL) = (platform_sku_id IS NULL)', name='sku_mapping_pair'),
        Index('uq_mapping_external_sku', 'platform', 'platform_sku_id', unique=True, postgresql_where=text('platform_sku_id IS NOT NULL')),
    )

