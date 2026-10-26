from datetime import date
from decimal import Decimal

from app.core.exceptions import ApiError


def validate_budget(content, budget_cap, daily_cap, duration_days):
    plan = content['budget_plan']
    total = Decimal(plan['total_amount'])
    daily = Decimal(plan['daily_cap'])
    days = plan['duration_days']
    if not (Decimal(0) < total <= Decimal(budget_cap)):
        raise ApiError(422, 'BUDGET_CONSTRAINT_VIOLATION', '建议总预算必须大于零且不得超过人工预算上限')
    if not (Decimal(0) < daily <= min(Decimal(daily_cap), total)):
        raise ApiError(422, 'BUDGET_CONSTRAINT_VIOLATION', '建议每日预算必须大于零且不得超过总预算和人工每日上限')
    if not (1 <= days <= duration_days) or total > daily * days:
        raise ApiError(422, 'BUDGET_CONSTRAINT_VIOLATION', '建议天数或每日预算无法覆盖总预算')
    allocations = sum((Decimal(a['amount']) for a in plan['allocations']), Decimal(0))
    if allocations != total:
        raise ApiError(422, 'BUDGET_CONSTRAINT_VIOLATION', '各项预算分配之和必须等于总预算')


def validate_experiment_plan(experiment, recommendation):
    plan = recommendation['content']['budget_plan']
    start = date.fromisoformat(experiment['planned_start_date'])
    end = date.fromisoformat(experiment['planned_end_date'])
    days = (end - start).days + 1
    budget, daily = Decimal(experiment['budget_amount']), Decimal(experiment['daily_cap'])
    if not 1 <= days <= plan['duration_days']:
        raise ApiError(422, 'EXPERIMENT_DATE_INVALID', '实验日期范围须为正数且不得超过建议批准天数')
    if not (0 < budget <= Decimal(plan['total_amount'])) or not (0 < daily <= min(budget, Decimal(plan['daily_cap']))) or budget > daily * days:
        raise ApiError(422, 'BUDGET_CONSTRAINT_VIOLATION', '实验预算必须满足建议总预算、每日上限及计划天数约束')
    value = Decimal(experiment['target_value'])
    if value < 0 or (experiment['success_metric'] == 'ctr' and value > 1) or (experiment['success_metric'] == 'cpa' and value <= 0):
        raise ApiError(422, 'METRIC_TARGET_INVALID', '目标 CTR 范围为 0–1，CPA 必须大于零，其他指标不得为负数')


def occupies_budget(experiment):
    return experiment['experiment_status'] in {'confirmed', 'running', 'finished'} or (
        experiment['experiment_status'] == 'cancelled' and experiment.get('actual_start_at') is not None)


def ensure_budget_available(experiment, recommendation, siblings):
    total = Decimal(experiment['budget_amount']) + sum(
        (Decimal(r['budget_amount']) for r in siblings if r['id'] != experiment['id'] and occupies_budget(r)), Decimal(0))
    if total > Decimal(recommendation['content']['budget_plan']['total_amount']):
        raise ApiError(409, 'BUDGET_EXCEEDED', '已确认、执行过的实验与本实验计划预算之和超过建议总预算')


def split_money(total, count):
    cents = int(Decimal(total) * 100)
    if count < 1 or cents < count:
        raise ApiError(422, 'BUDGET_CONSTRAINT_VIOLATION', '预算不足以按分拆分为指定数量的实验')
    quotient, remainder = divmod(cents, count)
    return [format(Decimal(quotient + (i < remainder)) / 100, '.2f') for i in range(count)]
