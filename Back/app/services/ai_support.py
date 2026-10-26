"""Shared workflow checks. Writes run inside the API/worker transaction."""
from copy import deepcopy
from datetime import datetime, timezone

from app.services.common import ApiError, Result

CREATIVE_KINDS = {"main_image_plan", "video_script", "title_plan"}
AI_KINDS = CREATIVE_KINDS | {"diagnosis", "ad_recommendation", "review_report"}
RESOURCE_TYPES = {
    "diagnosis": "Diagnosis", "creative_plan": "CreativePlan",
    "ad_recommendation": "AdRecommendation", "review_report": "ReviewReport",
}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ref(row):
    return {"id": row["id"], "version": row["version"]}


def owned(ctx, kind, resource_id, *, product_id=None, round_id=None, lock=False):
    row = ctx.get(kind, resource_id, lock=lock)
    product_id = product_id or ctx.params.get("product_id")
    if product_id and row.get("product_id") != product_id:
        raise ApiError(404, "NOT_FOUND", "资源不存在")
    if round_id and row.get("round_id") != round_id:
        raise ApiError(404, "NOT_FOUND", "资源不存在")
    return row


def creative_started(ctx, round_id):
    return any(j["job_kind"] in CREATIVE_KINDS for j in ctx.repo.list(
        "GenerationJob", {"round_id": round_id}))


def require_diagnosis_unlocked(ctx, round_id):
    if creative_started(ctx, round_id):
        raise ApiError(409, "DIAGNOSIS_LOCKED", "已进入创意生成，本轮诊断已锁定")


def human_provenance(row):
    return {**row["provenance"], "source_type": "human_edited"}


def selected_diagnosis(ctx, product_id, round_row, diagnosis_ref):
    if diagnosis_ref != round_row.get("selected_diagnosis"):
        raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "必须使用本轮选定的诊断版本")
    return ctx.resolve_ref("Diagnosis", diagnosis_ref, product_id, round_row["id"])


def available_files(ctx, ids, product_id, *, real_only=False):
    if len(set(ids)) != len(ids):
        raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "参考文件不能重复")
    rows = []
    for file_id in ids:
        row = owned(ctx, "FileObject", file_id, product_id=product_id)
        if row["storage_status"] != "available" or not row["content_type"].startswith("image/"):
            raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "参考文件必须为已验证可用图片")
        if real_only and row["execution_mode"] != "real":
            raise ApiError(422, "DEMO_REAL_MIXED", "真实生成不能引用演示文件")
        rows.append(row)
    return rows


def text_config(ctx):
    from app.llm.client import get_secret
    settings_rows = ctx.repo.list("SystemSettings")
    settings = settings_rows[0] if settings_rows else {}
    config_id = settings.get("text_model_config_id")
    config = ctx.repo.get("ModelConfig", config_id) if config_id else None
    if not config or not config.get("enabled"):
        raise ApiError(422, "MODEL_NOT_CONFIGURED", "请管理员配置并启用文本模型")
    if not any(c["capability"] == "text" for c in config["capabilities"]):
        raise ApiError(422, "MODEL_CAPABILITY_UNSUPPORTED", "所选模型未声明文本能力")
    if config["execution_mode"] == "demo":
        if not settings.get("demo_generation_enabled") or config["provider"] != "demo":
            raise ApiError(422, "MODEL_NOT_CONFIGURED", "演示生成须由管理员显式启用演示模型")
    elif config["provider"] != "openai_compatible" or not (
        get_secret(config.get("secret_env_name"))
    ):
        raise ApiError(422, "MODEL_NOT_CONFIGURED", "文本模型服务或密钥环境变量尚未配置")
    return deepcopy(config)


def submit_text(ctx, kind, payload):
    from app.services.jobs import submit
    config = text_config(ctx)
    payload = deepcopy(payload)
    if config["execution_mode"] == "real":
        dependencies = payload.get("assets", []) + payload.get("reference_files", []) + payload.get("experiments", [])
        if payload.get("comparison"):
            dependencies += payload["comparison"].get("experiments", [])
        dependencies += [payload[key] for key in ("diagnosis", "source_review", "title_plan") if payload.get(key)]
        if any(d.get("execution_mode", d.get("provenance", {}).get("execution_mode")) == "demo" for d in dependencies):
            raise ApiError(422, "DEMO_REAL_MIXED", "真实模型任务不能引用演示结果或演示素材")
    payload["model_config"] = config
    payload["prompt_version"] = "v1"
    payload["execution_mode"] = config["execution_mode"]
    # Never store environment values in the immutable task input.
    accepted = submit(ctx, kind, payload, model_config_id=config["id"],
                      execution_mode=config["execution_mode"])
    return Result(accepted, status=202, headers={"Location": accepted["poll_url"]})


def resource_list(ctx, kind, allowed_filters=()):
    product_id = ctx.params["product_id"]
    ctx.require_product(product_id)
    filters = {"product_id": product_id}
    for key in allowed_filters:
        if ctx.query.get(key) is not None:
            filters[key] = ctx.query[key]
    if filters.get("round_id"):
        owned(ctx, "OperatingRound", filters["round_id"], product_id=product_id)
    return ctx.collection(kind, filters)


def unique_actions(content):
    ids = [action["action_id"] for action in content["next_actions"]]
    if len(ids) != len(set(ids)):
        raise ApiError(422, "INVALID_RESOURCE_REFERENCE", "复盘动作 action_id 必须唯一")

