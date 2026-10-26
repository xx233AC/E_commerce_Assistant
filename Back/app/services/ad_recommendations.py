"""Strategy recommendations remain advisory until an explicit human confirmation."""
from copy import deepcopy
from decimal import Decimal

from app.services.common import ApiError
from app.services.ai_support import (
    owned, selected_diagnosis, submit_text, resource_list, ref, human_provenance,
)
from app.rules.budgets import validate_budget


def approved_asset(ctx, asset_ref, product_id, round_id):
    asset = owned(ctx, "Asset", asset_ref["id"], product_id=product_id, round_id=round_id)
    if asset["version"] != asset_ref["version"] or asset["review_status"] != "approved":
        raise ApiError(409, "DEPENDENCY_CHANGED", "素材版本或审核状态已变化，请重新选择")
    file = owned(ctx, "FileObject", asset["file_id"], product_id=product_id)
    if file["storage_status"] != "available":
        raise ApiError(409, "DEPENDENCY_CHANGED", "素材文件已不可用")
    return asset


def selected_title(ctx, title_ref, product_id, round_id):
    plan = ctx.resolve_ref("CreativePlan", title_ref, product_id, round_id)
    current = owned(ctx, "CreativePlan", title_ref["id"], product_id=product_id, round_id=round_id)
    if plan["plan_type"] != "title" or current["status"] != "selected" or ref(current) != title_ref:
        raise ApiError(409, "DEPENDENCY_CHANGED", "标题方案须为本轮当前选定版本")
    return plan


def validate_recommendation(ctx, content, product_id, round_id, caps, *, allowed_assets=None,
                            allowed_title=None, execution_mode=None):
    validate_budget(content, caps["budget_cap"], caps["daily_cap"], caps["duration_days"])
    assets = []
    for test in content["creative_tests"]:
        if allowed_assets is not None and test["asset"] not in allowed_assets:
            raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "建议只能使用本次提供的素材版本")
        assets.append(approved_asset(ctx, test["asset"], product_id, round_id))
        if test.get("title_plan"):
            if allowed_title is not None and test["title_plan"] != allowed_title:
                raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "建议标题引用不属于本次输入")
            selected_title(ctx, test["title_plan"], product_id, round_id)
        value = Decimal(test["target_value"])
        if test["success_metric"] == "ctr" and not Decimal(0) <= value <= Decimal(1):
            raise ApiError(422, "VALIDATION_ERROR", "CTR目标须介于0和1之间")
        if test["success_metric"] == "cpa" and value <= 0:
            raise ApiError(422, "VALIDATION_ERROR", "CPA目标必须大于0")
    modes = {a["execution_mode"] for a in assets}
    if len(modes) > 1 or (execution_mode == "real" and "demo" in modes):
        raise ApiError(422, "DEMO_REAL_MIXED", "真实与演示素材不得混用")
    return assets


def generate(ctx):
    pid, body = ctx.params["product_id"], deepcopy(ctx.body)
    ctx.require_product(pid, active=True, lock=True)
    round_row = ctx.require_round(pid, body["round_id"])
    diagnosis = selected_diagnosis(ctx, pid, round_row, body["diagnosis"])
    if Decimal(body["budget_cap"]) <= 0 or Decimal(body["daily_cap"]) <= 0:
        raise ApiError(422, "BUDGET_CONSTRAINT_VIOLATION", "预算上限和每日上限必须大于0")
    refs = body["asset_refs"]
    if len({(r["id"], r["version"]) for r in refs}) != len(refs):
        raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "素材引用不能重复")
    assets = [approved_asset(ctx, r, pid, round_row["id"]) for r in refs]
    if len({a["execution_mode"] for a in assets}) > 1:
        raise ApiError(422, "DEMO_REAL_MIXED", "投放建议不能混合真实与演示素材")
    title = selected_title(ctx, body["title_plan"], pid, round_row["id"]) if body.get("title_plan") else None
    return submit_text(ctx, "ad_recommendation", {
        "request": body, "product_id": pid, "round_id": round_row["id"],
        "round": round_row, "snapshot": ctx.get("RoundSnapshot", diagnosis["snapshot_id"]),
        "diagnosis": diagnosis, "assets": assets, "title_plan": title,
    })


def patch(ctx):
    row = owned(ctx, "AdRecommendation", ctx.params["recommendation_id"], lock=True)
    ctx.require_round(row["product_id"], row["round_id"])
    ctx.check_version(row)
    for experiment in ctx.repo.list("AdExperiment", {"round_id": row["round_id"]}):
        if experiment["recommendation"]["id"] == row["id"] and experiment["experiment_status"] in {"confirmed", "running"}:
            raise ApiError(409, "DEPENDENCY_CHANGED", "已有确认或执行中的实验，不能修改其投放建议")
    content = deepcopy(ctx.body.get("content", row["content"]))
    validate_recommendation(ctx, content, row["product_id"], row["round_id"], row,
                            execution_mode=row["provenance"]["execution_mode"])
    updated = ctx.repo.update("AdRecommendation", row["id"], {
        "content": content, "confirm_status": "pending", "latest_confirmation": None,
        "provenance": human_provenance(row),
    })
    ctx.save_revision("AdRecommendation", updated, ctx.body.get("edit_remark"))
    return updated


def confirm(ctx):
    row = owned(ctx, "AdRecommendation", ctx.params["recommendation_id"], lock=True)
    ctx.require_round(row["product_id"], row["round_id"])
    ctx.check_version(row)
    if row["confirm_status"] != "pending":
        raise ApiError(409, "INVALID_STATE_TRANSITION", "只有待确认建议可确认或驳回")
    if ctx.body["decision"] == "confirmed":
        validate_recommendation(ctx, row["content"], row["product_id"], row["round_id"], row,
                                execution_mode=row["provenance"]["execution_mode"])
    confirmation = ctx.repo.create("Confirmation", {
        "product_id": row["product_id"], "round_id": row["round_id"],
        "recommendation_id": row["id"], "resource_version": row["version"],
        "decision": ctx.body["decision"], "operator_id": ctx.user["id"],
        "remark": ctx.body["remark"],
    })
    updated = ctx.repo.update("AdRecommendation", row["id"], {
        "confirm_status": ctx.body["decision"], "latest_confirmation": confirmation,
    })
    ctx.save_revision("AdRecommendation", updated, ctx.body["remark"])
    return updated


def confirmations(ctx):
    row = owned(ctx, "AdRecommendation", ctx.params["recommendation_id"])
    return ctx.collection("Confirmation", {"recommendation_id": row["id"]})


HANDLERS = {
    "POST /products/{product_id}/ad-recommendations/generate": generate,
    "GET /products/{product_id}/ad-recommendations": lambda ctx: resource_list(ctx, "AdRecommendation", ("round_id", "confirm_status")),
    "GET /products/{product_id}/ad-recommendations/{recommendation_id}": lambda ctx: owned(ctx, "AdRecommendation", ctx.params["recommendation_id"]),
    "PATCH /products/{product_id}/ad-recommendations/{recommendation_id}": patch,
    "PATCH /products/{product_id}/ad-recommendations/{recommendation_id}/confirmation": confirm,
    "GET /products/{product_id}/ad-recommendations/{recommendation_id}/confirmations": confirmations,
}
