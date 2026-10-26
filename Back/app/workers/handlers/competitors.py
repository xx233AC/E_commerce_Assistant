from uuid import uuid4

from app.core.contract import validate_schema
from app.core.exceptions import ApiError
from app.integrations.public_pages.client import fetch_public_html
from app.integrations.public_pages.parser import parse_metadata
from app.services.catalog import owned


def execute_parse(input):
    page = fetch_public_html(input['source_url'])
    result = parse_metadata(input['source_url'], page.text, final_url=page.url)
    validate_schema('ParseResult', result)
    return result


def publish_parse(ctx, job, input, result):
    """Caller holds the job lease/cancellation lock and commits all output atomically."""
    validate_schema('ParseResult', result)
    if result['source_url'] != input['source_url']:
        raise ApiError(409, 'DEPENDENCY_CHANGED', '解析结果来源与已保存任务输入不一致')
    existing = ctx.repo.list('ParseResult', {'job_id': job['id']})
    if existing:
        # The worker should only publish once; a retry may return its recorded output.
        outputs = ctx.repo.list('JobOutput', {'job_id': job['id']})
        return [{'resource_type': r['resource_type'], 'resource_id': r['resource_id'], 'version': None} for r in outputs]
    identifier = str(uuid4())
    ctx.repo.create('ParseResult', {**result, 'id': identifier, 'job_id': job['id']})
    if input.get('monitor_id'):
        monitor = ctx.get('CompetitorMonitor', input['monitor_id'], lock=True)
        competitor = owned(ctx, 'Competitor', monitor['competitor_id'], job['product_id'])
        if competitor['id'] != input.get('competitor_id'):
            raise ApiError(409, 'DEPENDENCY_CHANGED', '监控对象与任务快照不一致')
        # Snapshot records the URL at dispatch time; it never overwrites manual fields.
        ctx.repo.create('MonitorSnapshot', {'monitor_id': monitor['id'], 'competitor_id': competitor['id'],
            'price': result['price'], 'sales_hint': result['sales_hint'], 'selling_points': result['selling_points'],
            'source_url': result['source_url'], 'captured_at': result['captured_at'],
            'completeness': 'partial' if result['missing_fields'] else 'complete', 'warnings': result['warnings']})
        ctx.repo.update('CompetitorMonitor', monitor['id'], {'last_error': None}, bump=False)
    return [{'resource_type': 'parse_result', 'resource_id': identifier, 'version': None}]


def record_monitor_failure(ctx, input, error):
    if input.get('monitor_id'):
        # Use the already sanitized business message, never the HTML/provider body.
        ctx.repo.update('CompetitorMonitor', input['monitor_id'], {'last_error': error.message[:4000] if isinstance(error, ApiError) else '公开页面读取失败，请查看解析任务状态。'}, bump=False)
