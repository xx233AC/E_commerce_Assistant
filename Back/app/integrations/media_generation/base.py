"""Registry for official media adapters and explicit future extensions."""
from typing import Protocol
from app.core.exceptions import ApiError


class MediaProvider(Protocol):
    def validate(self,kind,request,config): ...
    def validate_input(self,kind,data): ...
    def submit(self,kind,request,config,idempotency_key): ...
    def query(self,provider_task_id,config): ...


PROVIDERS = {}


def get_provider(config):
    adapter=PROVIDERS.get(config['provider'])
    if adapter is None and config['provider'] in {'image_provider', 'video_provider'}:
        from app.integrations.media_generation.zhipu import BASE_URL, ZhipuMediaProvider
        if config['base_url'].rstrip('/') == BASE_URL:
            adapter = ZhipuMediaProvider()
    if adapter is None:
        raise ApiError(422,'MODEL_CAPABILITY_UNSUPPORTED','此供应商尚未接入，请选择已配置的智谱媒体模型或上传真实素材')
    return adapter
