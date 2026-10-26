from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.exceptions import ApiError
from app.integrations.public_pages.client import check_url_syntax, resolve_public_target
from app.services.catalog import now_iso, owned, parse_time
from app.services.common import Result
from app.services.jobs import accepted, event, submit


def list_competitors(ctx):
    ctx.require_product(ctx.params['product_id'])
    filters = {'product_id': ctx.params['product_id']}
    if 'status' in ctx.query:
        filters['status'] = ctx.query['status']
    return ctx.collection('Competitor', filters)


def _validate_image(ctx, identifier):
    if not identifier:
        return
    row = owned(ctx, 'FileObject', identifier)
    if row['storage_status'] != 'available' or not row['content_type'].startswith('image/') or row['purpose'] not in {'reference', 'product_image', 'media'}:
        raise ApiError(422, 'FILE_VALIDATION_FAILED', '竞品参考图必须是同商品已验证可用的图片文件')


def create_competitor(ctx):
    ctx.require_product(ctx.params['product_id'], lock=True)
    _validate_image(ctx, ctx.body.get('main_image_file_id'))
    if ctx.body.get('url'):
        check_url_syntax(ctx.body['url'])
    return ctx.repo.create('Competitor', {**ctx.body, 'product_id': ctx.params['product_id'], 'status': ctx.body.get('status', 'active')})


def patch_competitor(ctx):
    ctx.require_product(ctx.params['product_id'], lock=True)
    row = owned(ctx, 'Competitor', ctx.params['competitor_id'], lock=True)
    ctx.check_version(row)
    if 'main_image_file_id' in ctx.body:
        _validate_image(ctx, ctx.body['main_image_file_id'])
    if ctx.body.get('url'):
        check_url_syntax(ctx.body['url'])
    updated = ctx.repo.update('Competitor', row['id'], ctx.body)
    if updated['status'] == 'archived' or not updated.get('url'):
        for monitor in ctx.repo.list('CompetitorMonitor', {'competitor_id': row['id']}):
            if monitor['monitor_status'] == 'active':
                ctx.repo.update('CompetitorMonitor', monitor['id'], {'monitor_status': 'paused', 'next_run_at': None, 'last_error': '竞品已归档或移除公开链接，监控已暂停。'})
    return updated


def create_parse_task(ctx):
    product = ctx.require_product(ctx.params['product_id'], lock=True)
    if product['status'] == 'inactive':
        raise ApiError(422, 'PRODUCT_NOT_READY', '停用商品不能创建新的公开链接解析任务')
    check_url_syntax(ctx.body['source_url'])
    if ctx.body.get('competitor_id'):
        owned(ctx, 'Competitor', ctx.body['competitor_id'])
    # dispatch=False preserves the documented create -> run separation.
    return submit(ctx, 'public_link_parse', ctx.body, dispatch=False)['job']


def list_parse_tasks(ctx):
    ctx.require_product(ctx.params['product_id'])
    filters = {'product_id': ctx.params['product_id'], 'job_kind': 'public_link_parse'}
    if ctx.query.get('status'):
        filters['job_status'] = ctx.query['status']
    return ctx.collection('GenerationJob', filters)


def get_parse_task(ctx):
    ctx.require_product(ctx.params['product_id'])
    job = owned(ctx, 'GenerationJob', ctx.params['task_id'])
    if job['job_kind'] != 'public_link_parse':
        raise ApiError(404, 'NOT_FOUND', '链接解析任务不存在')
    return job


def run_parse_task(ctx):
    product = ctx.require_product(ctx.params['product_id'], lock=True)
    if product['status'] == 'inactive':
        raise ApiError(422, 'PRODUCT_NOT_READY', '停用商品不能运行新的公开链接解析任务')
    get_parse_task(ctx)
    job = ctx.get('GenerationJob', ctx.params['task_id'], lock=True)
    ctx.check_version(job)
    if job['dispatch_status'] != 'awaiting_dispatch':
        raise ApiError(409, 'TASK_ALREADY_DISPATCHED', '该解析任务已经进入队列')
    if job['job_status'] != 'pending':
        raise ApiError(409, 'JOB_TERMINAL', '只有待运行解析任务可以入队')
    job = ctx.repo.update('GenerationJob', job['id'], {'dispatch_status': 'queued', 'queued_at': now_iso(), 'deadline_at': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat().replace('+00:00', 'Z')})
    event(ctx, job, 'enqueued', '用户确认运行公开链接解析')
    return Result(accepted(job), status=202)


