from copy import deepcopy

from app.services.ai_support import (
    owned, require_diagnosis_unlocked, human_provenance,
    submit_text, resource_list,
)
from app.services.common import ApiError
from app.services.rounds import capture_snapshot


def generate(ctx):
    pid = ctx.params["product_id"]
    product = ctx.require_product(pid, active=True, lock=True)
    round_row = ctx.require_round(pid, ctx.body["round_id"])
    require_diagnosis_unlocked(ctx, round_row["id"])
    source = ctx.body.get("source_review")
    if source and source != round_row.get("source_review"):
        raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "来源复盘必须与本轮来源一致")
    source = round_row.get("source_review")
    review = ctx.resolve_ref("ReviewReport", source, pid, round_row["previous_round_id"]) if source else None
    snapshot = capture_snapshot(ctx, product, round_row["id"])
    return submit_text(ctx, "diagnosis", {
        "request": deepcopy(ctx.body), "product_id": pid, "round_id": round_row["id"],
        "snapshot": snapshot, "round": round_row, "source_review": review,
    })


def patch(ctx):
    row = owned(ctx, "Diagnosis", ctx.params["diagnosis_id"], lock=True)
    ctx.require_round(row["product_id"], row["round_id"])
    ctx.check_version(row)
    require_diagnosis_unlocked(ctx, row["round_id"])
    updates = {**deepcopy(ctx.body), "provenance": human_provenance(row)}
    updated = ctx.repo.update("Diagnosis", row["id"], updates)
    ctx.save_revision("Diagnosis", updated, ctx.body.get("edit_remark"))
    return updated


HANDLERS = {
    "POST /products/{product_id}/diagnoses/generate": generate,
    "GET /products/{product_id}/diagnoses": lambda ctx: resource_list(ctx, "Diagnosis", ("round_id",)),
    "GET /products/{product_id}/diagnoses/{diagnosis_id}": lambda ctx: owned(ctx, "Diagnosis", ctx.params["diagnosis_id"]),
    "PATCH /products/{product_id}/diagnoses/{diagnosis_id}": patch,
}
