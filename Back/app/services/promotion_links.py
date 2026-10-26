import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone

from app.core.exceptions import ApiError
from app.rules.promotion_links import validate_public_url, with_utm
from app.services.catalog import now_iso, owned, parse_time, read_round
from app.services.common import RawResult

SHOP_TZ = timezone(timedelta(hours=8))


def suggest(ctx):
    product = ctx.require_product(ctx.params['product_id'], lock=True)
    ctx.require_round(product['id'], ctx.body['round_id'])
    validate_public_url(ctx.body['target_url'])
    utm = ctx.body.get('utm') or {'source': product['platform'], 'medium': 'manual', 'campaign': ctx.body['round_id'], 'content': ctx.body['scene_text'][:100], 'term': None}
    return {'link_name': f'{product["name"]} · {ctx.body["scene_text"]}'[:100], 'target_url': ctx.body['target_url'], 'utm': utm, 'scene_text': ctx.body['scene_text'], 'warnings': []}


def create_link(ctx):
    ctx.require_product(ctx.params['product_id'], lock=True)
    ctx.require_round(ctx.params['product_id'], ctx.body['round_id'])
    validate_public_url(ctx.body['target_url'])
    if len(with_utm(ctx.body['target_url'], ctx.body['utm'])) > 8192:
        raise ApiError(422, 'URL_TOO_LONG', '拼接追踪参数后的目标地址过长')
    code = secrets.token_urlsafe(24)
    return ctx.repo.create('PromotionLink', {**ctx.body, 'product_id': ctx.params['product_id'], 'status': ctx.body.get('status', 'active'), 'tracking_code': code, 'short_url': ctx.base_url.rstrip('/') + '/api/v1/r/' + code, 'click_count': 0})


def list_links(ctx):
    ctx.require_product(ctx.params['product_id'])
    if ctx.query.get('round_id'):
        read_round(ctx, ctx.query['round_id'])
    return ctx.collection('PromotionLink', {'product_id': ctx.params['product_id'], **{k: ctx.query[k] for k in ('round_id', 'status') if k in ctx.query}})


def get_link(ctx):
    ctx.require_product(ctx.params['product_id'])
    return owned(ctx, 'PromotionLink', ctx.params['link_id'])


def patch_link(ctx):
    ctx.require_product(ctx.params['product_id'], lock=True)
    row = owned(ctx, 'PromotionLink', ctx.params['link_id'], lock=True)
    ctx.require_round(row['product_id'], row['round_id'])
    ctx.check_version(row)
    if ctx.body.get('status') == 'disabled' and any(r['related_link_id'] == row['id'] and r['experiment_status'] in {'confirmed', 'running'} for r in ctx.repo.list('AdExperiment', {'product_id': row['product_id']})):
        raise ApiError(409, 'LINK_IN_USE', '已确认或运行中的实验正在使用该链接')
    return ctx.repo.update('PromotionLink', row['id'], ctx.body)


def _date_range(query):
    start, end = date.fromisoformat(query['start_date']), date.fromisoformat(query['end_date'])
    if end < start or (end - start).days >= 366:
        raise ApiError(422, 'DATE_RANGE_INVALID', '统计日期范围两端包含且最长 366 天')
    return start, end


def link_stats(ctx):
    row = get_link(ctx)
    start, end = _date_range(ctx.query)
    days = {}
    for event in ctx.repo.list('ClickEvent', {'link_id': row['id']}):
        day = parse_time(event['clicked_at']).astimezone(SHOP_TZ).date()
        if start <= day <= end:
            bucket = days.setdefault(day.isoformat(), {'date': day.isoformat(), 'redirect_requests': 0, 'counted_clicks': 0, 'filtered_requests': 0})
            bucket['redirect_requests'] += 1
            bucket['counted_clicks' if event['counted'] else 'filtered_requests'] += 1
    return {'link_id': row['id'], 'start_date': start.isoformat(), 'end_date': end.isoformat(),
        'totals': {key: sum(v[key] for v in days.values()) for key in ('redirect_requests', 'counted_clicks', 'filtered_requests')},
        'days': [days[key] for key in sorted(days)], 'attribution_note': '统计为正常跳转请求次数，不代表去重用户、支付订单或订单归因；重复正常点击会累计。'}


def redirect(ctx):
    rows = ctx.repo.list('PromotionLink', {'tracking_code': ctx.params['tracking_code']})
    if not rows:
        raise ApiError(404, 'NOT_FOUND', '推广链接不存在')
    row = ctx.get('PromotionLink', rows[0]['id'], lock=True)
    if row['status'] != 'active':
        raise ApiError(410, 'LINK_DISABLED', '推广链接已停用')
    # 目标仅来自保存的不可变数据，不使用请求中的任何覆盖地址。
    agent = ctx.headers.get('user-agent', '').casefold()
    fingerprint = hashlib.sha256((str(ctx.client_ip) + '|' + agent).encode()).hexdigest()
    minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    recent = [e for e in ctx.repo.list('ClickEvent', {'link_id': row['id'], 'request_fingerprint': fingerprint}) if parse_time(e['clicked_at']) >= minute_ago]
    limited = len(recent) >= 60
    preview = any(token in agent for token in ('bot', 'spider', 'crawler', 'preview', 'facebookexternalhit', 'slack', 'telegram'))
    counted = ctx.request_method != 'HEAD' and not preview and not limited
    ctx.repo.create('ClickEvent', {'link_id': row['id'], 'clicked_at': now_iso(), 'counted': counted, 'request_fingerprint': fingerprint, 'ip_hash': hashlib.sha256(str(ctx.client_ip).encode()).hexdigest()})
    if counted:
        ctx.repo.update('PromotionLink', row['id'], {'click_count': row['click_count'] + 1}, bump=False)
    return RawResult(b'', media_type='text/plain', status=302, headers={'Location': with_utm(row['target_url'], row['utm']), 'Cache-Control': 'no-store'})
