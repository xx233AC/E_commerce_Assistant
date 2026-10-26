# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class PromotionLink(Base):
    __tablename__ = 'promotion_links'
    SCHEMA_NAME = 'PromotionLink'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'product_id', 'round_id', 'link_name', 'target_url', 'utm', 'scene_text', 'status', 'tracking_code', 'short_url', 'click_count')
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
    round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=False, index=True)
    link_name = mapped_column(String(100), nullable=False)
    target_url = mapped_column(String(2048), nullable=False)
    utm = mapped_column(JSONB, nullable=False)
    scene_text = mapped_column(String(500), nullable=False)
    status = mapped_column(Text, nullable=False)
    tracking_code = mapped_column(String(64), nullable=False)
    short_url = mapped_column(String(2048), nullable=False)
    click_count = mapped_column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("status IN ('active', 'disabled')", name='status_enum'),
        CheckConstraint('click_count >= 0', name='click_count_minimum'),
        CheckConstraint('click_count <= 2147483647', name='click_count_maximum'),
        UniqueConstraint('tracking_code', name='uq_promotion_tracking'),
    )

