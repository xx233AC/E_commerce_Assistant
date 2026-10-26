import copy
from datetime import timedelta
from uuid import uuid4
from app.core.exceptions import ApiError
from app.core.security import utcnow
from app.services.common import Result

TERMINAL={'succeeded','failed','cancelled','timeout'}


def timestamp(): return utcnow().isoformat().replace('+00:00','Z')


def event(ctx,job,event_type,message):
    ctx.get('GenerationJob',job['id'],lock=True)
    seq=ctx.repo.count('JobEvent',{'job_id':job['id']})+1
    return ctx.repo.create('JobEvent',{'job_id':job['id'],'sequence':seq,'attempt':job['attempts'],'event_type':event_type,'event_message':message})


def accepted(job):
    if job['product_id']:
        path=f"/api/v1/products/{job['product_id']}/generation-jobs/{job['id']}"
    else: path=f"/api/v1/workspace/jobs/{job['id']}"
    return {'job':job,'poll_url':path,'events_url':path+'/events','poll_after_seconds':2}


def submit(ctx,kind,body,model_config_id=None,execution_mode='real',creative_plan=None,dispatch=True):
    data=copy.deepcopy(body)
    product_id=ctx.params.get('product_id') or data.get('product_id')
    round_id=data.get('round_id') or data.get('request',{}).get('round_id')
    if product_id: ctx.require_product(product_id,lock=True)
    if round_id: ctx.require_round(product_id,round_id)
    config=ctx.get('ModelConfig',model_config_id) if model_config_id else None
    if config:
        if not config['enabled']: raise ApiError(422,'MODEL_NOT_CONFIGURED','模型配置已停用')
        data.setdefault('model_config',config)
    settings=ctx.get('SystemSettings','singleton')
    demo_flag = 'demo_data_enabled' if kind=='demo_data' else 'demo_generation_enabled'
    if execution_mode=='demo' and not settings[demo_flag]:
        raise ApiError(422,'MODEL_CAPABILITY_UNSUPPORTED','未启用演示生成')
    queue=ctx.get('QueueSettings','singleton')
    data['_timeout_seconds']=queue['job_timeout_sec']
    job=ctx.repo.create('GenerationJob',{
        'product_id':product_id,'round_id':round_id,'creative_plan_id':creative_plan.get('id') if creative_plan else None,
        'creative_plan_version':creative_plan.get('version') if creative_plan else None,
        'job_kind':kind,'job_status':'pending','dispatch_status':'queued' if dispatch else 'awaiting_dispatch',
        'execution_mode':execution_mode,'attempts':0,'max_attempts':queue['max_attempts'],
        'cancellation_requested':False,'result_resources':[],'progress':0,
        'model_config_id':model_config_id,'model_config_version':config['version'] if config else None,
        'source_url':data.get('source_url') or data.get('url'),'submitted_by':ctx.user.get('id'),
        'queued_at':timestamp() if dispatch else None,
        'deadline_at':(utcnow()+timedelta(hours=24)).isoformat().replace('+00:00','Z'),
    })
    ctx.repo.create('JobRuntime',{'job_id':job['id'],'input':data,'provider_state':{},'result_state':{}})
    if dispatch: event(ctx,job,'enqueued','任务已进入后台队列')
    return accepted(job)


def get_job(ctx):
    job=ctx.get('GenerationJob',ctx.params.get('job_id') or ctx.params.get('task_id'))
    if ctx.params.get('product_id') and job['product_id']!=ctx.params['product_id']: raise ApiError(404,'NOT_FOUND','任务不属于此商品')
    if not ctx.params.get('product_id') and job['product_id'] is not None: raise ApiError(404,'NOT_FOUND','请通过商品任务接口访问')
    return job


def list_jobs(ctx):
    filters={'product_id':ctx.params['product_id']}
    for key in ('round_id','job_kind','job_status','execution_mode','creative_plan_id'):
        if key in ctx.query: filters[key]=ctx.query[key]
    return ctx.collection('GenerationJob',filters)


def events(ctx):
    job=get_job(ctx)
    rows=ctx.repo.list('JobEvent',{'job_id':job['id']},order='sequence')
    if ctx.query.get('after_sequence'): rows=[r for r in rows if r['sequence']>ctx.query['after_sequence']]
    return ctx.page(rows)


def retry(ctx):
    job=get_job(ctx)
    if job['round_id']: ctx.require_round(job['product_id'],job['round_id'])
    job=ctx.get('GenerationJob',job['id'],lock=True);ctx.check_version(job)
    if job['job_status'] not in ('failed','timeout'): raise ApiError(409,'JOB_TERMINAL','只有失败或超时任务可以重试')
    if job['attempts']>=job['max_attempts']: raise ApiError(409,'MAX_ATTEMPTS_EXCEEDED','已达到最大尝试次数')
    if job['error_code']=='PROVIDER_SUBMISSION_UNKNOWN': raise ApiError(409,'RECONCILIATION_REQUIRED','供应商是否受理尚未确认，请先核对')
    if job['job_kind'] in {'image','video'}:
        runtime=ctx.get('JobRuntime',job['id'],lock=True)
        records=runtime['provider_state'].get('media',[])
        if any(item.get('submitting') and not item.get('task_id') for item in records):
            raise ApiError(409,'RECONCILIATION_REQUIRED','供应商是否受理尚未确认，请先核对，避免重复扣费')
        if any(item.get('status')=='FAIL' for item in records):
            raise ApiError(409,'PROVIDER_TASK_FAILED','智谱已确认生成失败，请修改方案后重新发起生成')
    job=ctx.repo.update('GenerationJob',job['id'],{'job_status':'pending','dispatch_status':'queued','error_code':None,'error_message':None,
        'finished_at':None,'next_run_at':None,'queued_at':timestamp(),'deadline_at':(utcnow()+timedelta(hours=24)).isoformat().replace('+00:00','Z')})
    event(ctx,job,'retry_requested','用户请求使用原输入快照重试')
    return Result(accepted(job),status=202)


def cancel(ctx):
    job=get_job(ctx)
    if job['round_id']: ctx.require_round(job['product_id'],job['round_id'])
    job=ctx.get('GenerationJob',job['id'],lock=True);ctx.check_version(job)
    if job['job_status'] in TERMINAL: raise ApiError(409,'JOB_TERMINAL','任务已结束')
    changes={'cancellation_requested':True}
    if job['job_status']=='pending':changes.update(job_status='cancelled',finished_at=timestamp(),error_code='USER_CANCELLED',error_message='用户取消任务')
    job=ctx.repo.update('GenerationJob',job['id'],changes)
    event(ctx,job,'cancelled' if job['job_status']=='cancelled' else 'cancellation_requested',ctx.body['reason'])
    return Result(accepted(job),status=202)


def sweep(ctx): return Result(submit(ctx,'timeout_sweep',ctx.body),status=202)
def monitor_sweep(ctx): return Result(submit(ctx,'competitor_monitor_sweep',ctx.body),status=202)

HANDLERS={
    'GET /products/{product_id}/generation-jobs':list_jobs,
    'GET /products/{product_id}/generation-jobs/{job_id}':get_job,
    'GET /products/{product_id}/generation-jobs/{job_id}/events':events,
    'POST /products/{product_id}/generation-jobs/{job_id}/retry':retry,
    'POST /products/{product_id}/generation-jobs/{job_id}/cancel':cancel,
    'GET /workspace/jobs/{job_id}':get_job,'GET /workspace/jobs/{job_id}/events':events,
    'POST /workspace/generation-jobs/sweep-timeouts':sweep,
    'POST /workspace/competitor-monitors/run-due':monitor_sweep,
}
