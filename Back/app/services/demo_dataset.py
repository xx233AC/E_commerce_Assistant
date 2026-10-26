"""Explicit empty-workspace demonstration. Never runs during app startup.

All database writes belong to the caller's one transaction. Real sample bytes
are stored in private MinIO; text outputs are visibly labeled demo, not AI calls.
"""
import hashlib
import io
import logging
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.contract import validate_schema
from app.core.exceptions import ApiError
from app.integrations.storage import minio
from app.services import ad_experiments, ad_recommendations, assets, catalog, competitors, creative, files, inventory, jobs, performance, rounds
from app.services.ai_support import ref
from app.services.common import Result
from app.services.settings import TEXT_CAPABILITY
from app.rules.metrics import summarize
from app.workers.handlers.text import execute_text, publish_text

logger = logging.getLogger(__name__)
SINGLE_STORE_LOCK = 777001
SHOP_TZ = timezone(timedelta(hours=8))
SAMPLE_PATH = Path(__file__).resolve().parents[2] / 'demo-assets/product-mug.jpg'


def _iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _objects(job_id):
    return [f'demo/{job_id}/product-mug.jpg', f'demo/{job_id}/media-mug.jpg']


def cleanup_demo_objects(job_id):
    """Call only after confirming the demo transaction did not succeed."""
    settings = get_settings()
    for object_name in _objects(job_id):
        try:
            minio.client().remove_object(settings.minio_bucket, object_name)
        except Exception:
            # Preserve a discoverable deterministic key; never report clean-up as
            # successful when storage is unavailable. No credentials are logged.
            logger.error('Demo object cleanup pending for job %s', job_id)


def _guard(ctx, job, payload):
    validate_schema('DemoCreate', {k: payload[k] for k in ('dataset_version', 'mode') if k in payload})
    if ctx.user.get('role') != 'admin':
        raise ApiError(403, 'FORBIDDEN', '演示初始化仅允许管理员')
    # Serializes with ordinary store creation; the unique DB constraint is an
    # additional safeguard if an older caller lacks this advisory lock.
    ctx.db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': SINGLE_STORE_LOCK})
    settings = ctx.get('SystemSettings', 'singleton', lock=True)
    if not get_settings().demo_enabled or not settings['demo_data_enabled'] or job.get('execution_mode') != 'demo':
        raise ApiError(422, 'DEMO_DISABLED', '服务端与系统设置必须显式开启演示初始化')
    for kind in ('Store', 'Product', 'PlatformAccount', 'Sku', 'Inventory', 'Competitor', 'OperatingRound', 'FileObject', 'Asset', 'ImportBatch', 'PromotionLink', 'PerformanceRecord'):
        if ctx.repo.count(kind):
            raise ApiError(409, 'DEMO_DATA_NOT_EMPTY', '已有业务数据，不能初始化演示数据')


def _call(ctx, function, schema=None, *, params=None, body=None, version=None):
    result = function(replace(ctx, params=params or {}, body=body or {}, headers={'if-match': f'"{version}"'} if version else {}))
    value = result.data if isinstance(result, Result) else result
    if schema:
        validate_schema(schema, value)
    return value


def _sample_file(ctx, product_id, object_name, content, purpose, mode):
    stream = io.BytesIO(content)
    mime, width, height, duration = files.inspect_file(stream, 'product-mug.jpg', purpose, len(content), ctx.get('SystemSettings', 'singleton'))
    minio.put(stream, object_name, len(content), mime)
    checksum = hashlib.sha256(content).hexdigest()
    file = ctx.repo.create('FileObject', {
        'product_id': product_id, 'file_name': '[演示样例] product-mug.jpg', 'content_type': mime,
        'byte_size': len(content), 'sha256': checksum, 'purpose': purpose,
        'storage_status': 'available', 'execution_mode': mode,
    })
    ctx.repo.create('FileStorage', {'file_id': file['id'], 'bucket': get_settings().minio_bucket,
        'object_name': object_name, 'width': width, 'height': height, 'duration_seconds': duration, 'checksum': checksum})
    return file


