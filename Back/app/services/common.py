from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4
import math
import re

from app.core.exceptions import ApiError
from app.core.security import utcnow
from app.db.repository import Repo


@dataclass
class Page:
    items: list
    total: int
    page: int = 1
    page_size: int = 20


@dataclass
class Result:
    data: Any
    status: int = 200
    headers: dict = field(default_factory=dict)


@dataclass
class RawResult:
    body: Any
    media_type: str
    status: int = 200
    headers: dict = field(default_factory=dict)


@dataclass
class Context:
    db: Any
    user: dict
    params: dict = field(default_factory=dict)
    query: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)
    headers: Any = field(default_factory=dict)
    request_id: str = ''
    session_id: str | None = None
    request_method: str = 'GET'
    client_ip: str = ''
    base_url: str = 'http://127.0.0.1:5173'
    upload: Any = None
    file_hash: str | None = None

    @property
    def repo(self):
        return Repo(self.db)

    def get(self, kind, id, lock=False):
        row = self.repo.get(kind, str(id), lock=lock)
        if row is None:
            raise ApiError(404, 'NOT_FOUND', '资源不存在或不属于当前业务范围')
        return row

    def check_version(self, row):
        value = self.headers.get('if-match') or self.headers.get('If-Match')
        if value is None:
            raise ApiError(428, 'PRECONDITION_REQUIRED', '请携带当前资源版本')
        if not re.fullmatch(r'"[1-9][0-9]*"', value):
            raise ApiError(400, 'INVALID_IF_MATCH', 'If-Match 必须为带双引号的正整数')
        if int(value[1:-1]) != row['version']:
            raise ApiError(412, 'VERSION_CONFLICT', '资源已更新，请刷新后再提交')

    def page(self, items):
        number = int(self.query.get('page', 1))
        size = int(self.query.get('page_size', 20))
        return Page(items[(number-1)*size:number*size], len(items), number, size)

    def collection(self, kind, filters=None):
        number = int(self.query.get('page', 1))
        size = int(self.query.get('page_size', 20))
        return Page(self.repo.list(kind, filters, limit=size, offset=(number-1)*size), self.repo.count(kind, filters), number, size)

    def require_product(self, product_id, active=False, lock=False):
        product = self.get('Product', product_id, lock=lock)
        if active and product['status'] != 'active':
            raise ApiError(422, 'PRODUCT_NOT_READY', '请先补齐原图和SKU并启用商品')
        return product

    def require_round(self, product_id, round_id, lock=True):
        self.require_product(product_id, lock=lock)
        row = self.get('OperatingRound', round_id, lock=lock)
        if row['product_id'] != str(product_id):
            raise ApiError(404, 'NOT_FOUND', '轮次不属于此商品')
        if row['status'] != 'active':
            raise ApiError(409, 'ROUND_READ_ONLY', '已完成或取消的轮次只读')
        return row

    def save_revision(self, kind, row, reason=None):
        types = {'Diagnosis':'diagnosis', 'CreativePlan':'creative_plan', 'AdRecommendation':'ad_recommendation', 'ReviewReport':'review_report'}
        existing = self.repo.list('ResourceRevision', {'resource_type': types[kind], 'resource_id': row['id'], 'version':row['version']})
        if existing:
            return existing[0]
        return self.repo.create('ResourceRevision', {
            'revision_id': str(uuid4()), 'resource_type':types[kind], 'resource_id':row['id'],
            'version':row['version'], 'created_at':utcnow().isoformat().replace('+00:00','Z'),
            'created_by':self.user.get('id'), 'change_reason':reason, 'resource':row,
            'product_id':row['product_id'], 'round_id':row['round_id'],
        })

    def resolve_ref(self, kind, ref, product_id, round_id=None):
        types = {'Diagnosis':'diagnosis','CreativePlan':'creative_plan','AdRecommendation':'ad_recommendation','ReviewReport':'review_report'}
        if kind in types:
            rows = self.repo.list('ResourceRevision', {'resource_type':types[kind], 'resource_id':ref['id'], 'version':ref['version']})
            row = rows[0]['resource'] if rows else None
        else:
            row = self.repo.get(kind, ref['id'])
            if row and row.get('version') != ref['version']:
                row = None
        if not row or row.get('product_id') != str(product_id) or (round_id and row.get('round_id') != str(round_id)):
            raise ApiError(422, 'INVALID_RESOURCE_REFERENCE', '引用不存在、版本不符或不属于当前商品轮次')
        return row
