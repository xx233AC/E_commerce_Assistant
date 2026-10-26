"""Checkpoint paid submissions, poll without resubmission, publish private assets."""
import base64
from copy import deepcopy
import hashlib
import io
import logging
import math
import time
from uuid import NAMESPACE_URL, uuid5

from app.core.config import get_settings
from app.core.contract import validate_schema
from app.core.exceptions import ApiError
from app.integrations.media_generation.base import get_provider
from app.integrations.public_pages.client import _fetch_bytes
from app.integrations.storage import minio
from app.services.files import inspect_file, read_bytes

logger = logging.getLogger(__name__)
POLL_SECONDS = 5


def checkpoint(job_id, lease, records=None, *, progress=None):
    from app.workers import runtime
    with runtime.SessionLocal.begin() as db:
        ctx = runtime.context(db)
        owned = runtime.still_owned(ctx, job_id, lease)
        if not owned:
            raise ApiError(409, 'JOB_TIMEOUT', '任务已取消、超时或执行权失效')
        job, state = owned
        if records is not None:
            provider_state = {**state['provider_state'], 'media': deepcopy(records)}
            ctx.repo.update('JobRuntime', job_id, {'provider_state': provider_state}, bump=False)
        if progress is not None:
            ctx.repo.update('GenerationJob', job_id, {'progress': progress})
        return deepcopy(state['provider_state'].get('media', []))


def download(url, limit):
    # DNS-pinned public GET, bounded size/time, no authentication or proxy forwarded.
    status, _, content, _ = _fetch_bytes(url, time.monotonic() + 180, limit)
    if status != 200:
        raise ApiError(503, 'PROVIDER_DOWNLOAD_FAILED', '生成文件暂时无法下载，可重试同步已有供应商结果')
    return content


def reference_images(job, data):
    if job['job_kind'] != 'video':
        return []
    from app.workers import runtime
    images = []
    with runtime.SessionLocal() as db:
        ctx = runtime.context(db)
        for file in data['reference_files']:
            raw = read_bytes(ctx, file['id'])
            if len(raw) > 5 * 1024 * 1024:
                raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '视频参考图片超过 5MiB')
            images.append('data:' + file['content_type'] + ';base64,' + base64.b64encode(raw).decode('ascii'))
    return images


