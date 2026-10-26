"""Operating round lifecycle and immutable diagnostic input snapshots."""
from copy import deepcopy

from app.services.common import ApiError, Result
from app.services.ai_support import now, owned, creative_started, ref


def derive_stage(ctx, row):
    if row["status"] != "active":
        return row["status"]
    round_id = row["id"]
    jobs = ctx.repo.list("GenerationJob", {"round_id": round_id})
    if not row["selected_diagnosis"]:
        return "diagnosing" if any(j["job_kind"] == "diagnosis" for j in jobs) else "draft"
    plans = ctx.repo.list("CreativePlan", {"round_id": round_id})
    if not any(p["status"] == "selected" and p["plan_type"] in {"main_image", "video_script"} for p in plans):
        return "creative"
    assets = ctx.repo.list("Asset", {"round_id": round_id})
    if not any(a["review_status"] == "approved" for a in assets):
        return "reviewing" if any(a["review_status"] == "pending" for a in assets) else "generating"
    experiments = ctx.repo.list("AdExperiment", {"round_id": round_id})
    if not experiments or any(e["experiment_status"] in {"draft", "confirmed"} for e in experiments):
        return "planning"
    if any(e["experiment_status"] == "running" for e in experiments):
        return "executing"
    return "analyzing"


def public_round(ctx, row):
    return {**row, "stage": derive_stage(ctx, row)}


def list_rounds(ctx):
    product_id = ctx.params["product_id"]
    ctx.require_product(product_id)
    filters = {"product_id": product_id}
    if ctx.query.get("status"):
        filters["status"] = ctx.query["status"]
    return ctx.page([public_round(ctx, r) for r in ctx.repo.list("OperatingRound", filters)])


def get_round(ctx):
    return public_round(ctx, owned(ctx, "OperatingRound", ctx.params["round_id"]))


def create_round(ctx):
    pid, body = ctx.params["product_id"], deepcopy(ctx.body)
    ctx.require_product(pid, active=True, lock=True)
    rounds = ctx.repo.list("OperatingRound", {"product_id": pid})
    if any(r["status"] == "active" for r in rounds):
        raise ApiError(409, "ACTIVE_ROUND_EXISTS", "该商品已有进行中的运营轮次")
    previous_id = body.get("previous_round_id")
    source = body.get("source_review")
    actions = body.get("adopted_action_ids", [])
    if previous_id:
        previous = owned(ctx, "OperatingRound", previous_id, product_id=pid)
        if previous["status"] != "completed":
            raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "来源轮次必须已完成")
        report = ctx.resolve_ref("ReviewReport", source, pid, previous_id)
        valid_ids = {a["action_id"] for a in report["content"]["next_actions"]}
        if not actions or len(set(actions)) != len(actions) or not set(actions) <= valid_ids:
            raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "采纳动作必须来自指定复盘版本且不能重复")
    elif source or actions:
        raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "首轮不能指定来源复盘或采纳动作")
    row = ctx.repo.create("OperatingRound", {
        "product_id": pid, "name": body["name"], "objective": body["objective"],
        "round_no": max((r["round_no"] for r in rounds), default=0) + 1,
        "previous_round_id": previous_id, "source_review": source,
        "adopted_action_ids": actions, "selected_diagnosis": None,
        "status": "active", "stage": "draft", "started_at": now(),
        "closed_at": None, "close_remark": None,
    })
    return Result(row, status=201)


def patch_round(ctx):
    pid, rid = ctx.params["product_id"], ctx.params["round_id"]
    row = ctx.require_round(pid, rid)
    ctx.check_version(row)
    body = deepcopy(ctx.body)
    jobs = ctx.repo.list("GenerationJob", {"round_id": rid})
    if jobs and any(key in body and body[key] != row[key] for key in ("name", "objective")):
        raise ApiError(409, "DEPENDENCY_CHANGED", "首个任务入队后轮次名称和目标已冻结")
    if "selected_diagnosis" in body:
        diagnosis = ctx.resolve_ref("Diagnosis", body["selected_diagnosis"], pid, rid)
        if creative_started(ctx, rid) and body["selected_diagnosis"] != row["selected_diagnosis"]:
            raise ApiError(409, "DIAGNOSIS_LOCKED", "进入创意生成后不能更换诊断")
    target = body.get("status", "active")
    if target in {"completed", "cancelled"}:
        experiments = ctx.repo.list("AdExperiment", {"round_id": rid})
        if any(e["experiment_status"] not in {"finished", "cancelled"} for e in experiments):
            raise ApiError(409, "INVALID_STATE_TRANSITION", "请先结束或取消本轮所有实验")
        if any(j["job_status"] in {"pending", "running"} for j in jobs):
            raise ApiError(409, "INVALID_STATE_TRANSITION", "请先完成或取消本轮所有任务")
        if target == "completed" and not ctx.repo.count("ReviewReport", {"round_id": rid}):
            raise ApiError(409, "INVALID_STATE_TRANSITION", "完成轮次前至少需要一份复盘报告")
        body["closed_at"] = now()
    elif "close_remark" in body:
        raise ApiError(422, "VALIDATION_ERROR", "结束说明须与完成或取消操作一起提交")
    row = ctx.repo.update("OperatingRound", rid, body)
    return public_round(ctx, row)


def snapshots(ctx):
    owned(ctx, "OperatingRound", ctx.params["round_id"])
    return ctx.collection("RoundSnapshot", {"round_id": ctx.params["round_id"]})


def capture_snapshot(ctx, product, round_id):
    return ctx.repo.create("RoundSnapshot", {
        "product_id": product["id"], "round_id": round_id, "product": deepcopy(product),
        "skus": ctx.repo.list("Sku", {"product_id": product["id"]}),
        "competitors": ctx.repo.list("Competitor", {"product_id": product["id"]}),
        "captured_at": now(),
    })


HANDLERS = {
    "GET /products/{product_id}/rounds": list_rounds,
    "POST /products/{product_id}/rounds": create_round,
    "GET /products/{product_id}/rounds/{round_id}": get_round,
    "PATCH /products/{product_id}/rounds/{round_id}": patch_round,
    "GET /products/{product_id}/rounds/{round_id}/snapshots": snapshots,
}
