"""BigModel official REST API. Submit once; poll the returned task id.

request_id is a trace id, NOT an assumed provider idempotency guarantee.
No SDK or transport retry may repeat a paid POST automatically.
"""
import json
import re
from urllib.parse import quote

import httpx

from app.core.exceptions import ApiError
from app.llm.client import get_secret

BASE_URL = 'https://open.bigmodel.cn/api/paas/v4'
IMAGE_SIZES = [(1280, 1280), (1152, 1536), (1536, 1152), (1152, 2048), (2048, 1152)]
VIDEO_SIZES = {
    ('16:9', '720p'): '1280x720', ('9:16', '720p'): '720x1280',
    ('16:9', '1080p'): '1920x1080', ('9:16', '1080p'): '1080x1920',
    ('1:1', '1080p'): '1024x1024',
}


def capability(kind):
    return {'capability': kind,
            'supported_aspect_ratios': ['1:1', '3:4', '4:3', '9:16', '16:9'] if kind == 'image' else ['1:1', '9:16', '16:9'],
            'max_duration_sec': 10 if kind == 'video' else None,
            'max_images_per_request': 4 if kind == 'image' else None,
            'supported_resolutions': ['720p', '1080p'] if kind == 'video' else [],
            'supported_image_sizes': [{'width': w, 'height': h} for w, h in IMAGE_SIZES] if kind == 'image' else []}


class ZhipuMediaProvider:
    def validate(self, kind, request, config):
        expected = 'glm-image' if kind == 'image' else 'cogvideox-3'
        if config['base_url'].rstrip('/') != BASE_URL or config['model_name'] != expected or config['execution_mode'] != 'real':
            raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '智谱媒体配置须使用官方地址和对应的 glm-image / cogvideox-3 模型')
        if not get_secret(config.get('secret_env_name')):
            raise ApiError(422, 'MODEL_NOT_CONFIGURED', '智谱密钥尚未配置')
        if kind == 'image':
            if (request['width'], request['height']) not in IMAGE_SIZES:
                raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '请选择模型配置中列出的 GLM-Image 尺寸')
        elif request['duration_sec'] not in (5, 10):
            raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', 'CogVideoX-3 仅支持 5 或 10 秒，请先调整并重新选定视频脚本')

    def validate_input(self, kind, data):
        content = data['creative_plan']['content']
        files = data['reference_files']
        if kind == 'image' and files:
            raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', 'GLM-Image 官方接口仅支持文生图；请清空方案和生成请求的参考图，改用文字描述商品外观')
        if kind == 'video':
            if not 1 <= len(content['generation_prompt']) <= 512:
                raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', 'CogVideoX-3 视频提示词须为 1—512 个字符，请先编辑脚本')
            if (content['aspect_ratio'], data['request']['resolution']) not in VIDEO_SIZES:
                raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', '方形视频请选择 1080p（供应商实际输出为 1024×1024）')
            if len(files) > 2 or any(f['content_type'] not in ('image/jpeg', 'image/png') or f['byte_size'] > 5 * 1024 * 1024 for f in files):
                raise ApiError(422, 'MODEL_CAPABILITY_UNSUPPORTED', 'CogVideoX-3 最多接受两张 JPEG/PNG 首尾帧，每张不超过 5MiB')

    def payload(self, kind, data, request_id, reference_images=None):
        content, request = data['creative_plan']['content'], data['request']
        prompt = content['generation_prompt']
        if kind == 'image':
            if content.get('negative_prompt'):
                prompt += '\n避免：' + content['negative_prompt']
            return {'model': 'glm-image', 'prompt': prompt, 'quality': 'hd',
                    'size': f"{request['width']}x{request['height']}"}
        result = {'model': 'cogvideox-3', 'prompt': prompt, 'quality': 'quality',
                  'size': VIDEO_SIZES[(content['aspect_ratio'], request['resolution'])],
                  'duration': request['duration_sec'], 'fps': 30, 'with_audio': False,
                  'watermark_enabled': False, 'request_id': request_id}
        if reference_images:
            result['image_url'] = reference_images[0] if len(reference_images) == 1 else reference_images
        return result

    def _request(self, method, path, config, payload=None):
        secret = get_secret(config.get('secret_env_name'))
        if not secret:
            raise ApiError(422, 'MODEL_NOT_CONFIGURED', '智谱密钥尚未配置')
        try:
            with httpx.Client(timeout=min(config['request_timeout_sec'], 120), trust_env=False, follow_redirects=False) as client:
                with client.stream(method, BASE_URL + path, json=payload,
                                   headers={'Authorization': 'Bearer ' + secret, 'Accept': 'application/json'}) as response:
                    if response.status_code == 429 and method == 'GET':
                        raise ApiError(503, 'PROVIDER_UNAVAILABLE', '智谱查询暂时限流，稍后继续查询原任务', retryable=True)
                    # 5xx/transport failures after a POST may still have created a task.
                    if response.status_code >= 500:
                        code = 'PROVIDER_SUBMISSION_UNKNOWN' if method == 'POST' else 'PROVIDER_UNAVAILABLE'
                        raise ApiError(503, code, '智谱服务暂不可用；提交状态不明确时不会自动重复扣费', retryable=method == 'GET')
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 2 * 1024 * 1024:
                            raise ValueError()
                    result = json.loads(raw)
                    if not isinstance(result, dict):
                        raise ValueError()
                    if not 200 <= response.status_code < 300 or result.get('error'):
                        error = result.get('error') or {}
                        provider_code = str(error.get('code', response.status_code))
                        safe_code = provider_code if re.fullmatch(r'[A-Za-z0-9_-]{1,40}', provider_code) else 'unknown'
                        # Never expose provider response text, request payload or credentials.
                        raise ApiError(422, 'PROVIDER_REJECTED', f'智谱拒绝请求（代码 {safe_code}），请检查额度、模型权限；无水印视频需开通去水印权限')
                    return result
        except (httpx.HTTPError, ValueError, TypeError):
            code = 'PROVIDER_SUBMISSION_UNKNOWN' if method == 'POST' else 'PROVIDER_UNAVAILABLE'
            raise ApiError(503, code, '无法确认智谱响应，请稍后查询；不会自动重复提交生成请求', retryable=method == 'GET') from None

    def submit(self, kind, payload, config, idempotency_key):
        path = '/async/images/generations' if kind == 'image' else '/videos/generations'
        result = self._request('POST', path, config, payload)
        task_id = result.get('id')
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,200}', task_id):
            raise ApiError(503, 'PROVIDER_SUBMISSION_UNKNOWN', '智谱未返回有效任务编号，请核对供应商记录后处理')
        request_id = result.get('request_id')
        return {'task_id': task_id, 'request_id': request_id[:200] if isinstance(request_id, str) else None, 'status': result.get('task_status')}

    def query(self, provider_task_id, config):
        return self._request('GET', '/async-result/' + quote(provider_task_id, safe=''), config)

    def result_url(self, kind, result):
        items = (result.get('image_result') or result.get('data')) if kind == 'image' else result.get('video_result')
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict) or not isinstance(items[0].get('url'), str):
            raise ApiError(422, 'PROVIDER_OUTPUT_INVALID', '智谱任务成功但没有返回预期的媒体文件')
        return items[0]['url']
