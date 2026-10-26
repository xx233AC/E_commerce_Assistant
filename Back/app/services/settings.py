import os
from urllib.parse import urlsplit
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.contract import validate_schema
from app.core.security import utcnow
from app.integrations.public_pages.url_policy import validate_public_url

TEXT_CAPABILITY = {'capability':'text','supported_aspect_ratios':[],
                   'max_duration_sec':None,'max_images_per_request':None,
                   'supported_resolutions':[],'supported_image_sizes':[]}


def supports(config, capability):
    return any(item['capability'] == capability for item in config['capabilities'])


def system(ctx): return ctx.get('SystemSettings','singleton')
def queue(ctx): return ctx.get('QueueSettings','singleton')


def validate_model(data):
    validate_schema('ModelConfigCreate',{k:v for k,v in data.items() if k not in ('id','version','created_at','updated_at','secret_configured') and not(k=='secret_env_name' and v is None)})
    capabilities = [item['capability'] for item in data['capabilities']]
    if len(capabilities) != len(set(capabilities)):
        raise ApiError(422,'VALIDATION_ERROR','模型能力不能重复')
    if (data['provider']=='demo') != (data['execution_mode']=='demo'):
        raise ApiError(422,'MODEL_CAPABILITY_UNSUPPORTED','演示供应商必须与演示模式对应，真实模式不能使用演示供应商')
    try:
        url=urlsplit(data['base_url'])
        url.port
    except ValueError:
        raise ApiError(422,'UNSUPPORTED_PUBLIC_URL','模型服务基础地址格式无效') from None
    if url.username or url.password or url.query or url.fragment:
        raise ApiError(422,'UNSUPPORTED_PUBLIC_URL','模型服务基础地址不得包含凭据、查询参数或片段')
    if data['execution_mode']=='real':
        validate_public_url(data['base_url'],provider=True)
        if not os.environ.get(data.get('secret_env_name','')):
            raise ApiError(422,'MODEL_NOT_CONFIGURED','密钥引用的服务端环境变量尚未配置')
    elif not get_settings().demo_enabled:
        raise ApiError(422,'MODEL_CAPABILITY_UNSUPPORTED','服务端未启用演示模式')


def list_models(ctx): return ctx.collection('ModelConfig')
def model(ctx): return ctx.get('ModelConfig',ctx.params['config_id'])


def create_model(ctx):
    data={**ctx.body,'enabled':ctx.body.get('enabled',True)}
    validate_model(data)
    return ctx.repo.create('ModelConfig',data)


def patch_model(ctx):
    old=ctx.get('ModelConfig',ctx.params['config_id'],lock=True);ctx.check_version(old)
    validate_model({**old,**ctx.body})
    return ctx.repo.update('ModelConfig',old['id'],ctx.body)


def patch_system(ctx):
    old=ctx.get('SystemSettings','singleton',lock=True);ctx.check_version(old)
    for field,capability in [('text_model_config_id','text'),('image_model_config_id','image'),('video_model_config_id','video')]:
        if ctx.body.get(field):
            config=ctx.get('ModelConfig',ctx.body[field])
            if not config['enabled'] or not supports(config,capability):
                raise ApiError(422,'MODEL_CAPABILITY_UNSUPPORTED','模型配置未启用或不具备对应能力')
    if any(ctx.body.get(k) for k in ('demo_generation_enabled','demo_data_enabled')) and not get_settings().demo_enabled:
        raise ApiError(422,'MODEL_CAPABILITY_UNSUPPORTED','服务端未启用演示模式')
    return ctx.repo.update('SystemSettings','singleton',ctx.body)


def patch_queue(ctx):
    old=ctx.get('QueueSettings','singleton',lock=True);ctx.check_version(old)
    return ctx.repo.update('QueueSettings','singleton',ctx.body)


def initialize(repo):
    if not repo.get('QueueSettings','singleton'):
        repo.create('QueueSettings',{'text_concurrency':2,'image_concurrency':1,'video_concurrency':1,'max_attempts':3,'job_timeout_sec':1800})
    if not repo.get('SystemSettings','singleton'):
        model_id=None
        if os.environ.get('DEEPSEEK_API_KEY'):
            model_id=repo.create('ModelConfig',{'name':'DeepSeek Flash','provider':'openai_compatible','base_url':'https://api.deepseek.com','model_name':'deepseek-flash','capabilities':[TEXT_CAPABILITY],'enabled':True,'execution_mode':'real','request_timeout_sec':180,'secret_env_name':'DEEPSEEK_API_KEY'})['id']
        repo.create('SystemSettings',{'text_model_config_id':model_id,'image_model_config_id':None,'video_model_config_id':None,
            'demo_generation_enabled':False,'demo_data_enabled':False,'max_upload_image_bytes':20971520,'max_upload_video_bytes':524288000,'max_import_rows':10000})

HANDLERS={'GET /settings/model-configs':list_models,'POST /settings/model-configs':create_model,
          'GET /settings/model-configs/{config_id}':model,'PATCH /settings/model-configs/{config_id}':patch_model,
          'GET /settings/system':system,'PATCH /settings/system':patch_system,'GET /settings/queue':queue,'PATCH /settings/queue':patch_queue}
