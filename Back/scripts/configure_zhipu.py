"""Register official media models without storing secrets in PostgreSQL."""
from app.core.contract import validate_schema
from app.db.repository import Repo
from app.db.session import SessionLocal
from app.integrations.media_generation.zhipu import BASE_URL, capability
from app.llm.client import get_secret
from app.services.settings import validate_model


def configure(repo):
    if not get_secret('ZHIPU_API_KEY'):
        raise RuntimeError('Set ZHIPU_API_KEY in Back/.env first')
    defaults = {}
    for kind, model in [('image', 'glm-image'), ('video', 'cogvideox-3')]:
        data = {'name': '智谱 ' + model, 'provider': kind + '_provider', 'base_url': BASE_URL,
                'model_name': model, 'capabilities': [capability(kind)], 'enabled': True,
                'execution_mode': 'real', 'request_timeout_sec': 120, 'secret_env_name': 'ZHIPU_API_KEY'}
        validate_model(data)
        found = repo.list('ModelConfig', {'provider': kind + '_provider', 'model_name': model, 'base_url': BASE_URL})
        config = repo.update('ModelConfig', found[0]['id'], data) if found else repo.create('ModelConfig', data)
        validate_schema('ModelConfig', config)
        defaults[kind + '_model_config_id'] = config['id']
    repo.update('SystemSettings', 'singleton', defaults)
    return defaults


if __name__ == '__main__':
    with SessionLocal.begin() as db:
        configure(Repo(db))
    print('Configured glm-image and cogvideox-3. Text model unchanged; secrets remain in environment only.')
