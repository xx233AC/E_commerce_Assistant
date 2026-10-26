from datetime import date, datetime, timedelta, timezone

from app.core.exceptions import ApiError
from app.rules.metrics import calculate_metrics, summarize
from app.services.catalog import now_iso, owned, parse_time, read_round

SHOP_TZ = timezone(timedelta(hours=8))


def _validate_date_and_experiment(ctx, body, product_id):
    record_day = date.fromisoformat(body['record_date'])
    today = datetime.now(SHOP_TZ).date()
    if record_day > today:
        raise ApiError(422, 'FUTURE_PERFORMANCE_DATE', '经营数据不能记录未来自然日')
    if body['granularity'] == 'product_day':
        if body.get('experiment_id') is not None:
            raise ApiError(422, 'METRIC_GRAIN_MISMATCH', '商品日汇总不能关联实验')
        return {'experiment_id': None, 'creative_plan': None, 'generated_asset': None, 'promotion_link_id': None}
    if not body.get('experiment_id'):
        raise ApiError(422, 'EXPERIMENT_REQUIRED', '实验日数据必须关联实验')
    experiment = owned(ctx, 'AdExperiment', body['experiment_id'], product_id)
    if experiment['round_id'] != body['round_id']:
        raise ApiError(404, 'NOT_FOUND', '实验不属于当前轮次')
    if experiment['experiment_status'] not in {'running', 'finished', 'cancelled'} or not experiment.get('actual_start_at'):
        raise ApiError(409, 'EXPERIMENT_NOT_STARTED', '只能录入实际已经启动的实验数据')
    start = parse_time(experiment['actual_start_at']).astimezone(SHOP_TZ).date()
    end = parse_time(experiment['actual_end_at']).astimezone(SHOP_TZ).date() if experiment.get('actual_end_at') else today
    if not start <= record_day <= end:
        raise ApiError(422, 'PERFORMANCE_DATE_OUTSIDE_EXPERIMENT', '经营日期须在实验实际执行的店铺自然日范围内')
    asset = owned(ctx, 'Asset', experiment['related_asset']['id'], product_id)
    plan = {'id': asset['creative_plan_id'], 'version': asset['creative_plan_version']} if asset.get('creative_plan_id') else None
    return {'experiment_id': experiment['id'], 'creative_plan': plan, 'generated_asset': experiment['related_asset'], 'promotion_link_id': experiment['related_link_id']}


def preserve_revision(ctx, record):
    if not ctx.repo.count('PerformanceRevision', {'record_id': record['id'], 'version': record['version']}):
        ctx.repo.create('PerformanceRevision', {'record_id': record['id'], 'version': record['version'], 'resource': record, 'created_by': ctx.user['id'] if ctx.user else None, 'created_at': now_iso()})


def create_record(ctx, payload=None, *, source='manual', import_id=None):
    body = dict(payload if payload is not None else ctx.body)
    product_id = ctx.params['product_id']
    ctx.require_product(product_id, lock=True)
    ctx.require_round(product_id, body['round_id'])
    refs = _validate_date_and_experiment(ctx, body, product_id)
    filters = {'granularity': body['granularity'], 'record_date': body['record_date'], 'voided': False}
    filters['product_id' if body['granularity'] == 'product_day' else 'experiment_id'] = product_id if body['granularity'] == 'product_day' else body['experiment_id']
    if ctx.repo.count('PerformanceRecord', filters):
        raise ApiError(409, 'DUPLICATE_PERFORMANCE_RECORD', '同商品或同实验的该自然日已有有效记录，不能跨轮次重复录入')
    row = ctx.repo.create('PerformanceRecord', {**body, **refs, **calculate_metrics(body), 'product_id': product_id, 'source': source, 'import_id': import_id, 'voided': False})
    preserve_revision(ctx, row)
    return row


def create_performance(ctx):
    return create_record(ctx)


def _filter_records(ctx, query, *, summary=False):
    product_id = ctx.params['product_id']
    ctx.require_product(product_id)
    if query.get('round_id'):
        read_round(ctx, query['round_id'])
    if query.get('experiment_id'):
        experiment = owned(ctx, 'AdExperiment', query['experiment_id'])
        if query.get('round_id') and experiment['round_id'] != query['round_id']:
            raise ApiError(404, 'NOT_FOUND', '实验不属于当前轮次')
        if query.get('granularity') == 'product_day':
            raise ApiError(422, 'METRIC_GRAIN_MISMATCH', '商品日汇总不能筛选实验')
    start, end = query.get('start_date'), query.get('end_date')
    if start and end and start > end:
        raise ApiError(422, 'DATE_RANGE_INVALID', '开始日期不能晚于结束日期')
    filters = {'product_id': product_id, **{k: query[k] for k in ('round_id', 'granularity', 'experiment_id') if k in query}}
    if summary or not query.get('include_voided'):
        filters['voided'] = False
    return [r for r in ctx.repo.list('PerformanceRecord', filters) if (not start or r['record_date'] >= start) and (not end or r['record_date'] <= end)]


def list_performance(ctx):
    return ctx.page(_filter_records(ctx, ctx.query))


def get_performance(ctx):
    ctx.require_product(ctx.params['product_id'])
    return owned(ctx, 'PerformanceRecord', ctx.params['record_id'])


def _writable_record(ctx):
    ctx.require_product(ctx.params['product_id'], lock=True)
    row = owned(ctx, 'PerformanceRecord', ctx.params['record_id'], lock=True)
    ctx.require_round(row['product_id'], row['round_id'])
    ctx.check_version(row)
    if row['voided']:
        raise ApiError(409, 'PERFORMANCE_VOIDED', '已作废记录不能修改或恢复')
    return row


def patch_performance(ctx):
    row = _writable_record(ctx)
    merged = {**row, **ctx.body}
    preserve_revision(ctx, row)
    updated = ctx.repo.update('PerformanceRecord', row['id'], {**ctx.body, **calculate_metrics(merged)})
    preserve_revision(ctx, updated)
    return updated


def void_performance(ctx):
    row = _writable_record(ctx)
    if not ctx.body['reason'].strip():
        raise ApiError(422, 'VOID_REASON_REQUIRED', '必须填写作废原因')
    preserve_revision(ctx, row)
    updated = ctx.repo.update('PerformanceRecord', row['id'], {'voided': True, 'void_reason': ctx.body['reason']})
    preserve_revision(ctx, updated)
    return updated


def summary(ctx):
    rows = _filter_records(ctx, ctx.query, summary=True)
    if len(rows) > 10000:
        raise ApiError(422, 'TOO_MANY_RECORDS', '一次汇总最多一万条记录，请缩小日期范围')
    totals, warnings = summarize(rows)
    if not rows:
        warnings.append('所选范围没有有效经营数据。')
    return {'round_id': ctx.query['round_id'], 'granularity': ctx.query['granularity'], 'experiment_id': ctx.query.get('experiment_id'), 'start_date': ctx.query['start_date'], 'end_date': ctx.query['end_date'], 'totals': totals, 'record_ids': [r['id'] for r in rows], 'warnings': warnings}
