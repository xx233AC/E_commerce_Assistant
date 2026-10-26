"""单店铺、商品与平台元数据；所有写入由请求适配层统一提交事务。"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import text

from app.core.exceptions import ApiError


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_time(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))


def owned(ctx, kind, identifier, product_id=None, lock=False):
    row = ctx.get(kind, identifier, lock=lock)
    product_id = product_id or ctx.params.get('product_id')
    if row.get('product_id') != product_id:
        raise ApiError(404, 'NOT_FOUND', '资源不存在')
    return row


def read_round(ctx, round_id, product_id=None):
    return owned(ctx, 'OperatingRound', round_id, product_id)


def store_view(ctx, row):
    # Repository按真实商品和启用SKU实时聚合，不在店铺表缓存计数。
    return row


def list_stores(ctx):
    return ctx.page([store_view(ctx, r) for r in ctx.repo.list('Store')])


def create_store(ctx):
    ctx.db.execute(text('SELECT pg_advisory_xact_lock(777001)'))
    if ctx.repo.count('Store'):
        raise ApiError(409, 'STORE_ALREADY_EXISTS', '本系统只允许一个店铺')
    return ctx.repo.create('Store', {**ctx.body, 'currency': 'CNY', 'timezone': 'Asia/Shanghai', 'product_count': 0, 'low_stock_sku_count': 0})


def get_store(ctx):
    return store_view(ctx, ctx.get('Store', ctx.params['store_id']))


def patch_store(ctx):
    row = ctx.get('Store', ctx.params['store_id'], lock=True)
    ctx.check_version(row)
    if ctx.body.get('platform', row['platform']) != row['platform'] and (
        ctx.repo.count('Product', {'store_id': row['id']}) or ctx.repo.count('PlatformAccount', {'store_id': row['id']})):
        raise ApiError(409, 'STORE_PLATFORM_LOCKED', '已有商品或平台账号后不能改变店铺平台')
    return store_view(ctx, ctx.repo.update('Store', row['id'], ctx.body))


def list_accounts(ctx):
    ctx.get('Store', ctx.params['store_id'])
    return ctx.collection('PlatformAccount', {'store_id': ctx.params['store_id']})


def create_account(ctx):
    store = ctx.get('Store', ctx.params['store_id'], lock=True)
    if ctx.body['platform'] != store['platform']:
        raise ApiError(422, 'PLATFORM_MISMATCH', '平台账号必须与店铺平台一致')
    return ctx.repo.create('PlatformAccount', {**ctx.body, 'store_id': store['id'], 'auth_status': 'unconfigured'})


def _account(ctx):
    ctx.get('Store', ctx.params['store_id'])
    row = ctx.get('PlatformAccount', ctx.params['account_id'], lock=True)
    if row['store_id'] != ctx.params['store_id']:
        raise ApiError(404, 'NOT_FOUND', '平台账号不存在')
    return row


def start_authorization(ctx):
    account = _account(ctx)
    token = secrets.token_urlsafe(40)
    identifier = str(uuid4())
    expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat().replace('+00:00', 'Z')
    ctx.repo.create('AuthorizationState', {'id': identifier, 'account_id': account['id'], 'user_id': ctx.user['id'],
        'login_session_id': ctx.session_id, 'state_hash': hashlib.sha256(token.encode()).hexdigest(), 'expires_at': expires, 'used_at': None})
    return {'authorization_session_id': identifier, 'state': token, 'mode': 'placeholder', 'expires_at': expires, 'authorization_url': None}


def callback_authorization(ctx):
    account = _account(ctx)
    row = ctx.get('AuthorizationState', ctx.body['authorization_session_id'], lock=True)
    matches = row['account_id'] == account['id'] and row['user_id'] == ctx.user['id'] and str(row['login_session_id']) == str(ctx.session_id)
    if not matches or row.get('used_at') or parse_time(row['expires_at']) <= datetime.now(timezone.utc) or not hmac.compare_digest(row['state_hash'], hashlib.sha256(ctx.body['state'].encode()).hexdigest()):
        raise ApiError(422, 'AUTHORIZATION_STATE_INVALID', '授权占位会话不匹配、已过期或已使用')
    ctx.repo.update('AuthorizationState', row['id'], {'used_at': now_iso()}, bump=False)
    changes = {'auth_meta': ctx.body['auth_meta'], 'auth_status': 'placeholder_authorized'}
    if 'remark' in ctx.body:
        changes['remark'] = ctx.body['remark']
    return ctx.repo.update('PlatformAccount', account['id'], changes)


def list_products(ctx):
    filters = {k: ctx.query[k] for k in ('store_id', 'platform', 'status') if k in ctx.query}
    rows = ctx.repo.list('Product', filters)
    keyword = ctx.query.get('keyword', '').strip().casefold()
    if keyword:
        rows = [r for r in rows if keyword in r['name'].casefold() or keyword in r['category'].casefold()]
    return ctx.page(rows)


def validate_product_images(ctx, product_id, ids):
    if len(ids) != len(set(ids)):
        raise ApiError(422, 'DUPLICATE_FILE', '商品图片不能重复')
    for identifier in ids:
        file = ctx.get('FileObject', identifier)
        if file.get('product_id') != product_id:
            raise ApiError(404, 'NOT_FOUND', '商品图片不存在')
        if file['storage_status'] != 'available' or file['purpose'] != 'product_image' or not file['content_type'].startswith('image/') or file['execution_mode'] != 'real':
            raise ApiError(422, 'PRODUCT_IMAGE_INVALID', '商品原图必须是本商品已验证可用的真实图片')


def require_active_requirements(ctx, product):
    if not product.get('image_file_ids') or not ctx.repo.count('Sku', {'product_id': product['id'], 'status': 'active'}):
        raise ApiError(422, 'PRODUCT_NOT_READY', '启用商品需要至少一个启用 SKU 和一张已验证商品原图')
    validate_product_images(ctx, product['id'], product['image_file_ids'])


def create_product(ctx):
    store = ctx.get('Store', ctx.body['store_id'], lock=True)
    # 新商品尚无 SKU 和专属已上传文件，必须先完成基础档案再启用。
    if ctx.body.get('status') == 'active':
        raise ApiError(422, 'PRODUCT_NOT_READY', '请先建立商品，再添加 SKU 和原图后启用')
    identifier = str(uuid4())
    validate_product_images(ctx, identifier, ctx.body.get('image_file_ids', []))
    return ctx.repo.create('Product', {**ctx.body, 'id': identifier, 'platform': store['platform'], 'status': ctx.body.get('status', 'draft')})


def get_product(ctx):
    return ctx.require_product(ctx.params['product_id'])


def patch_product(ctx):
    row = ctx.require_product(ctx.params['product_id'], lock=True)
    ctx.check_version(row)
    merged = {**row, **ctx.body}
    if 'image_file_ids' in ctx.body:
        validate_product_images(ctx, row['id'], ctx.body['image_file_ids'])
    if merged['status'] == 'active':
        require_active_requirements(ctx, merged)
    return ctx.repo.update('Product', row['id'], ctx.body)


def list_mappings(ctx):
    ctx.require_product(ctx.params['product_id'])
    return ctx.collection('PlatformMapping', {'product_id': ctx.params['product_id']})


def validate_mapping(ctx, product, data, current_id=None):
    if data['platform'] != product['platform']:
        raise ApiError(422, 'PLATFORM_MISMATCH', '平台映射必须与店铺平台一致')
    if bool(data.get('sku_id')) != bool(data.get('platform_sku_id')):
        raise ApiError(422, 'MAPPING_SKU_PAIR_REQUIRED', 'sku_id 与 platform_sku_id 须同时给出或同时为空')
    if data.get('sku_id'):
        owned(ctx, 'Sku', data['sku_id'], product['id'])
    for existing in ctx.repo.list('PlatformMapping', {'platform': data['platform']}):
        if existing['id'] == current_id:
            continue
        if data.get('platform_sku_id') and existing.get('platform_sku_id') == data['platform_sku_id']:
            raise ApiError(409, 'DUPLICATE_PLATFORM_MAPPING', '该平台外部 SKU 已存在映射')
        if not data.get('sku_id') and not existing.get('sku_id') and existing['platform_product_id'] == data['platform_product_id']:
            raise ApiError(409, 'DUPLICATE_PLATFORM_MAPPING', '该平台商品已存在商品级映射')


def create_mapping(ctx):
    product = ctx.require_product(ctx.params['product_id'], lock=True)
    validate_mapping(ctx, product, ctx.body)
    return ctx.repo.create('PlatformMapping', {**ctx.body, 'product_id': product['id'], 'mapping_status': ctx.body.get('mapping_status', 'active')})


def patch_mapping(ctx):
    product = ctx.require_product(ctx.params['product_id'], lock=True)
    row = owned(ctx, 'PlatformMapping', ctx.params['mapping_id'], lock=True)
    ctx.check_version(row)
    validate_mapping(ctx, product, {**row, **ctx.body}, row['id'])
    return ctx.repo.update('PlatformMapping', row['id'], ctx.body)
