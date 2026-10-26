from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from itertools import product as combinations

from app.core.exceptions import ApiError
from app.rules.budgets import ensure_budget_available, split_money, validate_budget, validate_experiment_plan
from app.rules.transitions import EXPERIMENT_TRANSITIONS, require_transition
from app.services.catalog import now_iso, owned, parse_time, read_round
from app.services.common import Result

SHOP_TZ = timezone(timedelta(hours=8))


def _current_recommendation(ctx, ref, round_id):
    recommendation = owned(ctx, 'AdRecommendation', ref['id'], lock=True)
    if recommendation['round_id'] != round_id:
        raise ApiError(404, 'NOT_FOUND', '投放建议不属于当前轮次')
    if recommendation['version'] != ref['version'] or recommendation['confirm_status'] != 'confirmed':
        raise ApiError(409, 'RECOMMENDATION_NOT_CONFIRMED', '必须引用投放建议当前已确认的批准版本；旧草案请取消后重新生成')
    validate_budget(recommendation['content'], recommendation['budget_cap'], recommendation['daily_cap'], recommendation['duration_days'])
    return recommendation


def _validate_dependencies(ctx, experiment, *, exact_versions=True):
    asset = owned(ctx, 'Asset', experiment['related_asset']['id'])
    link = owned(ctx, 'PromotionLink', experiment['related_link_id'])
    if asset['round_id'] != experiment['round_id'] or link['round_id'] != experiment['round_id']:
        raise ApiError(404, 'NOT_FOUND', '素材和链接必须属于本轮次')
    if asset['review_status'] != 'approved' or (exact_versions and asset['version'] != experiment['related_asset']['version']):
        raise ApiError(409, 'ASSET_NOT_APPROVED', '素材必须为当前已审核通过版本')
    if link['status'] != 'active':
        raise ApiError(409, 'LINK_DISABLED', '实验链接必须启用')
    if experiment['execution_mode'] == 'real' and asset['execution_mode'] != 'real':
        raise ApiError(409, 'DEMO_REAL_MIXED', '真实实验不能使用演示素材')
    if experiment.get('title_plan'):
        plan = owned(ctx, 'CreativePlan', experiment['title_plan']['id'])
        if plan['round_id'] != experiment['round_id']:
            raise ApiError(404, 'NOT_FOUND', '标题方案不属于本轮次')
        if plan['plan_type'] != 'title' or plan['status'] != 'selected' or (exact_versions and plan['version'] != experiment['title_plan']['version']):
            raise ApiError(409, 'TITLE_PLAN_NOT_SELECTED', '必须引用当前已选定的标题方案版本')


def _generation_context(ctx, body):
    ctx.require_product(ctx.params['product_id'], active=True, lock=True)
    ctx.require_round(ctx.params['product_id'], body['round_id'])
    recommendation = _current_recommendation(ctx, body['recommendation'], body['round_id'])
    mode = recommendation['provenance']['execution_mode']
    if len(body['related_link_ids']) != len(set(body['related_link_ids'])):
        raise ApiError(422, 'DUPLICATE_LINK', '推广链接不能重复')
    for identifier in body['related_link_ids']:
        link = owned(ctx, 'PromotionLink', identifier)
        if link['round_id'] != body['round_id']:
            raise ApiError(404, 'NOT_FOUND', '推广链接不属于本轮次')
        if link['status'] != 'active':
            raise ApiError(409, 'LINK_DISABLED', '推广链接必须处于启用状态')
    tests = recommendation['content']['creative_tests']
    count = body.get('count', min(len(tests), 10))
    if count > len(tests) * len(body['related_link_ids']):
        raise ApiError(422, 'EXPERIMENT_COUNT_INVALID', '实验数量超过创意测试与链接的可用组合数')
    for test in tests:
        _validate_dependencies(ctx, {'related_asset': test['asset'], 'related_link_id': body['related_link_ids'][0], 'title_plan': test['title_plan'], 'round_id': body['round_id'], 'execution_mode': mode})
    return recommendation, count, mode


def generate(ctx):
    from app.services.jobs import submit
    recommendation, count, mode = _generation_context(ctx, ctx.body)
    body = {**ctx.body, 'count': count, 'planned_start_date': datetime.now(SHOP_TZ).date().isoformat()}
    return Result(submit(ctx, 'ad_experiment', body, execution_mode=mode), status=202)


