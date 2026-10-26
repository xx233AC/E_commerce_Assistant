from datetime import datetime
from app.core.exceptions import ApiError
from app.services.rounds import public_round


def dashboard(ctx):
    stores=ctx.repo.list('Store')
    return {'store':stores[0] if stores else None,'product_count':ctx.repo.count('Product'),
            'active_product_count':ctx.repo.count('Product',{'status':'active'}),
            'low_stock_sku_count':stores[0]['low_stock_sku_count'] if stores else 0,
            'pending_asset_review_count':ctx.repo.count('Asset',{'review_status':'pending'}),
            'pending_ad_confirmation_count':ctx.repo.count('AdRecommendation',{'confirm_status':'pending'}),
            'running_job_count':ctx.repo.count('GenerationJob',{'job_status':['pending','running']}),
            'latest_rounds':[public_round(ctx,row) for row in ctx.repo.list('OperatingRound',limit=10)]}


def audit_logs(ctx):
    rows=ctx.repo.list('AuditLog')
    for key in ('actor_id','resource_type','resource_id','action'):
        if key in ctx.query: rows=[r for r in rows if r.get(key)==ctx.query[key]]
    parse=lambda value: datetime.fromisoformat(value.replace('Z','+00:00'))
    start=parse(ctx.query['start_at']) if ctx.query.get('start_at') else None
    end=parse(ctx.query['end_at']) if ctx.query.get('end_at') else None
    if start and end and end<start:
        raise ApiError(422,'VALIDATION_ERROR','审计结束时间不能早于开始时间')
    if start: rows=[r for r in rows if parse(r['created_at'])>=start]
    if end: rows=[r for r in rows if parse(r['created_at'])<=end]
    return ctx.page(rows)

HANDLERS={'GET /workspace/dashboard':dashboard,'GET /workspace/audit-logs':audit_logs}
