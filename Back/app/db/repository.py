"""Small typed-table repository. It flushes; the caller owns commit/rollback."""
from __future__ import annotations

import copy
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Numeric, Uuid, func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import MODELS

SINGLETON_ID = UUID('00000000-0000-0000-0000-000000000001')
IMMUTABLE = {'ResourceRevision', 'RoundSnapshot', 'PerformanceRevision', 'JobOutput'}


def json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


class Repo:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def model(kind: str):
        try:
            return MODELS[kind]
        except KeyError:
            raise ValueError(f'Unknown repository kind: {kind}') from None

    @staticmethod
    def _cast(column, value):
        if value is None:
            return None
        if isinstance(column.type, Uuid):
            if value == 'singleton':
                return SINGLETON_ID
            return value if isinstance(value, UUID) else UUID(str(value))
        if isinstance(column.type, DateTime):
            if isinstance(value, str):
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if value.tzinfo is None:
                raise ValueError(f'{column.key} requires a timezone-aware datetime')
            return value.astimezone(timezone.utc)
        if isinstance(column.type, Date):
            return date.fromisoformat(value) if isinstance(value, str) else value
        if isinstance(column.type, Numeric):
            return value if isinstance(value, Decimal) else Decimal(str(value))
        return json_value(copy.deepcopy(value)) if isinstance(value, (dict, list)) else value

    def _values(self, model, data):
        data = copy.deepcopy(data)
        for field in getattr(model, '__computed_fields__', ()):
            data.pop(field, None)
        for field, (id_col, ver_col) in getattr(model, '__ref_fields__', {}).items():
            if field not in data:
                continue
            ref = data.pop(field)
            data[id_col] = None if ref is None else ref['id']
            data[ver_col] = None if ref is None else ref['version']
        columns = model.__table__.columns
        invalid = set(data) - set(columns.keys())
        if invalid:
            raise ValueError(f'{model.SCHEMA_NAME}: unknown storage fields {sorted(invalid)}')
        return {key: self._cast(columns[key], value) for key, value in data.items()}

    def _select(self, kind, filters=None):
        model = self.model(kind)
        statement = select(model)
        for key, value in (filters or {}).items():
            if key not in model.__table__.columns:
                raise ValueError(f'{kind}: unknown filter field {key}')
            column = model.__table__.columns[key]
            if isinstance(value, (list, tuple, set)):
                statement = statement.where(column.in_([self._cast(column, v) for v in value]))
            elif value is None:
                statement = statement.where(column.is_(None))
            else:
                statement = statement.where(column == self._cast(column, value))
        return statement

    def serialize(self, instance) -> dict:
        model = type(instance)
        refs = getattr(model, '__ref_fields__', {})
        computed = set(getattr(model, '__computed_fields__', ()))
        result = {}
        for field in model.__dto_fields__:
            if field in computed:
                continue
            if field in refs:
                id_col, ver_col = refs[field]
                value = None if getattr(instance, id_col) is None else {'id': str(getattr(instance, id_col)), 'version': getattr(instance, ver_col)}
            else:
                value = getattr(instance, field)
                if value is not None and field in getattr(model, '__money_fields__', ()):
                    value = format(value, '.2f')
                elif value is not None and field in getattr(model, '__ratio_fields__', ()):
                    value = format(value, '.6f').rstrip('0').rstrip('.') or '0'
            result[field] = json_value(value)
        if model.SCHEMA_NAME == 'Inventory':
            result['available_qty'] = instance.stock_qty - instance.locked_qty
            result['is_low_stock'] = result['available_qty'] <= instance.warning_threshold
        elif model.SCHEMA_NAME == 'Store':
            product, sku, inventory = (MODELS[k] for k in ('Product', 'Sku', 'Inventory'))
            result['product_count'] = self.db.scalar(select(func.count()).select_from(product).where(product.store_id == instance.id)) or 0
            result['low_stock_sku_count'] = self.db.scalar(select(func.count()).select_from(inventory).join(sku, sku.id == inventory.sku_id).join(product, product.id == sku.product_id).where(product.store_id == instance.id, sku.status == 'active', inventory.stock_qty - inventory.locked_qty <= inventory.warning_threshold)) or 0
        elif model.SCHEMA_NAME == 'ModelConfig':
            result['secret_configured'] = bool(instance.secret_env_name and os.environ.get(instance.secret_env_name))
        return result

    def get(self, kind: str, id, lock: bool = False) -> dict | None:
        model = self.model(kind)
        statement = self._select(kind, {model.__pk_field__: id})
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        item = self.db.scalar(statement)
        return None if item is None else self.serialize(item)

    def create(self, kind: str, data: dict) -> dict:
        model = self.model(kind)
        values = self._values(model, data)
        if kind in ('SystemSettings', 'QueueSettings'):
            values.setdefault('id', SINGLETON_ID)
        item = model(**values)
        self.db.add(item)
        self.db.flush()
        return self.serialize(item)

    def update(self, kind: str, id, changes: dict, bump: bool = True) -> dict:
        if kind in IMMUTABLE:
            raise ValueError(f'{kind} is immutable; create a new revision instead')
        model = self.model(kind)
        item = self.db.scalar(self._select(kind, {model.__pk_field__: id}).with_for_update().execution_options(populate_existing=True))
        if item is None:
            raise LookupError(f'{kind} not found')
        values = self._values(model, changes)
        if model.__pk_field__ in values:
            raise ValueError('A primary key cannot be changed')
        for key, value in values.items():
            setattr(item, key, value)
        if bump and 'version' in model.__table__.columns:
            item.version += 1
        if 'updated_at' in model.__table__.columns:
            item.updated_at = utcnow()
        self.db.flush()
        return self.serialize(item)

    def list(self, kind: str, filters: dict | None = None, limit: int | None = None, offset: int = 0, order=None) -> list[dict]:
        model = self.model(kind)
        statement = self._select(kind, filters)
        if order is None:
            if 'updated_at' in model.__table__.columns:
                order = '-updated_at'
            elif 'created_at' in model.__table__.columns:
                order = '-created_at'
            else:
                order = '-' + model.__pk_field__
        orders = [order] if isinstance(order, str) else order
        for field in orders:
            if not isinstance(field, str):
                statement = statement.order_by(field)
                continue
            descending = field.startswith('-')
            name = field.lstrip('+-')
            if name not in model.__table__.columns:
                raise ValueError(f'{kind}: unknown order field {name}')
            column = model.__table__.columns[name]
            statement = statement.order_by(column.desc() if descending else column.asc())
        statement = statement.order_by(getattr(model, model.__pk_field__).desc())
        if limit is not None:
            statement = statement.limit(limit)
        statement = statement.offset(offset)
        return [self.serialize(item) for item in self.db.scalars(statement)]

    def count(self, kind: str, filters: dict | None = None) -> int:
        return self.db.scalar(select(func.count()).select_from(self._select(kind, filters).subquery())) or 0

    def delete(self, kind: str, id) -> None:
        """Internal maintenance only. Public business API never hard-deletes."""
        model = self.model(kind)
        item = self.db.scalar(self._select(kind, {model.__pk_field__: id}).with_for_update())
        if item is not None:
            self.db.delete(item)
            self.db.flush()