def execute_experiments(ctx, job, input):
    """Worker在同一事务内执行；无模型调用、无外部平台投放。"""
    recommendation, count, mode = _generation_context(ctx, input)
    content, plan = recommendation['content'], recommendation['content']['budget_plan']
    budgets = split_money(plan['total_amount'], count)
    # 使用提交时固化日期，重试不会把计划日期悄悄推后。
    start = datetime.fromisoformat(input['planned_start_date']).date()
    end = start + timedelta(days=plan['duration_days'] - 1)
    resources = []
    pairs = list(combinations(content['creative_tests'], input['related_link_ids']))[:count]
    for index, (test, link_id) in enumerate(pairs):
        amount = Decimal(budgets[index])
        daily = (amount / plan['duration_days']).quantize(Decimal('0.01'), rounding=ROUND_CEILING)
        if daily > Decimal(plan['daily_cap']):
            raise ApiError(422, 'BUDGET_CONSTRAINT_VIOLATION', '实验日预算超过已批准上限')
        audience = content['audience_segments'][index % len(content['audience_segments'])]
        data = {'product_id': ctx.params['product_id'], 'round_id': input['round_id'],
            'experiment_name': f'实验 {index + 1} · {test["comparison_dimension"]}',
            'target_text': content['objective_text'], 'audience_text': audience['description'],
            'budget_amount': budgets[index], 'daily_cap': format(daily, '.2f'),
            'success_metric': test['success_metric'], 'target_value': test['target_value'], 'hypothesis_text': test['hypothesis'],
            'related_asset': test['asset'], 'related_link_id': link_id, 'title_plan': test['title_plan'],
            'planned_start_date': start.isoformat(), 'planned_end_date': end.isoformat(),
            'recommendation': input['recommendation'], 'experiment_status': 'draft', 'execution_mode': mode}
        validate_experiment_plan(data, recommendation)
        row = ctx.repo.create('AdExperiment', data)
        resources.append({'resource_type': 'ad_experiment', 'resource_id': row['id'], 'version': row['version']})
    return resources


def list_experiments(ctx):
    ctx.require_product(ctx.params['product_id'])
    if ctx.query.get('round_id'):
        read_round(ctx, ctx.query['round_id'])
    return ctx.collection('AdExperiment', {'product_id': ctx.params['product_id'], **{k: ctx.query[k] for k in ('round_id', 'experiment_status') if k in ctx.query}})


def get_experiment(ctx):
    ctx.require_product(ctx.params['product_id'])
    return owned(ctx, 'AdExperiment', ctx.params['experiment_id'])


def patch_experiment(ctx):
    product = ctx.require_product(ctx.params['product_id'], lock=True)
    row = owned(ctx, 'AdExperiment', ctx.params['experiment_id'], lock=True)
    ctx.require_round(product['id'], row['round_id'])
    ctx.check_version(row)
    if 'experiment_status' not in ctx.body:
        if row['experiment_status'] != 'draft':
            raise ApiError(409, 'EXPERIMENT_PLAN_FROZEN', '只有草案可以编辑计划；确认后请取消并重新生成')
        merged = {**row, **ctx.body}
        recommendation = _current_recommendation(ctx, row['recommendation'], row['round_id'])
        validate_experiment_plan(merged, recommendation)
        _validate_dependencies(ctx, merged)
        return ctx.repo.update('AdExperiment', row['id'], ctx.body)
    target = ctx.body['experiment_status']
    require_transition(row['experiment_status'], target, EXPERIMENT_TRANSITIONS)
    if not ctx.body['remark'].strip():
        raise ApiError(422, 'TRANSITION_REMARK_REQUIRED', '状态变更必须填写说明')
    allowed_time_fields = {'running': {'actual_start_at', 'external_campaign_id'}, 'finished': {'actual_end_at'}, 'cancelled': {'actual_end_at'}, 'confirmed': set()}[target]
    if any(k in ctx.body and k not in allowed_time_fields for k in ('actual_start_at', 'actual_end_at', 'external_campaign_id')):
        raise ApiError(422, 'TRANSITION_FIELDS_INVALID', '该状态转换不能修改所提交的执行时间或外部计划标识')
    changes = {'experiment_status': target, 'last_transition_remark': ctx.body['remark']}
    now = datetime.now(timezone.utc)
    if target == 'confirmed':
        if ctx.user['role'] not in {'admin', 'operator'}:
            raise ApiError(403, 'FORBIDDEN', '没有确认投放实验的权限')
        recommendation = _current_recommendation(ctx, row['recommendation'], row['round_id'])
        _validate_dependencies(ctx, row)
        validate_experiment_plan(row, recommendation)
        siblings = [r for r in ctx.repo.list('AdExperiment', {'product_id': product['id']}) if r['recommendation']['id'] == recommendation['id']]
        ensure_budget_available(row, recommendation, siblings)
        changes.update(confirmed_by=ctx.user['id'], confirmed_at=now_iso())
    elif target == 'running':
        if product['status'] != 'active':
            raise ApiError(409, 'PRODUCT_NOT_ACTIVE', '只有启用商品可以启动投放实验')
        _validate_dependencies(ctx, row, exact_versions=False)
        start = parse_time(ctx.body['actual_start_at'])
        if start > now:
            raise ApiError(422, 'ACTUAL_TIME_IN_FUTURE', '实际开始时间不能在未来')
        changes.update(actual_start_at=ctx.body['actual_start_at'], external_campaign_id=ctx.body['external_campaign_id'])
    elif target == 'finished' or (target == 'cancelled' and row.get('actual_start_at')):
        if not ctx.body.get('actual_end_at'):
            raise ApiError(422, 'ACTUAL_END_REQUIRED', '结束或取消已启动实验必须填写实际结束时间')
        end = parse_time(ctx.body['actual_end_at'])
        if end > now or end < parse_time(row['actual_start_at']):
            raise ApiError(422, 'ACTUAL_TIME_INVALID', '实际结束时间不得早于开始或晚于当前时间')
        changes['actual_end_at'] = ctx.body['actual_end_at']
    elif target == 'cancelled' and 'actual_end_at' in ctx.body:
        raise ApiError(422, 'ACTUAL_TIME_INVALID', '未启动实验不能填写实际结束时间')
    return ctx.repo.update('AdExperiment', row['id'], changes)
