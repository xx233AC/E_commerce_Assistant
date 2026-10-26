from app.core.exceptions import ApiError
from app.rules.inventory_advice import advice_item, inventory_values
from app.services.catalog import now_iso, owned, parse_time
from app.services.common import Result


def list_skus(ctx):
    ctx.require_product(ctx.params['product_id'])
    filters = {'product_id': ctx.params['product_id']}
    if 'status' in ctx.query:
        filters['status'] = ctx.query['status']
    return ctx.collection('Sku', filters)


def _unique_code(ctx, code, identifier=None):
    if any(r['id'] != identifier for r in ctx.repo.list('Sku', {'sku_code': code})):
        raise ApiError(409, 'DUPLICATE_SKU_CODE', 'SKU 编号在本店铺中已存在')


def create_sku(ctx):
    ctx.require_product(ctx.params['product_id'], lock=True)
    _unique_code(ctx, ctx.body['sku_code'])
    row = ctx.repo.create('Sku', {**ctx.body, 'product_id': ctx.params['product_id'], 'status': ctx.body.get('status', 'active')})
    ctx.repo.create('Inventory', {'sku_id': row['id'], **inventory_values(0, 0)})
    return row


def patch_sku(ctx):
    product = ctx.require_product(ctx.params['product_id'], lock=True)
    row = owned(ctx, 'Sku', ctx.params['sku_id'], lock=True)
    ctx.check_version(row)
    _unique_code(ctx, ctx.body.get('sku_code', row['sku_code']), row['id'])
    if product['status'] == 'active' and row['status'] == 'active' and ctx.body.get('status') == 'inactive' and ctx.repo.count('Sku', {'product_id': product['id'], 'status': 'active'}) <= 1:
        raise ApiError(409, 'LAST_ACTIVE_SKU', '启用商品至少需要一个启用 SKU，请先停用商品')
    return ctx.repo.update('Sku', row['id'], ctx.body)


def inventory_row(ctx, lock=False):
    ctx.require_product(ctx.params['product_id'], lock=lock)
    sku = owned(ctx, 'Sku', ctx.params['sku_id'])
    rows = ctx.repo.list('Inventory', {'sku_id': sku['id']})
    if not rows:
        raise ApiError(404, 'NOT_FOUND', 'SKU 库存记录不存在')
    return ctx.get('Inventory', rows[0]['id'], lock=lock)


def get_inventory(ctx):
    return inventory_row(ctx)


def patch_inventory(ctx):
    row = inventory_row(ctx, lock=True)
    ctx.check_version(row)
    threshold = ctx.body.get('warning_threshold', row['warning_threshold'])
    return ctx.repo.update('Inventory', row['id'], {**ctx.body, **inventory_values(row['stock_qty'], threshold)})


def adjust_inventory(ctx):
    row = inventory_row(ctx, lock=True)
    ctx.check_version(row)
    delta = ctx.body['change_qty']
    after = row['stock_qty'] + delta
    if not delta or not 0 <= after <= 2147483647:
        raise ApiError(409, 'INSUFFICIENT_STOCK' if after < 0 else 'STOCK_OUT_OF_RANGE', '调整后库存必须在 0 至 2147483647 之间，调整量不能为零')
    updated = ctx.repo.update('Inventory', row['id'], inventory_values(after, row['warning_threshold']))
    movement = ctx.repo.create('InventoryMovement', {'sku_id': row['sku_id'], **ctx.body, 'movement_type': 'increase' if delta > 0 else 'decrease', 'before_qty': row['stock_qty'], 'after_qty': after, 'operator_id': ctx.user['id'], 'inventory_version': updated['version']})
    return Result(movement, status=201, headers={'ETag': f'"{updated["version"]}"'})


def list_movements(ctx):
    ctx.require_product(ctx.params['product_id'])
    skus = {r['id'] for r in ctx.repo.list('Sku', {'product_id': ctx.params['product_id']})}
    if ctx.query.get('sku_id'):
        owned(ctx, 'Sku', ctx.query['sku_id'])
        skus = {ctx.query['sku_id']}
    start, end = ctx.query.get('start_at'), ctx.query.get('end_at')
    if start and end and parse_time(start) > parse_time(end):
        raise ApiError(422, 'DATE_RANGE_INVALID', '开始时间不能晚于结束时间')
    rows = [r for r in ctx.repo.list('InventoryMovement') if r['sku_id'] in skus and (not start or parse_time(r['created_at']) >= parse_time(start)) and (not end or parse_time(r['created_at']) <= parse_time(end))]
    return ctx.page(rows)


def store_inventory_rows(ctx):
    store = ctx.get('Store', ctx.params['store_id'])
    products = {r['id'] for r in ctx.repo.list('Product', {'store_id': store['id']})}
    if ctx.query.get('product_id'):
        if ctx.query['product_id'] not in products:
            raise ApiError(404, 'NOT_FOUND', '商品不存在')
        products = {ctx.query['product_id']}
    skus = {r['id'] for r in ctx.repo.list('Sku') if r['product_id'] in products}
    return [r for r in ctx.repo.list('Inventory') if r['sku_id'] in skus and (not ctx.query.get('low_stock_only') or r['is_low_stock'])]


def list_store_inventory(ctx):
    return ctx.page(store_inventory_rows(ctx))


def generate_advice(ctx):
    rows = store_inventory_rows(ctx)
    if len(rows) > 10000:
        raise ApiError(422, 'TOO_MANY_SKUS', '本次库存建议最多支持一万个 SKU')
    return {'items': [advice_item(r, ctx.body.get('horizon_days', 7)) for r in rows], 'generated_at': now_iso(), 'basis': 'threshold_rule'}