def execute_media(job, lease, data):
    from app.workers import runtime
    started = time.monotonic()
    kind, config = job['job_kind'], data['model_config']
    adapter = get_provider(config)
    adapter.validate(kind, data['request'], config)
    adapter.validate_input(kind, data)
    records = checkpoint(job['id'], lease)
    count = data['request']['count'] if kind == 'image' else 1
    images = reference_images(job, data)
    for index in range(count):
        checkpoint(job['id'], lease)
        if len(records) <= index:
            records.append({'index': index})
        item = records[index]
        if item.get('submitting') and not item.get('task_id'):
            raise ApiError(409, 'PROVIDER_SUBMISSION_UNKNOWN', '上次提交结果不明确，已停止重复提交，请核对智谱任务记录')
        if not item.get('task_id'):
            payload = adapter.payload(kind, data, f"{job['id']}-{index}", images)
            # Durable intent BEFORE the network side effect closes the restart gap.
            item['submitting'] = True
            checkpoint(job['id'], lease, records)
            try:
                submitted = adapter.submit(kind, payload, config, f"{job['id']}-{index}")
            except ApiError as exc:
                if exc.code != 'PROVIDER_SUBMISSION_UNKNOWN':
                    item['submitting'] = False
                    checkpoint(job['id'], lease, records)
                raise
            item.update(submitted, submitting=False)
            # Save task id even if cancellation wins, so it remains auditable.
            with runtime.SessionLocal.begin() as db:
                ctx = runtime.context(db)
                ctx.get('GenerationJob', job['id'], lock=True)
                state = ctx.get('JobRuntime', job['id'], lock=True)
                if state['lease_token'] != lease and state['provider_state'].get('media') != records:
                    # Never overwrite the state of a newer execution.
                    if state['lease_token'] is not None:
                        raise ApiError(409, 'JOB_TIMEOUT', '任务执行权已改变')
                ctx.repo.update('JobRuntime', job['id'], {'provider_state': {**state['provider_state'], 'media': deepcopy(records)}}, bump=False)
            checkpoint(job['id'], lease, records, progress=10 + index * 70 // count)
        if item.get('status') == 'FAIL':
            raise ApiError(422, 'PROVIDER_TASK_FAILED', '智谱媒体生成失败，请修改方案后重新发起生成')
        while not item.get('result_url'):
            checkpoint(job['id'], lease)
            try:
                response = adapter.query(item['task_id'], config)
            except ApiError as exc:
                if not exc.retryable:
                    raise
                time.sleep(POLL_SECONDS)
                continue
            status = response.get('task_status')
            if status not in ('PROCESSING', 'SUCCESS', 'FAIL'):
                raise ApiError(422, 'PROVIDER_OUTPUT_INVALID', '智谱返回了未知任务状态')
            item['status'] = status
            if status == 'SUCCESS':
                item['result_url'] = adapter.result_url(kind, response)
            checkpoint(job['id'], lease, records)
            if status == 'FAIL':
                raise ApiError(422, 'PROVIDER_TASK_FAILED', '智谱媒体生成失败，请修改方案后重新发起生成')
            if status == 'PROCESSING':
                time.sleep(POLL_SECONDS)
        if not item.get('file'):
            with runtime.SessionLocal() as db:
                limits = runtime.context(db).get('SystemSettings', 'singleton')
            limit = min(limits['max_upload_image_bytes'], 20971520) if kind == 'image' else min(limits['max_upload_video_bytes'], 524288000)
            raw = download(item['result_url'], limit)
            stream = io.BytesIO(raw)
            mime, width, height, duration = inspect_file(stream, 'generated', 'media', len(raw), limits)
            if not mime.startswith(kind + '/'):
                raise ApiError(422, 'PROVIDER_OUTPUT_INVALID', '生成文件类型与任务不一致')
            if kind == 'image' and (width, height) != (data['request']['width'], data['request']['height']):
                raise ApiError(422, 'PROVIDER_OUTPUT_INVALID', '生成图片尺寸与请求不一致')
            if kind == 'video' and abs(duration - data['request']['duration_sec']) > 1:
                raise ApiError(422, 'PROVIDER_OUTPUT_INVALID', '生成视频时长与请求不一致')
            if kind == 'video':
                from app.integrations.media_generation.zhipu import VIDEO_SIZES
                expected_size = VIDEO_SIZES[(data['creative_plan']['content']['aspect_ratio'], data['request']['resolution'])]
                if f'{width}x{height}' != expected_size:
                    raise ApiError(422, 'PROVIDER_OUTPUT_INVALID', '生成视频尺寸与请求不一致')
            file_id = str(uuid5(NAMESPACE_URL, f"commerce-media:{job['id']}:{index}"))
            object_name = 'generated/' + job['id'] + '/' + file_id
            item['storage_intent'] = {'file_id': file_id, 'bucket': get_settings().minio_bucket, 'object_name': object_name}
            checkpoint(job['id'], lease, records)
            minio.put(stream, object_name, len(raw), mime)
            item['file'] = {**item['storage_intent'], 'content_type': mime, 'width': width, 'height': height,
                            'duration_seconds': duration, 'byte_size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            checkpoint(job['id'], lease, records, progress=10 + (index + 1) * 80 // count)
    return [item['file'] for item in records], {
        'elapsed_seconds': time.monotonic() - started,
        'provider_request_id': records[0].get('request_id') or records[0].get('task_id'),
        'provider_task_ids': [item['task_id'] for item in records],
    }


def publish_media(ctx, job, data, outputs):
    resources = []
    for index, file in enumerate(outputs):
        existing = ctx.repo.list('Asset', {'source_job_id': job['id'], 'output_index': index})
        if existing:
            asset = existing[0]
        else:
            ext = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp', 'video/mp4': '.mp4'}[file['content_type']]
            row = ctx.repo.create('FileObject', {'id': file['file_id'], 'product_id': job['product_id'],
                'file_name': data['model_config']['model_name'] + '-' + str(index + 1) + ext,
                **{key: file[key] for key in ('content_type', 'byte_size', 'sha256')},
                'purpose': 'media', 'storage_status': 'available', 'execution_mode': 'real'})
            ctx.repo.create('FileStorage', {key: file[key] for key in ('file_id', 'bucket', 'object_name', 'width', 'height', 'duration_seconds')} | {'checksum': file['sha256']})
            asset = ctx.repo.create('Asset', {'product_id': job['product_id'], 'round_id': job['round_id'],
                'creative_plan_id': job['creative_plan_id'], 'creative_plan_version': job['creative_plan_version'],
                'file_id': row['id'], 'asset_type': job['job_kind'], 'origin': 'generated',
                'model_name': data['model_config']['model_name'], 'source_job_id': job['id'], 'output_index': index,
                'width': file['width'], 'height': file['height'],
                'duration_sec': math.ceil(file['duration_seconds']) if file['duration_seconds'] else None,
                'review_status': 'pending', 'version_no': 1, 'execution_mode': 'real',
                'usage_scene': 'main_image' if job['job_kind'] == 'image' else 'short_video'})
            validate_schema('FileObject', row)
            validate_schema('Asset', asset)
        resources.append({'resource_type': 'asset', 'resource_id': asset['id'], 'version': asset['version']})
    return resources


def cleanup_unpublished(job_id):
    """Only remove this terminal job's objects after checking actual DB publication."""
    from app.workers import runtime
    try:
        with runtime.SessionLocal.begin() as db:
            ctx = runtime.context(db)
            job = ctx.get('GenerationJob', job_id, lock=True)
            if job['job_status'] not in ('failed', 'cancelled', 'timeout'):
                return
            state = ctx.get('JobRuntime', job_id, lock=True)
            records = deepcopy(state['provider_state'].get('media', []))
            for item in records:
                storage = item.get('storage_intent')
                if storage and not ctx.repo.get('FileStorage', storage['file_id']):
                    minio.client().remove_object(storage['bucket'], storage['object_name'])
                    item.pop('file', None)
                    item.pop('storage_intent', None)
            result_state = {key: value for key, value in state['result_state'].items() if key != 'outputs'}
            ctx.repo.update('JobRuntime', job_id, {'provider_state': {**state['provider_state'], 'media': records}, 'result_state': result_state}, bump=False)
    except Exception:
        logger.error('Media cleanup requires reconciliation for job %s', job_id)
