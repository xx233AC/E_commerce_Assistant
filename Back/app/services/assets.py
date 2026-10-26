from decimal import Decimal, ROUND_CEILING

from app.core.exceptions import ApiError
from app.rules.transitions import ASSET_TRANSITIONS, require_transition
from app.services.catalog import now_iso, owned, read_round
from app.services.common import Result


def list_assets(ctx):
    ctx.require_product(ctx.params['product_id'])
    if ctx.query.get('round_id'):
        read_round(ctx, ctx.query['round_id'])
    if ctx.query.get('creative_plan_id'):
        owned(ctx, 'CreativePlan', ctx.query['creative_plan_id'])
    filters = {'product_id': ctx.params['product_id'], **{k: ctx.query[k] for k in ('round_id', 'asset_type', 'review_status', 'creative_plan_id', 'execution_mode') if k in ctx.query}}
    return ctx.collection('Asset', filters)


def get_asset(ctx):
    ctx.require_product(ctx.params['product_id'])
    return owned(ctx, 'Asset', ctx.params['asset_id'])


def create_asset(ctx):
    product = ctx.require_product(ctx.params['product_id'], lock=True)
    ctx.require_round(product['id'], ctx.body['round_id'])
    file = owned(ctx, 'FileObject', ctx.body['file_id'])
    if file['storage_status'] != 'available' or file['purpose'] != 'media' or not file['content_type'].startswith(('image/', 'video/')):
        raise ApiError(422, 'ASSET_FILE_INVALID', '只能登记同商品已验证可用的媒体用途图片或视频')
    storage = ctx.get('FileStorage', file['id'])
    if not storage.get('width') or not storage.get('height'):
        raise ApiError(422, 'MEDIA_METADATA_MISSING', '文件缺少已验证的媒体尺寸，请重新上传')
    asset_type = 'video' if file['content_type'].startswith('video/') else 'image'
    if asset_type == 'video' and not storage.get('duration_seconds'):
        raise ApiError(422, 'MEDIA_METADATA_MISSING', '视频缺少已验证的时长，请重新上传')
    version_no = 1
    if ctx.body.get('parent_asset_id'):
        parent = owned(ctx, 'Asset', ctx.body['parent_asset_id'])
        if parent['asset_type'] != asset_type:
            raise ApiError(422, 'ASSET_TYPE_MISMATCH', '新素材版本必须与父素材类型一致')
        version_no = parent['version_no'] + 1
    return ctx.repo.create('Asset', {**ctx.body, 'product_id': product['id'], 'asset_type': asset_type,
        'origin': 'uploaded', 'review_status': 'pending', 'version_no': version_no, 'execution_mode': file['execution_mode'],
        'width': storage['width'], 'height': storage['height'], 'duration_sec': int(Decimal(storage['duration_seconds']).to_integral_value(rounding=ROUND_CEILING)) if asset_type == 'video' else None})


def apply_patch(ctx, asset, body):
    ctx.require_round(asset['product_id'], asset['round_id'])
    changes = dict(body)
    target = changes.get('review_status', asset['review_status'])
    if target != asset['review_status']:
        require_transition(asset['review_status'], target, ASSET_TRANSITIONS)
        if target == 'rejected' and not (changes.get('review_remark') or '').strip():
            raise ApiError(422, 'REVIEW_REMARK_REQUIRED', '驳回素材必须填写审核原因')
        if asset['review_status'] == 'approved' and any(
            r['experiment_status'] in {'confirmed', 'running'} and r['related_asset']['id'] == asset['id']
            for r in ctx.repo.list('AdExperiment', {'product_id': asset['product_id']})):
            raise ApiError(409, 'ASSET_IN_USE', '已确认或运行中的实验正在使用该素材，不能撤回审核')
        changes.update(reviewed_by=ctx.user['id'], reviewed_at=now_iso())
        if target == 'pending':
            changes.update(reviewed_by=None, reviewed_at=None)
    return ctx.repo.update('Asset', asset['id'], changes)


def patch_asset(ctx):
    ctx.require_product(ctx.params['product_id'], lock=True)
    row = owned(ctx, 'Asset', ctx.params['asset_id'], lock=True)
    ctx.check_version(row)
    return apply_patch(ctx, row, ctx.body)


def batch_patch(ctx):
    ctx.require_product(ctx.params['product_id'], lock=True)
    plan = owned(ctx, 'CreativePlan', ctx.params['creative_plan_id'])
    ids = [i['asset_id'] for i in ctx.body['items']]
    if len(ids) != len(set(ids)):
        raise ApiError(422, 'DUPLICATE_ASSET', '批量审核中不能重复提供同一素材')
    rows = {identifier: owned(ctx, 'Asset', identifier, lock=True) for identifier in sorted(ids)}
    for item in ctx.body['items']:
        row = rows[item['asset_id']]
        if row['creative_plan_id'] != plan['id']:
            raise ApiError(404, 'NOT_FOUND', '素材不属于当前创意方案')
        if row['version'] != item['expected_version']:
            raise ApiError(412, 'VERSION_CONFLICT', '素材已被修改，请刷新后重新审核')
    return {'items': [apply_patch(ctx, rows[item['asset_id']], {k: v for k, v in item.items() if k not in {'asset_id', 'expected_version'}}) for item in ctx.body['items']]}


def sync_assets(ctx):
    from app.services.jobs import submit
    ctx.require_product(ctx.params['product_id'], lock=True)
    modes = set()
    for identifier in ctx.body['job_ids']:
        job = owned(ctx, 'GenerationJob', identifier)
        if job['job_status'] != 'succeeded' or job['job_kind'] not in {'image', 'video'}:
            raise ApiError(409, 'JOB_NOT_SUCCEEDED', '只能补偿同步成功的图片或视频任务')
        if job.get('round_id'):
            ctx.require_round(ctx.params['product_id'], job['round_id'])
        modes.add(job['execution_mode'])
    if len(modes) > 1:
        raise ApiError(422, 'DEMO_REAL_MIXED', '真实与演示媒体任务须分批同步')
    return Result(submit(ctx, 'asset_sync', dict(ctx.body), execution_mode=next(iter(modes))), status=202)
