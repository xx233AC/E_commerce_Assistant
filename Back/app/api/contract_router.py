"""Bind explicit business handlers to the shared contract; centralize protocol checks."""
import hashlib
import hmac
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.contract import SPEC, resolve, validate_value
from app.core.exceptions import ApiError, unauthorized
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.schemas.user import UserRead
from app.services.auth import authenticate
from app.services.common import Context, Page, Result, RawResult

logger = logging.getLogger(__name__)


def cleanup_uncommitted_uploads(objects):
    """Delete only newly created objects whose absence in PostgreSQL is confirmed.

    A lost connection during commit leaves an ambiguous outcome. In that case a
    fresh database read prevents deleting a file that was actually committed.
    """
    from app.db.repository import Repo
    from app.integrations.storage import minio
    for item in objects:
        try:
            with SessionLocal() as check:
                if Repo(check).get('FileStorage', item['file_id']) is not None:
                    continue
            minio.client().remove_object(item['bucket'], item['object_name'])
        except Exception:
            logger.warning('Upload cleanup deferred file_id=%s', item['file_id'])


def integrity_conflict(exc):
    # PostgreSQL constraints are the final guard when distinct requests race.
    # Expose stable contract codes, never SQL text or bound request parameters.
    constraint = getattr(getattr(exc.orig, 'diag', None), 'constraint_name', None)
    known = {
        'uq_stores_singleton_key': ('STORE_ALREADY_EXISTS', '本系统只允许一个店铺'),
        'uq_users_username': ('DUPLICATE_USERNAME', '用户名已存在'),
        'uq_skus_code': ('DUPLICATE_SKU_CODE', 'SKU 编码已存在'),
        'uq_mapping_external_sku': ('DUPLICATE_PLATFORM_MAPPING', '该平台外部 SKU 已存在映射'),
        'uq_round_active_product': ('ACTIVE_ROUND_EXISTS', '该商品已有进行中的运营轮次'),
        'uq_performance_product_day': ('DUPLICATE_PERFORMANCE_RECORD', '此商品当天的经营记录已存在'),
        'uq_performance_experiment_day': ('DUPLICATE_PERFORMANCE_RECORD', '此实验当天的经营记录已存在'),
    }
    code, message = known.get(constraint, ('BUSINESS_CONFLICT', '资源标识重复或业务约束冲突，请刷新后检查'))
    return ApiError(409, code, message)


def parse_query(request, operation):
    allowed = {p['name']:p for raw in operation.get('parameters', []) if (p:=resolve(raw)).get('in') == 'query'}
    if set(request.query_params) - set(allowed):
        raise ApiError(422,'VALIDATION_ERROR','包含未声明的查询字段')
    values = {}
    for name,p in allowed.items():
        schema = resolve(p['schema'])
        if name not in request.query_params:
            if p.get('required'):
                raise ApiError(422,'VALIDATION_ERROR','缺少必填查询参数：'+name)
            if 'default' in schema:
                values[name]=schema['default']
            continue
        raw = request.query_params.get(name)
        try:
            if schema.get('type') == 'integer': value=int(raw)
            elif schema.get('type') == 'boolean':
                if raw not in ('true','false'): raise ValueError()
                value=raw=='true'
            elif schema.get('type') == 'array': value=[x for r in request.query_params.getlist(name) for x in r.split(',')]
            else: value=raw
        except ValueError:
            raise ApiError(422,'VALIDATION_ERROR','查询参数格式不正确') from None
        validate_value(schema,value)
        values[name]=value
    return values


def ownership(ctx):
    product_id=ctx.params.get('product_id')
    if product_id:
        # Ownership checks must remain read-only before the idempotency lock.
        # Business handlers take row locks only after acquiring that lock.
        ctx.require_product(product_id)
    if ctx.params.get('store_id'):
        ctx.get('Store',ctx.params['store_id'])
    mappings={'sku_id':'Sku','mapping_id':'PlatformMapping','competitor_id':'Competitor','round_id':'OperatingRound',
              'diagnosis_id':'Diagnosis','creative_plan_id':'CreativePlan','job_id':'GenerationJob','task_id':'GenerationJob',
              'asset_id':'Asset','link_id':'PromotionLink','recommendation_id':'AdRecommendation',
              'experiment_id':'AdExperiment','record_id':'PerformanceRecord','report_id':'ReviewReport','account_id':'PlatformAccount',
              'revision_id':'ResourceRevision','file_id':'FileObject','config_id':'ModelConfig','import_id':'ImportBatch'}
    for key,kind in mappings.items():
        if key not in ctx.params: continue
        row=ctx.get(kind,ctx.params[key])
        resource_product = row.get('product_id') if key != 'revision_id' else row.get('resource',{}).get('product_id')
        if product_id and resource_product != product_id:
            raise ApiError(404,'NOT_FOUND','资源不属于此商品')
        if key=='account_id' and row.get('store_id') != ctx.params['store_id']:
            raise ApiError(404,'NOT_FOUND','账号不属于此店铺')
    if 'user_id' in ctx.params:
        from app.models.user import User
        if ctx.db.get(User, UUID(ctx.params['user_id'])) is None:
            raise ApiError(404,'NOT_FOUND','用户不存在')


