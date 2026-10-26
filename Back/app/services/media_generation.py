"""Validate selected plans and freeze dependencies before paid media dispatch."""
from copy import deepcopy
from fractions import Fraction

from app.core.exceptions import ApiError
from app.services.common import Result
from app.services.jobs import submit
from app.integrations.media_generation.base import get_provider
from app.services.ai_support import available_files, owned
from app.services.settings import supports


def validate_capability(kind, request, plan, config):
    capability = next(item for item in config['capabilities'] if item['capability'] == kind)
    content = plan['content']
    if content['aspect_ratio'] not in capability['supported_aspect_ratios']:
        raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '模型不支持方案要求的画面比例')
    if kind == 'image':
        ratio = Fraction(*map(int, content['aspect_ratio'].split(':')))
        if Fraction(request['width'], request['height']) != ratio:
            raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '图片尺寸比例须与选定方案一致')
        size = {'width': request['width'], 'height': request['height']}
        if size not in capability['supported_image_sizes'] or request['count'] > (capability['max_images_per_request'] or 0):
            raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '模型不支持请求的图片尺寸或张数')
    else:
        if request['duration_sec'] != content['duration_sec']:
            raise ApiError(422, 'VALIDATION_ERROR', '视频时长须与选定脚本总时长一致')
        if request['duration_sec'] > (capability['max_duration_sec'] or 0) or request['resolution'] not in capability['supported_resolutions']:
            raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '模型不支持请求的视频时长或分辨率')


def references(ctx, kind, request, plan, product_id, execution_mode):
    real = execution_mode == 'real'
    if real and plan['provenance']['execution_mode'] == 'demo':
        raise ApiError(422, 'DEMO_REAL_MIXED', '真实媒体生成不能使用演示方案')
    file_ids = request.get('reference_file_ids', [])
    if len(set(file_ids)) != len(file_ids):
        raise ApiError(422, 'INVALID_RESOURCE_REFERENCE', '参考文件不能重复')
    file_ids = list(dict.fromkeys(plan['content'].get('reference_file_ids', []) + file_ids))
    files = available_files(ctx, file_ids, product_id, real_only=real)
    asset_ids = request.get('reference_asset_ids', [])
    if len(set(asset_ids)) != len(asset_ids):
        raise ApiError(422, 'INVALID_RESOURCE_REFERENCE', '参考素材不能重复')
    assets = []
    for identifier in asset_ids:
        asset = owned(ctx, 'Asset', identifier, product_id=product_id)
        file = owned(ctx, 'FileObject', asset['file_id'], product_id=product_id)
        if asset['review_status'] != 'approved' or file['storage_status'] != 'available':
            raise ApiError(422, 'INVALID_RESOURCE_REFERENCE', '参考素材须为已审核通过且文件可用的同商品素材')
        if real and (asset['execution_mode'] == 'demo' or file['execution_mode'] == 'demo'):
            raise ApiError(422, 'DEMO_REAL_MIXED', '真实媒体生成不能使用演示素材')
        assets.append(asset)
        if file['id'] not in {item['id'] for item in files}:
            files.append(file)
    return files, assets


def generate(ctx, kind):
    product = ctx.require_product(ctx.params['product_id'], active=True, lock=True)
    round_row = ctx.require_round(product['id'], ctx.body['round_id'])
    plan = owned(ctx, 'CreativePlan', ctx.params['creative_plan_id'], product_id=product['id'], round_id=round_row['id'])
    if plan['version'] != ctx.body['plan_version'] or plan['status'] != 'selected':
        raise ApiError(409, 'DEPENDENCY_CHANGED', '请选定当前版本方案后生成')
    expected = 'main_image' if kind == 'image' else 'video_script'
    if plan['plan_type'] != expected:
        raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '方案类型与生成任务不匹配')
    config = ctx.get('ModelConfig', ctx.body['model_config_id'])
    if not config['enabled'] or not supports(config, kind):
        raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '所选模型不具备此生成能力，请上传真实素材')
    validate_capability(kind, ctx.body, plan, config)
    files, assets = references(ctx, kind, ctx.body, plan, product['id'], config['execution_mode'])
    provider = get_provider(config)
    provider.validate(kind, ctx.body, config)
    payload = {'request': deepcopy(ctx.body), 'product_id': product['id'], 'round_id': round_row['id'],
               'round': round_row, 'creative_plan': plan, 'model_config': config,
               'snapshot': ctx.get('RoundSnapshot', plan['snapshot_id']), 'reference_files': files,
               'reference_assets': assets, 'execution_mode': config['execution_mode']}
    provider.validate_input(kind, payload)
    accepted = submit(ctx, kind, payload, model_config_id=config['id'], execution_mode=config['execution_mode'], creative_plan=plan)
    return Result(accepted, status=202, headers={'Location': accepted['poll_url']})


def image(ctx): return generate(ctx, 'image')
def video(ctx): return generate(ctx, 'video')


HANDLERS = {'POST /products/{product_id}/creative-plans/{creative_plan_id}/images/generate': image,
            'POST /products/{product_id}/creative-plans/{creative_plan_id}/videos/generate': video}