def _text(ctx, parent_job, config, kind, input_data):
    current = _iso(datetime.now(timezone.utc))
    input_data = deepcopy(input_data)
    input_data.update(model_config=config, prompt_version='v1', execution_mode='demo', demo_parent_job_id=parent_job['id'])
    job = ctx.repo.create('GenerationJob', {
        'product_id': input_data['product_id'], 'round_id': input_data['round_id'],
        'job_kind': kind, 'job_status': 'running', 'dispatch_status': 'dispatched', 'execution_mode': 'demo',
        'attempts': 1, 'max_attempts': 1, 'cancellation_requested': False, 'result_resources': [], 'progress': 0,
        'model_config_id': config['id'], 'model_config_version': config['version'], 'submitted_by': ctx.user['id'],
        'queued_at': current, 'started_at': current,
    })
    ctx.repo.create('JobRuntime', {'job_id': job['id'], 'input': input_data, 'provider_state': {}, 'result_state': {}})
    jobs.event(ctx, job, 'running', '[演示] 使用明确标识的固定内容验证流程，不调用真实模型')
    output = execute_text(kind, input_data, config)
    resources = publish_text(ctx, job, input_data, output)
    for index, resource in enumerate(resources):
        ctx.repo.create('JobOutput', {'job_id': job['id'], 'output_index': index,
            'resource_type': resource['resource_type'], 'resource_id': resource['resource_id']})
    ctx.repo.update('JobRuntime', job['id'], {'result_state': {'resources': resources}}, bump=False)
    finished = ctx.repo.update('GenerationJob', job['id'], {'job_status': 'succeeded', 'progress': 100,
        'finished_at': _iso(datetime.now(timezone.utc)), 'result_resources': resources})
    jobs.event(ctx, finished, 'succeeded', '[演示] 结果已校验并保存不可变修订')
    ctx.repo.create('ModelCall', {'job_id': job['id'], 'model_config_id': config['id'], 'model_config_version': config['version'],
        'provider': 'demo', 'model_name': config['model_name'], 'prompt_version': 'v1', 'outcome': 'succeeded'})
    kinds = {'diagnosis': 'Diagnosis', 'creative_plan': 'CreativePlan', 'ad_recommendation': 'AdRecommendation', 'review_report': 'ReviewReport'}
    return [ctx.get(kinds[r['resource_type']], r['resource_id']) for r in resources]


