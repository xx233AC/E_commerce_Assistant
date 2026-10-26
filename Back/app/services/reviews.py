from copy import deepcopy
from datetime import date

from app.rules.metrics import summarize
from app.services.common import ApiError
from app.services.ai_support import (
    owned, ref, resource_list, submit_text, human_provenance, unique_actions,
)


def review_records(ctx, product_id, round_id, request):
    start, end = date.fromisoformat(request["period_start"]), date.fromisoformat(request["period_end"])
    if end < start or (end - start).days > 365:
        raise ApiError(422, "VALIDATION_ERROR", "复盘时间区间须有效且最多366天")
    experiment_ids = request.get("experiment_ids", [])
    if len(set(experiment_ids)) != len(experiment_ids):
        raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "实验不能重复")
    for experiment_id in experiment_ids:
        owned(ctx, "AdExperiment", experiment_id, product_id=product_id, round_id=round_id)
    rows = ctx.repo.list("PerformanceRecord", {
        "product_id": product_id, "round_id": round_id,
        "granularity": request["granularity"], "voided": False,
    })
    rows = [r for r in rows if request["period_start"] <= r["record_date"] <= request["period_end"]
            and (not experiment_ids or r["experiment_id"] in experiment_ids)]
    if len(rows) > 10000:
        raise ApiError(422, "VALIDATION_ERROR", "复盘范围最多10000条记录，请缩小范围")
    modes = set()
    experiments = []
    for experiment_id in sorted({r["experiment_id"] for r in rows if r["experiment_id"]}):
        experiment = owned(ctx, "AdExperiment", experiment_id, product_id=product_id, round_id=round_id)
        modes.add(experiment["execution_mode"])
        experiments.append(experiment)
    if len(modes) > 1:
        raise ApiError(422, "DEMO_REAL_MIXED", "同一复盘不能混合真实和演示实验")
    totals, warnings = summarize(rows)
    return rows, totals, warnings, experiments


def generate(ctx):
    pid, request = ctx.params["product_id"], deepcopy(ctx.body)
    product = ctx.require_product(pid, lock=True)
    round_row = ctx.require_round(pid, request["round_id"])
    records, totals, warnings, experiments = review_records(ctx, pid, round_row["id"], request)
    if not records:
        raise ApiError(422, "NO_PERFORMANCE_DATA", "该范围暂无有效经营数据")
    comparison = None
    if request.get("comparison_round_id"):
        comparison_round = owned(ctx, "OperatingRound", request["comparison_round_id"], product_id=pid)
        if comparison_round["id"] == round_row["id"]:
            raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "对比轮次必须为另一轮次")
        other_rows = ctx.repo.list("PerformanceRecord", {
            "product_id": pid, "round_id": comparison_round["id"],
            "granularity": request["granularity"], "voided": False,
        })
        if len(other_rows) > 10000:
            raise ApiError(422, "VALIDATION_ERROR", "对比轮次记录过多")
        other_experiments = [owned(ctx, "AdExperiment", experiment_id, product_id=pid, round_id=comparison_round["id"])
                             for experiment_id in sorted({r["experiment_id"] for r in other_rows if r["experiment_id"]})]
        if len({e["execution_mode"] for e in experiments + other_experiments}) > 1:
            raise ApiError(422, "DEMO_REAL_MIXED", "复盘及对比轮次不能混合真实和演示实验")
        other_totals, other_warnings = summarize(other_rows)
        comparison = {"round": comparison_round, "records": other_rows,
                      "metric_snapshot": other_totals, "warnings": other_warnings, "experiments": other_experiments,
                      "scope": "完整对比轮次；周期不等长时不得直接推断效果提升"}
    selected = round_row.get("selected_diagnosis")
    diagnosis = ctx.resolve_ref("Diagnosis", selected, pid, round_row["id"]) if selected else None
    snapshot = ctx.get("RoundSnapshot", diagnosis["snapshot_id"]) if diagnosis else {
        "product": product, "skus": ctx.repo.list("Sku", {"product_id": pid}),
        "competitors": ctx.repo.list("Competitor", {"product_id": pid}),
    }
    return submit_text(ctx, "review_report", {
        "request": request, "product_id": pid, "round_id": round_row["id"],
        "round": round_row, "snapshot": snapshot, "diagnosis": diagnosis,
        "performance_records": records, "metric_snapshot": totals,
        "warnings": warnings, "experiments": experiments, "comparison": comparison,
    })


def patch(ctx):
    row = owned(ctx, "ReviewReport", ctx.params["report_id"], lock=True)
    ctx.require_round(row["product_id"], row["round_id"])
    ctx.check_version(row)
    content = deepcopy(ctx.body.get("content", row["content"]))
    unique_actions(content)
    updated = ctx.repo.update("ReviewReport", row["id"], {
        "content": content, "provenance": human_provenance(row),
    })
    ctx.save_revision("ReviewReport", updated, ctx.body.get("edit_remark"))
    return updated


HANDLERS = {
    "POST /products/{product_id}/review-reports/generate": generate,
    "GET /products/{product_id}/review-reports": lambda ctx: resource_list(ctx, "ReviewReport", ("round_id",)),
    "GET /products/{product_id}/review-reports/{report_id}": lambda ctx: owned(ctx, "ReviewReport", ctx.params["report_id"]),
    "PATCH /products/{product_id}/review-reports/{report_id}": patch,
}