def canonical_path(request, operation):
    path = request.scope['route'].path
    values = dict(request.path_params)
    for raw in operation.get('parameters', []):
        param = resolve(raw)
        if param.get('in') != 'path':
            continue
        name = param['name']
        value = values[name]
        if resolve(param['schema']).get('format') == 'uuid':
            value = str(UUID(value))
            values[name] = value
        path = path.replace('{' + name + '}', quote(value, safe=''))
    return path, values


def check_identity(db, request, operation):
    if operation.get('security', SPEC.get('security')) == []:
        return None
    scheme, _, token = request.headers.get('authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token:
        raise unauthorized('请先登录')
    auth = authenticate(db, token)
    if auth.user.role not in operation.get('x-roles', []):
        raise ApiError(403, 'FORBIDDEN', '当前角色没有此操作权限')
    return auth


def preflight_upload(request, operation):
    # A large multipart body must not be read before identity/role checks.
    with SessionLocal() as db:
        check_identity(db, request, operation)


@contextmanager
def protocol_session():
    """Keep one checked-out connection until its session advisory lock is released.

The fingerprint is committed before business writes, while the advisory lock spans
both transactions. A failed/crashed request leaves a retryable fingerprint, never
a cached error response and never a window for changing the request body.
"""
    db = SessionLocal()
    connection = None
    bind = db.get_bind()
    if isinstance(bind, Engine):
        connection = bind.connect()
        db.bind = connection
    try:
        yield db
    finally:
        pending_objects = db.info.pop('pending_storage_objects', [])
        lock = db.info.pop('idempotency_lock', None)
        if lock is not None:
            try:
                db.rollback()
                db.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': lock})
                db.commit()
            except Exception:
                # A connection with an uncertain session lock must never re-enter the pool.
                db.invalidate()
                if connection is not None:
                    connection.invalidate()
        db.close()
        if connection is not None:
            connection.close()
        cleanup_uncommitted_uploads(pending_objects)


def execute(request, operation, handler, body, query, upload, file_hash):
    with protocol_session() as db:
        auth=check_identity(db,request,operation)
        for raw in operation.get('parameters',[]):
            param=resolve(raw)
            if param.get('in')=='path': validate_value(param['schema'],request.path_params[param['name']])
        path, path_params = canonical_path(request, operation)
        query = parse_query(request, operation)
        ctx=Context(db=db,user=UserRead.model_validate(auth.user).model_dump(mode='json') if auth else {},
                    params=path_params,query=query,body=body,headers=request.headers,
                    request_id=request.state.request_id,session_id=str(auth.session.id) if auth else None,
                    request_method=request.method,client_ip=request.client.host if request.client else '',
                    base_url=get_settings().public_base_url,upload=upload,file_hash=file_hash)
        ownership(ctx)
        parsing_error = getattr(request.state, 'parsing_error', None)
        if parsing_error:
            raise parsing_error
        params=[resolve(p) for p in operation.get('parameters',[])]
        idem=any(p.get('name')=='Idempotency-Key' for p in params)
        record=None
        fingerprint=None
        if idem:
            key=request.headers.get('idempotency-key')
            if not key: raise ApiError(400,'IDEMPOTENCY_KEY_REQUIRED','缺少 Idempotency-Key')
            try: key=str(UUID(key))
            except ValueError: raise ApiError(400,'INVALID_IDEMPOTENCY_KEY','幂等键须为UUID') from None
            canonical=json.dumps({'body':body,'file_hash':file_hash,'file_content_type':upload.content_type if upload else None},sort_keys=True,separators=(',',':'),ensure_ascii=False)
            fingerprint=hmac.new(get_settings().jwt_secret.get_secret_value().encode(),canonical.encode(),hashlib.sha256).hexdigest()
            scope='|'.join((ctx.user['id'],request.method,path,key))
            lock=int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8],'big',signed=True)
            if not db.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':lock}):
                raise ApiError(409,'IDEMPOTENCY_IN_PROGRESS','相同请求仍在处理，请稍后查询')
            db.info['idempotency_lock'] = lock
            found=ctx.repo.list('IdempotencyRecord',{'user_id':ctx.user['id'],'method':request.method,'path':path,'key':key})
            if found:
                record=found[0]
                if datetime.fromisoformat(record['expires_at'].replace('Z','+00:00')) <= utcnow():
                    ctx.repo.delete('IdempotencyRecord',record['id']); record=None
                elif record['fingerprint']!=fingerprint:
                    raise ApiError(409,'IDEMPOTENCY_KEY_REUSED','同一幂等键不能用于不同请求内容')
                elif record['status'] != 0:
                    saved=record['response']
                    payload=saved['body']
                    payload['meta']['request_id']=ctx.request_id
                    return JSONResponse(payload,status_code=record['status'],headers=saved.get('headers',{}))
            if record is None:
                record = ctx.repo.create('IdempotencyRecord', {
                    'user_id':ctx.user['id'],'method':request.method,'path':path,'key':key,
                    'fingerprint':fingerprint,'status':0,'response':{},'expires_at':utcnow()+timedelta(hours=24),
                })
            # Persist only the request fingerprint; business writes start afterwards.
            # A session advisory lock on the same fixed connection remains held.
            db.commit()
        if operation.get('requestBody'):
            content=resolve(operation['requestBody'])['content']
            schema=content['multipart/form-data' if upload else 'application/json']['schema']
            validate_value(schema,body)
        value=handler(ctx)
        if isinstance(value,RawResult):
            db.commit()
            db.info.pop('pending_storage_objects', None)
            return Response(value.body,status_code=value.status,media_type=value.media_type,headers=value.headers)
        default_status=next(int(s) for s in operation['responses'] if s.startswith('2'))
        result=value if isinstance(value,Result) else Result(value,status=default_status)
        meta={'request_id':ctx.request_id}
        if isinstance(result.data,Page):
            page=result.data
            meta.update(page=page.page,page_size=page.page_size,total=page.total,total_pages=(page.total+page.page_size-1)//page.page_size)
            data=page.items
        else: data=result.data
        payload={'data':data,'meta':meta}
        response_spec=resolve(operation['responses'][str(result.status)])
        schema=response_spec.get('content',{}).get('application/json',{}).get('schema')
        if schema:
            try: validate_value(schema,payload)
            except ApiError:
                raise ApiError(500,'RESPONSE_CONTRACT_MISMATCH','服务返回格式不符合接口契约') from None
        headers=dict(result.headers)
        if isinstance(data,dict) and 'version' in data: headers.setdefault('ETag','"'+str(data['version'])+'"')
        if result.status==202 and isinstance(data,dict) and data.get('poll_url'): headers['Location']=data['poll_url']
        if idem:
            ctx.repo.update('IdempotencyRecord',record['id'],{
                'status':result.status,'response':{'body':payload,'headers':headers},
            },bump=False)
        if request.method not in ('GET','HEAD') and auth:
            ctx.repo.create('AuditLog',{'actor_id':ctx.user['id'],'action':operation['operationId'][:100],
                'resource_type':operation.get('tags',['business'])[0],'resource_id':data.get('id') if isinstance(data,dict) else None,
                'resource_version':data.get('version') if isinstance(data,dict) else None,'request_id':ctx.request_id,
                'outcome':'succeeded','summary':operation.get('summary','业务操作')})
        db.commit()
        db.info.pop('pending_storage_objects', None)
        return JSONResponse(payload,status_code=result.status,headers=headers)


def make_endpoint(operation,handler):
    async def endpoint(request:Request):
        body={}; upload=None; file_hash=None; query=None
        if operation.get('requestBody'):
            content=resolve(operation['requestBody'])['content']
            if 'multipart/form-data' in content:
                await run_in_threadpool(preflight_upload,request,operation)
                if request.headers.get('content-type','').split(';',1)[0].strip().lower() != 'multipart/form-data':
                    raise ApiError(415,'UNSUPPORTED_MEDIA_TYPE','请使用 multipart/form-data')
                form=await request.form()
                upload=form.get('file')
                body={k:v for k,v in form.items() if k!='file'}
                if upload is None or not hasattr(upload,'read'):
                    raise ApiError(422,'VALIDATION_ERROR','缺少上传文件')
                body['file']=upload.filename
                digest=hashlib.sha256(); length=0
                while chunk:=await upload.read(1024*1024):
                    length+=len(chunk)
                    if length>524288000: raise ApiError(413,'PAYLOAD_TOO_LARGE','上传文件过大')
                    digest.update(chunk)
                await upload.seek(0)
                file_hash=digest.hexdigest()
            else:
                if request.headers.get('content-type','').split(';',1)[0].strip().lower() != 'application/json':
                    request.state.parsing_error=ApiError(415,'UNSUPPORTED_MEDIA_TYPE','请使用 application/json')
                else:
                    try: body=await request.json()
                    except (ValueError,UnicodeError): request.state.parsing_error=ApiError(422,'VALIDATION_ERROR','JSON格式不正确')
        try:
            return await run_in_threadpool(execute,request,operation,handler,body,query,upload,file_hash)
        except IntegrityError as exc:
            raise integrity_conflict(exc) from None
    return endpoint


def build_router(handlers):
    router=APIRouter(prefix='/api/v1')
    missing=[]
    for path,path_item in SPEC['paths'].items():
        for method,operation in path_item.items():
            if method not in ('get','post','patch','put','delete'): continue
            if path.startswith('/auth/'): continue
            key=method.upper()+' '+path
            if key not in handlers:
                missing.append(key); continue
            router.add_api_route(path,make_endpoint(operation,handlers[key]),methods=[method.upper()],name=operation['operationId'])
            if path=='/r/{tracking_code}':
                router.add_api_route(path,make_endpoint(operation,handlers[key]),methods=['HEAD'],include_in_schema=False)
    if missing: raise RuntimeError('Unbound contract operations: '+', '.join(missing))
    return router