def get_parse_result(ctx):
    job = get_parse_task(ctx)
    if job['job_status'] != 'succeeded':
        raise ApiError(409, 'JOB_NOT_SUCCEEDED', '解析任务尚未成功完成')
    rows = ctx.repo.list('ParseResult', {'job_id': job['id']})
    if not rows:
        raise ApiError(409, 'JOB_NOT_SUCCEEDED', '解析结果尚未完成持久化')
    return rows[0]


def _competitor(ctx, lock=False):
    ctx.require_product(ctx.params['product_id'], lock=lock)
    return owned(ctx, 'Competitor', ctx.params['competitor_id'], lock=lock)


def _monitor(ctx, lock=False):
    competitor = _competitor(ctx, lock=lock)
    rows = ctx.repo.list('CompetitorMonitor', {'competitor_id': competitor['id']})
    if not rows:
        raise ApiError(404, 'NOT_FOUND', '该竞品尚未创建监控')
    return ctx.get('CompetitorMonitor', rows[0]['id'], lock=lock)


def _monitor_supported(competitor):
    if competitor['status'] != 'active' or not competitor.get('url'):
        raise ApiError(422, 'UNSUPPORTED_PUBLIC_URL', '监控需要启用竞品及可公开访问的链接')
    resolve_public_target(competitor['url'])


def create_monitor(ctx):
    competitor = _competitor(ctx, lock=True)
    _monitor_supported(competitor)
    if ctx.repo.count('CompetitorMonitor', {'competitor_id': competitor['id']}):
        raise ApiError(409, 'BUSINESS_CONFLICT', '同一竞品最多创建一个监控')
    status = ctx.body.get('monitor_status', 'active')
    return ctx.repo.create('CompetitorMonitor', {**ctx.body, 'competitor_id': competitor['id'], 'monitor_status': status, 'next_run_at': now_iso() if status == 'active' else None})


def get_monitor(ctx):
    return _monitor(ctx)


def patch_monitor(ctx):
    competitor = _competitor(ctx, lock=True)
    monitor = _monitor(ctx, lock=True)
    ctx.check_version(monitor)
    merged = {**monitor, **ctx.body}
    if merged['monitor_status'] == 'active':
        _monitor_supported(competitor)
    changes = dict(ctx.body)
    changes['next_run_at'] = (datetime.now(timezone.utc) + timedelta(minutes=merged['interval_minutes'])).isoformat().replace('+00:00', 'Z') if merged['monitor_status'] == 'active' else None
    if merged['monitor_status'] == 'active':
        changes['last_error'] = None
    return ctx.repo.update('CompetitorMonitor', monitor['id'], changes)


def list_snapshots(ctx):
    monitor = _monitor(ctx)
    rows = ctx.repo.list('MonitorSnapshot', {'monitor_id': monitor['id']}, order='-captured_at')
    return ctx.page(rows)


def process_due_monitors(ctx):
    """Create at most one child task per monitor/scheduled instant, in one transaction."""
    count = 0
    now = datetime.now(timezone.utc)
    for candidate in ctx.repo.list('CompetitorMonitor', {'monitor_status': 'active'}, limit=1000, order='next_run_at'):
        if not candidate.get('next_run_at') or parse_time(candidate['next_run_at']) > now:
            continue
        competitor = ctx.get('Competitor', candidate['competitor_id'])
        product = ctx.require_product(competitor['product_id'], lock=True)
        monitor = ctx.get('CompetitorMonitor', candidate['id'], lock=True)
        if monitor['monitor_status'] != 'active' or not monitor.get('next_run_at') or parse_time(monitor['next_run_at']) > now:
            continue
        scheduled_at = monitor['next_run_at']
        next_at = (now + timedelta(minutes=monitor['interval_minutes'])).isoformat().replace('+00:00', 'Z')
        if competitor['status'] != 'active' or not competitor.get('url') or product['status'] == 'inactive':
            ctx.repo.update('CompetitorMonitor', monitor['id'], {'next_run_at': next_at, 'last_error': '商品或竞品未启用，或没有公开链接，本次监控已跳过。'})
            continue
        if ctx.repo.count('MonitorDispatch', {'monitor_id': monitor['id'], 'scheduled_at': scheduled_at}):
            ctx.repo.update('CompetitorMonitor', monitor['id'], {'next_run_at': next_at})
            continue
        child_ctx = replace(ctx, params={'product_id': product['id']})
        body = {'source_url': competitor['url'], 'competitor_id': competitor['id'], 'monitor_id': monitor['id'], 'scheduled_at': scheduled_at}
        job = submit(child_ctx, 'public_link_parse', body)['job']
        ctx.repo.create('MonitorDispatch', {'monitor_id': monitor['id'], 'scheduled_at': scheduled_at, 'job_id': job['id']})
        ctx.repo.update('CompetitorMonitor', monitor['id'], {'next_run_at': next_at, 'last_error': None})
        count += 1
    return count
