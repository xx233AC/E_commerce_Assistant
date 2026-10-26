from app.core.exceptions import ApiError
from app.core.config import get_settings
from app.services.common import Result
from app.services.jobs import submit
from sqlalchemy import text


def check_enabled(ctx):
    settings = ctx.get('SystemSettings', 'singleton')
    if not get_settings().demo_enabled or not settings['demo_data_enabled']:
        raise ApiError(422, 'DEMO_DISABLED', '当前工作空间未启用演示初始化')


def check_empty(ctx):
    if any(ctx.repo.count(kind) for kind in ('Store', 'Product', 'FileObject', 'ImportBatch')):
        raise ApiError(409, 'DEMO_DATA_NOT_EMPTY', '已有业务数据，不能初始化演示数据')


def initialize(ctx):
    check_enabled(ctx)
    ctx.db.execute(text('SELECT pg_advisory_xact_lock(777001)'))
    check_empty(ctx)
    if ctx.repo.count('GenerationJob', {'job_kind':'demo_data','job_status':['pending','running']}):
        raise ApiError(409, 'IDEMPOTENCY_IN_PROGRESS', '演示初始化正在执行，请先查看已有任务')
    return Result(submit(ctx, 'demo_data', ctx.body, execution_mode='demo'), status=202)


def execute_demo(ctx, job, payload):
    check_enabled(ctx)
    ctx.db.execute(text('SELECT pg_advisory_xact_lock(777001)'))
    check_empty(ctx)
    from app.services.demo_dataset import execute_demo as build_dataset
    return build_dataset(ctx, job, payload)


HANDLERS = {'POST /workspace/demo-data': initialize}
