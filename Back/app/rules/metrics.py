from decimal import Decimal, ROUND_HALF_UP

from app.core.exceptions import ApiError

MAX_MONEY = Decimal('999999999999.99')
MAX_COUNT = 9007199254740991


def money(value) -> str:
    amount = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if amount < 0 or amount > MAX_MONEY:
        raise ApiError(422, 'METRIC_OUT_OF_RANGE', '金额汇总超出接口允许范围，请缩小查询范围')
    return format(amount, '.2f')


def ratio(numerator, denominator, places=6):
    if Decimal(str(denominator)) == 0:
        return None
    value = (Decimal(str(numerator)) / Decimal(str(denominator))).quantize(
        Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    if value >= Decimal('1000000000000'):
        raise ApiError(422, 'METRIC_OUT_OF_RANGE', '指标结果超出接口允许范围')
    return format(value, '.2f') if places == 2 else format(value, 'f').rstrip('0').rstrip('.') if value else '0'


def calculate_metrics(row):
    return {
        'ctr': ratio(row['clicks'], row['impressions']),
        'conversion_rate': ratio(row['conversions'], row['clicks']),
        'roas': ratio(row['revenue'], row['spend']),
        'cpa': ratio(row['spend'], row['conversions'], 2),
        'roi': None,
    }


def summarize(rows):
    totals = {key: sum(int(r[key]) for r in rows) for key in ('impressions', 'clicks', 'conversions')}
    if any(value > MAX_COUNT for value in totals.values()):
        raise ApiError(422, 'METRIC_OUT_OF_RANGE', '计数汇总超出接口允许范围，请缩小查询范围')
    totals.update({key: money(sum((Decimal(r[key]) for r in rows), Decimal(0))) for key in ('spend', 'revenue')})
    totals.update(calculate_metrics(totals))
    warnings = []
    if any(r['clicks'] > r['impressions'] for r in rows):
        warnings.append('存在点击数大于曝光数的记录，请核对平台统计口径或归因延迟。')
    if any(r['conversions'] > r['clicks'] for r in rows):
        warnings.append('存在支付订单数大于点击数的记录；订单数不等于独立支付人数，请核对归因口径。')
    if any(Decimal(r['spend']) == 0 and Decimal(r['revenue']) > 0 for r in rows):
        warnings.append('存在零广告花费但有成交额的记录，可能包含自然流量，对应 ROAS 无法计算。')
    return totals, warnings
