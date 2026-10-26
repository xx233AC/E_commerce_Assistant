"""Explicit one-image/one-video live check; re-running resumes saved provider ids.

Uses real paid APIs. Does not create a shop/product or publish test assets.
State/output stay in ignored .local. Storage check removes only its own UUID key.
"""
import argparse
import io
import json
from pathlib import Path
import time
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.db.repository import Repo
from app.db.session import SessionLocal
from app.integrations.media_generation.zhipu import ZhipuMediaProvider
from app.integrations.storage import minio
from app.services.files import inspect_file
from app.workers.handlers.media import download


def verify(kind):
    folder = Path(__file__).resolve().parents[1] / '.local/zhipu-verification'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (kind + '-task.json')
    state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    def save():
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(state, indent=2), encoding='utf-8')
        temp.replace(path)
    with SessionLocal() as db:
        repo = Repo(db)
        settings = repo.get('SystemSettings', 'singleton')
        config = repo.get('ModelConfig', settings[kind + '_model_config_id'])
    data = {'request': {'width': 1280, 'height': 1280, 'count': 1, 'duration_sec': 5, 'resolution': '1080p'},
            'creative_plan': {'content': {'generation_prompt': 'A plain white ceramic mug on a light wooden table, soft daylight, clean studio product photography, no logo, no people.' if kind == 'image' else 'A plain white ceramic mug on a light wooden table. Soft morning light. One slow gentle camera push-in. Clean product showcase, no people, no captions.',
                'negative_prompt': None, 'aspect_ratio': '1:1' if kind == 'image' else '16:9'}}, 'reference_files': []}
    adapter = ZhipuMediaProvider()
    adapter.validate(kind, data['request'], config)
    adapter.validate_input(kind, data)
    if state.get('submitting') and not state.get('task_id'):
        raise ApiError(409, 'PROVIDER_SUBMISSION_UNKNOWN', 'Saved submission is ambiguous; do not submit another paid task automatically.')
    if not state.get('task_id'):
        state['submitting'] = True
        save()
        try:
            state.update(adapter.submit(kind, adapter.payload(kind, data, str(uuid4())), config, str(uuid4())))
        except ApiError as error:
            state['error_code'] = error.code
            if error.code != 'PROVIDER_SUBMISSION_UNKNOWN': state['submitting'] = False
            save()
            raise
        state['submitting'] = False
        save()
        print(kind + ': provider accepted task', flush=True)
    deadline = time.monotonic() + 1200
    while not state.get('result_url'):
        if time.monotonic() > deadline:
            print(kind + ': still processing; saved task id can be queried again', flush=True)
            return
        result = adapter.query(state['task_id'], config)
        status = result.get('task_status')
        if status == 'FAIL':
            raise ApiError(422, 'PROVIDER_TASK_FAILED', 'Provider confirmed generation failure')
        if status == 'SUCCESS':
            state['result_url'] = adapter.result_url(kind, result)
            save()
        else:
            print(kind + ': ' + str(status), flush=True)
            time.sleep(10)
    raw = download(state['result_url'], 20971520 if kind == 'image' else 524288000)
    stream = io.BytesIO(raw)
    mime, width, height, duration = inspect_file(stream, 'generated', 'media', len(raw), settings)
    assert mime.startswith(kind + '/')
    ext = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp', 'video/mp4': '.mp4'}[mime]
    output = folder / (kind + '-result' + ext)
    output.write_bytes(raw)
    key = 'verification/' + str(uuid4())
    bucket = get_settings().minio_bucket
    try:
        minio.put(stream, key, len(raw), mime)
        with httpx.Client(timeout=120, trust_env=False) as client:
            response = client.get(minio.access_url(bucket, key))
            assert response.status_code == 200 and response.content == raw
    finally:
        minio.client().remove_object(bucket, key)
    state.update(verified=True, width=width, height=height, duration=duration, byte_size=len(raw), output_file=str(output))
    save()
    print(f'{kind}: generated {width}x{height}, duration={duration}, bytes={len(raw)}; private MinIO upload/read passed', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['image', 'video'])
    args = parser.parse_args()
    try:
        verify(args.kind)
    except ApiError as exc:
        print(exc.code + ': ' + exc.message, flush=True)
        raise SystemExit(1) from None
