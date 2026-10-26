# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

class Store(Base):
    __tablename__ = 'stores'
    SCHEMA_NAME = 'Store'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'store_name', 'platform', 'external_store_id', 'owner_name', 'remark', 'currency', 'timezone', 'product_count', 'low_stock_sku_count')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ('product_count', 'low_stock_sku_count')
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    store_name = mapped_column(String(100), nullable=False)
    platform = mapped_column(Text, nullable=False)
    external_store_id = mapped_column(String(100), nullable=True)
    owner_name = mapped_column(String(100), nullable=False)
    remark = mapped_column(String(4000), nullable=True)
    currency = mapped_column(Text, nullable=False)
    timezone = mapped_column(Text, nullable=False)
    singleton_key = mapped_column(Integer, nullable=False, default=1, server_default='1', unique=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')", name='platform_enum'),
        CheckConstraint("currency IN ('CNY')", name='currency_enum'),
        CheckConstraint("timezone IN ('Asia/Shanghai')", name='timezone_enum'),
        CheckConstraint('singleton_key = 1', name='single_store'),
    )


class PlatformAccount(Base):
    __tablename__ = 'platform_accounts'
    SCHEMA_NAME = 'PlatformAccount'
    __dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'store_id', 'platform', 'account_name', 'auth_status', 'auth_meta', 'remark')
    __pk_field__ = 'id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    store_id = mapped_column(Uuid(as_uuid=True), ForeignKey('stores.id'), nullable=False, index=True)
    platform = mapped_column(Text, nullable=False)
    account_name = mapped_column(String(100), nullable=False)
    auth_status = mapped_column(Text, nullable=False)
    auth_meta = mapped_column(JSONB, nullable=True)
    remark = mapped_column(String(4000), nullable=True)
    __table_args__ = (
        CheckConstraint('version >= 1', name='version_minimum'),
        CheckConstraint('version <= 2147483647', name='version_maximum'),
        CheckConstraint("platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')", name='platform_enum'),
        CheckConstraint("auth_status IN ('unconfigured', 'placeholder_authorized', 'expired', 'revoked')", name='auth_status_enum'),
    )


class AuthorizationSession(Base):
    __tablename__ = 'authorization_sessions'
    SCHEMA_NAME = 'AuthorizationSession'
    __dto_fields__ = ('authorization_session_id', 'state', 'mode', 'expires_at', 'authorization_url')
    __pk_field__ = 'authorization_session_id'
    __ref_fields__ = {}
    __money_fields__ = ()
    __ratio_fields__ = ()
    __computed_fields__ = ()
    authorization_session_id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    state = mapped_column(String(200), nullable=False)
    mode = mapped_column(Text, nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    authorization_url = mapped_column(String(2048), nullable=True)
    account_id = mapped_column(Uuid(as_uuid=True), ForeignKey('platform_accounts.id'), nullable=False, index=True)
    consumed_at = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("mode IN ('placeholder')", name='mode_enum'),
        UniqueConstraint('state', name='uq_auth_placeholder_state'),
    )

