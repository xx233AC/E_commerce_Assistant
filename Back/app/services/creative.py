from copy import deepcopy
from functools import partial

from app.services.common import ApiError
from app.services.ai_support import (
    owned, selected_diagnosis, available_files, submit_text,
    resource_list, human_provenance,
)


def validate_content(ctx, plan_type, content, product_id):
    if plan_type in {"main_image", "video_script"}:
        available_files(ctx, content["reference_file_ids"], product_id)
    if plan_type == "video_script":
        shots = content["shots"]
        if sum(shot["duration_sec"] for shot in shots) != content["duration_sec"]:
            raise ApiError(422, "VALIDATION_ERROR", "分镜时长之和必须等于脚本总时长")
        if [s["shot_no"] for s in shots] != list(range(1, len(shots) + 1)):
            raise ApiError(422, "VALIDATION_ERROR", "分镜序号必须从1开始连续递增")
    if plan_type == "title":
        product = ctx.require_product(product_id)
        if content["platform"] != product["platform"]:
            raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "标题平台必须与商品平台一致")


def generate(ctx, kind):
    pid, body = ctx.params["product_id"], deepcopy(ctx.body)
    ctx.require_product(pid, active=True, lock=True)
    round_row = ctx.require_round(pid, body["round_id"])
    diagnosis = selected_diagnosis(ctx, pid, round_row, body["diagnosis"])
    files = available_files(ctx, body.get("reference_file_ids", []), pid)
    snapshot = ctx.get("RoundSnapshot", diagnosis["snapshot_id"])
    body.setdefault("count", 3)
    constraints = {}
    media_kind = {'main_image_plan': 'image', 'video_script': 'video'}.get(kind)
    if media_kind:
        settings = ctx.get('SystemSettings', 'singleton')
        config_id = settings.get(media_kind + '_model_config_id')
        media_config = ctx.get('ModelConfig', config_id) if config_id else None
        if media_config and media_config['enabled']:
            if media_config['model_name'] == 'glm-image':
                constraints = {'model': 'glm-image', 'text_to_image_only': True,
                               'reference_file_ids_must_be_empty': True,
                               'instruction': '主图生成仅使用文字提示词描述商品、布局、文字和材质；不要声称已看见参考图，也不要在输出中引用参考文件。'}
            elif media_config['model_name'] == 'cogvideox-3':
                constraints = {'model': 'cogvideox-3', 'allowed_duration_sec': [5, 10],
                               'max_generation_prompt_characters': 512, 'max_reference_images': 2,
                               'instruction': '每份脚本总时长必须为5或10秒，分镜时长合计一致；提示词不超过512字符。'}
    return submit_text(ctx, kind, {
        "request": body, "product_id": pid, "round_id": round_row["id"],
        "round": round_row, "snapshot": snapshot, "diagnosis": diagnosis,
        "reference_files": files,
        "media_constraints": constraints,
    })


def patch(ctx):
    row = owned(ctx, "CreativePlan", ctx.params["creative_plan_id"], lock=True)
    ctx.require_round(row["product_id"], row["round_id"])
    ctx.check_version(row)
    body = deepcopy(ctx.body)
    if body["plan_type"] != row["plan_type"]:
        raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "方案类型不可修改")
    changed_content = any(body[key] != row[key] for key in ("title", "content", "rationale_text"))
    if changed_content and body["status"] != "draft":
        raise ApiError(422, "PLAN_RESELECT_REQUIRED", "修改内容后须先保存为草案，再单独选定")
    if row["status"] == "archived" and body["status"] == "selected":
        raise ApiError(409, "INVALID_STATE_TRANSITION", "归档方案须先恢复为草案")
    validate_content(ctx, row["plan_type"], body["content"], row["product_id"])
    if body["status"] == "selected":
        for other in ctx.repo.list("CreativePlan", {
            "round_id": row["round_id"], "plan_type": row["plan_type"], "status": "selected",
        }):
            if other["id"] != row["id"]:
                demoted = ctx.repo.update("CreativePlan", other["id"], {"status": "draft"})
                ctx.save_revision("CreativePlan", demoted, "同类型新方案已选定")
    if changed_content:
        body["provenance"] = human_provenance(row)
    updated = ctx.repo.update("CreativePlan", row["id"], body)
    ctx.save_revision("CreativePlan", updated, "编辑方案" if changed_content else "调整方案状态")
    return updated


HANDLERS = {
    "POST /products/{product_id}/creative-plans/main-images/generate": partial(generate, kind="main_image_plan"),
    "POST /products/{product_id}/creative-plans/video-scripts/generate": partial(generate, kind="video_script"),
    "POST /products/{product_id}/creative-plans/titles/generate": partial(generate, kind="title_plan"),
    "GET /products/{product_id}/creative-plans": lambda ctx: resource_list(ctx, "CreativePlan", ("round_id", "plan_type", "status")),
    "GET /products/{product_id}/creative-plans/{creative_plan_id}": lambda ctx: owned(ctx, "CreativePlan", ctx.params["creative_plan_id"]),
    "PATCH /products/{product_id}/creative-plans/{creative_plan_id}": patch,
}
