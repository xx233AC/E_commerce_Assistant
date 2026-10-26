# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class Sku(Base):
    __tablename__ = 'skus'
    SCHEMA_NAME = 'Sku'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'sku_code', 'sku_name', 'spec', 'price', 'cost', 'status', 'platform_sku_id')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ('price', 'cost')
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)
    sku_code = mapped_column(String(64), nullable=False)
    sku_name = mapped_column(String(200), nullable=False)
    spec = mapped_column(JSONB, nullable=False, default=list)
    price = mapped_column(Numeric(14, 2), nullable=False)
    cost = mapped_column(Numeric(14, 2), nullable=False)
    status = mapped_column(Text, nullable=False)
    platform_sku_id = mapped_column(String(100), nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint('price >= 0', name='price_nonnegative'),
        CheckConstraint('cost >= 0', name='cost_nonnegative'),
        CheckConstraint("status IN ('active', 'inactive')", name='status_enum'),
        UniqueConstraint('sku_code', name='uq_skus_code'),
    )


class Inventory(Base):
    __tablename__ = 'inventories'
    SCHEMA_NAME = 'Inventory'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'sku_id', 'stock_qty', 'locked_qty', 'available_qty', 'warning_threshold', 'location_text', 'is_low_stock')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ('available_qty', 'is_low_stock')
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    sku_id = mapped_column(Uuid(as_uuid=True), ForeignKey('skus.id'), nullable=False, index=True)
    stock_qty = mapped_column(Integer, nullable=False)
    locked_qty = mapped_column(Integer, nullable=False)
    warning_threshold = mapped_column(Integer, nullable=False)
    location_text = mapped_column(String(200), nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint('stock_qty >= 0', name='stock_qty_minimum'),
        CheckConstraint('stock_qty <= 2147483647', name='stock_qty_maximum'),
        CheckConstraint('locked_qty >= 0', name='locked_qty_minimum'),
        CheckConstraint('locked_qty <= 0', name='locked_qty_maximum'),
        CheckConstraint('warning_threshold >= 0', name='warning_threshold_minimum'),
        CheckConstraint('warning_threshold <= 2147483647', name='warning_threshold_maximum'),
        UniqueConstraint('sku_id', name='uq_inventory_sku'),
        CheckConstraint('stock_qty >= locked_qty', name='stock_locked'),
    )


class InventoryMovement(Base):
    __tablename__ = 'inventory_movements'
    SCHEMA_NAME = 'InventoryMovement'
    __dto_fields__ = ('id', 'sku_id', 'movement_type', 'change_qty', 'before_qty', 'after_qty', 'reason_text', 'reference_text', 'operator_id', 'created_at', 'inventory_version')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    sku_id = mapped_column(Uuid(as_uuid=True), ForeignKey('skus.id'), nullable=False, index=True)
    movement_type = mapped_column(Text, nullable=False)
    change_qty = mapped_column(Integer, nullable=False)
    before_qty = mapped_column(Integer, nullable=False)
    after_qty = mapped_column(Integer, nullable=False)
    reason_text = mapped_column(String(500), nullable=False)
    reference_text = mapped_column(String(200), nullable=True)
    operator_id = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    inventory_version = mapped_column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint("movement_type IN ('increase', 'decrease')", name='movement_type_enum'),
        CheckConstraint('before_qty >= 0', name='before_qty_minimum'),
        CheckConstraint('before_qty <= 2147483647', name='before_qty_maximum'),
        CheckConstraint('after_qty >= 0', name='after_qty_minimum'),
        CheckConstraint('after_qty <= 2147483647', name='after_qty_maximum'),
        CheckConstraint('inventory_version >= 1', name='inventory_version_minimum'),
        CheckConstraint('inventory_version <= 2147483647', name='inventory_version_maximum'),
    )