def _round(ctx, parent_job, config, product_id, original, media, number, previous=None):
    pp = {'product_id': product_id}
    create = {'name': f'[演示] 第 {number} 轮运营', 'objective': '[演示] 验证商品诊断、内容制作、人工投放与复盘闭环'}
    if previous:
        create.update(previous_round_id=previous['round']['id'], source_review=ref(previous['report']),
            adopted_action_ids=[previous['report']['content']['next_actions'][0]['action_id']])
    round_row = _call(ctx, rounds.create_round, 'OperatingRound', params=pp, body=create)
    rid = round_row['id']
    rp = {**pp, 'round_id': rid}
    snapshot = rounds.capture_snapshot(ctx, ctx.get('Product', product_id), rid)
    shared = {'product_id': product_id, 'round_id': rid, 'round': round_row, 'snapshot': snapshot}
    diagnosis = _text(ctx, parent_job, config, 'diagnosis', {**shared, 'request': {'round_id': rid},
        'source_review': previous['report'] if previous else None})[0]
    round_row = _call(ctx, rounds.patch_round, 'OperatingRound', params=rp,
        body={'selected_diagnosis': ref(diagnosis)}, version=round_row['version'])
    selected = {}
    for kind in ('main_image_plan', 'video_script', 'title_plan'):
        plans = _text(ctx, parent_job, config, kind, {**shared, 'round': round_row, 'diagnosis': diagnosis,
            'reference_files': [original], 'request': {'round_id': rid, 'diagnosis': ref(diagnosis), 'count': 3,
            'reference_file_ids': [original['id']]}})
        first = plans[0]
        selected[kind] = _call(ctx, creative.patch, 'CreativePlan', params={**pp, 'creative_plan_id': first['id']},
            body={**{key: first[key] for key in ('plan_type', 'title', 'content', 'rationale_text')}, 'status': 'selected'}, version=first['version'])
    asset = _call(ctx, assets.create_asset, 'Asset', params=pp, body={'round_id': rid, 'file_id': media['id'],
        'usage_scene': 'ad_creative', 'tags': ['演示样例'], 'remark': '[演示] 来自随项目提供的真实照片，非模型生成效果'})
    asset = _call(ctx, assets.patch_asset, 'Asset', params={**pp, 'asset_id': asset['id']},
        body={'review_status': 'approved', 'review_remark': '[演示] 已核对样例照片；不代表真实商品审核'}, version=asset['version'])
    link = _call(ctx, promotion_link, 'PromotionLink', params=pp, body={'round_id': rid,
        'link_name': f'[演示] 第 {number} 轮链接', 'target_url': 'https://example.com/?demo=commerce-mug',
        'utm': {'source': 'other', 'medium': 'demo', 'campaign': rid, 'content': 'sample-mug', 'term': None},
        'scene_text': '[演示] 示例地址，不连接真实商品或广告平台'})
    request = {'round_id': rid, 'diagnosis': ref(diagnosis), 'asset_refs': [ref(asset)],
        'title_plan': ref(selected['title_plan']), 'budget_cap': '100.00', 'daily_cap': '20.00',
        'duration_days': 5, 'objective': '[演示] 验证人工确认后的实验流程，不产生真实花费'}
    recommendation = _text(ctx, parent_job, config, 'ad_recommendation', {**shared, 'round': round_row,
        'request': request, 'diagnosis': diagnosis, 'assets': [asset], 'title_plan': selected['title_plan']})[0]
    recommendation = _call(ctx, ad_recommendations.confirm, 'AdRecommendation',
        params={**pp, 'recommendation_id': recommendation['id']}, body={'decision': 'confirmed', 'remark': '[演示] 流程确认，不授权真实广告花费'}, version=recommendation['version'])
    # Historical demo dates avoid future records and keep the two rounds separate.
    day = datetime.now(SHOP_TZ).date() - timedelta(days=3 - number)
    experiment_input = {'round_id': rid, 'recommendation': ref(recommendation), 'related_link_ids': [link['id']],
        'count': 1, 'planned_start_date': day.isoformat()}
    experiment_resources = ad_experiments.execute_experiments(replace(ctx, params=pp), parent_job, experiment_input)
    experiment = ctx.get('AdExperiment', experiment_resources[0]['resource_id'])
    ep = {**pp, 'experiment_id': experiment['id']}
    for target, extra in (
        ('confirmed', {}),
        ('running', {'external_campaign_id': f'DEMO-ONLY-{number}-{rid[:8]}', 'actual_start_at': _iso(datetime.combine(day, datetime.min.time(), SHOP_TZ) + timedelta(hours=9))}),
        ('finished', {'actual_end_at': _iso(datetime.combine(day, datetime.min.time(), SHOP_TZ) + timedelta(hours=18))}),
    ):
        experiment = _call(ctx, ad_experiments.patch_experiment, 'AdExperiment', params=ep,
            body={'experiment_status': target, 'remark': '[演示] 模拟人工执行记录，无外部平台调用', **extra}, version=experiment['version'])
    record = _call(ctx, performance.create_performance, 'PerformanceRecord', params=pp, body={
        'round_id': rid, 'granularity': 'experiment_day', 'record_date': day.isoformat(), 'experiment_id': experiment['id'],
        'impressions': 1000 + number * 200, 'clicks': 30 + number * 10, 'conversions': number,
        'spend': '20.00', 'revenue': f'{number * 49}.00', 'notes': '[演示] 预设流程样例，非真实曝光、订单或广告账单',
    })
    totals, warnings = summarize([record])
    report = _text(ctx, parent_job, config, 'review_report', {**shared, 'round': round_row,
        'diagnosis': diagnosis, 'request': {'round_id': rid, 'period_start': day.isoformat(), 'period_end': day.isoformat(),
            'granularity': 'experiment_day', 'experiment_ids': [experiment['id']]},
        'performance_records': [record], 'metric_snapshot': totals,
        'warnings': ['演示数据，不构成真实经营效果或因果证据', *warnings], 'experiments': [experiment], 'comparison': None})[0]
    round_row = _call(ctx, rounds.patch_round, 'OperatingRound', params=rp,
        body={'status': 'completed', 'close_remark': '[演示] 已完成复盘并保留全部历史引用'}, version=ctx.get('OperatingRound', rid)['version'])
    return {'round': round_row, 'report': report}


def promotion_link(ctx):
    from app.services.promotion_links import create_link
    return create_link(ctx)


def execute_demo(ctx, job, payload):
    """Return result resources. Caller commits all business rows with job success."""
    _guard(ctx, job, payload)
    if not SAMPLE_PATH.is_file():
        raise ApiError(503, 'DEPENDENCY_UNAVAILABLE', '演示样例图片缺失，请检查部署文件')
    uploaded = False
    try:
        store = _call(ctx, catalog.create_store, 'Store', body={'store_name': '[演示] 商品运营样例店铺', 'platform': 'other',
            'owner_name': '[演示] 管理员', 'remark': '仅管理员显式启用后创建的流程演示；商品、预算和指标均为样例'})
        product = _call(ctx, catalog.create_product, 'Product', body={'store_id': store['id'], 'name': '[演示] 白色陶瓷马克杯',
            'category': '马克杯', 'price': '49.00', 'cost': '18.00', 'target_audience': '[演示] 办公与居家饮水场景',
            'selling_points': ['[演示] 简洁外观，实际规格和性能须自行核实'], 'status': 'draft'})
        pp = {'product_id': product['id']}
        sku = _call(ctx, inventory.create_sku, 'Sku', params=pp, body={'sku_code': 'DEMO-MUG-' + product['id'][:8],
            'sku_name': '[演示] 白色款', 'spec': [{'name': '颜色', 'value': '白色'}], 'price': '49.00', 'cost': '18.00'})
        stock = ctx.repo.list('Inventory', {'sku_id': sku['id']})[0]
        _call(ctx, inventory.adjust_inventory, 'InventoryMovement', params={**pp, 'sku_id': sku['id']},
            body={'change_qty': 100, 'reason_text': '[演示] 初始库存样例'}, version=stock['version'])
        sample = SAMPLE_PATH.read_bytes()
        # Mark before I/O so even partially accepted object writes get compensation.
        uploaded = True
        original = _sample_file(ctx, product['id'], _objects(job['id'])[0], sample, 'product_image', 'real')
        media = _sample_file(ctx, product['id'], _objects(job['id'])[1], sample, 'media', 'demo')
        product = _call(ctx, catalog.patch_product, 'Product', params=pp,
            body={'status': 'active', 'image_file_ids': [original['id']]}, version=product['version'])
        _call(ctx, competitors.create_competitor, 'Competitor', params=pp, body={'name': '[演示] 可比马克杯候选',
            'platform': 'other', 'price': '59.00', 'selling_points': ['[演示] 用于演示竞品输入快照'], 'review_keywords': [],
            'sales_hint': '[演示] 无真实销量信息', 'status': 'active'})
        config = ctx.repo.create('ModelConfig', {'name': '[演示] 明确标识的流程样例', 'provider': 'demo',
            'base_url': 'https://example.invalid', 'model_name': 'explicit-demo-v1', 'capabilities': [TEXT_CAPABILITY],
            'enabled': True, 'execution_mode': 'demo', 'request_timeout_sec': 60})
        first = _round(ctx, job, config, product['id'], original, media, 1)
        second = _round(ctx, job, config, product['id'], original, media, 2, previous=first)
        return [{'resource_type': 'review_report', 'resource_id': r['report']['id'], 'version': r['report']['version']} for r in (first, second)]
    except Exception:
        if uploaded:
            cleanup_demo_objects(job['id'])
        raise
