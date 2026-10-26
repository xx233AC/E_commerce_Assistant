"""Generate outside a transaction, then publish atomically under the worker's lease."""
from copy import deepcopy
from uuid import NAMESPACE_URL, uuid4, uuid5
from decimal import Decimal
from time import monotonic

from app.agents import analysis, creative, strategy
from app.core.contract import validate_schema
from app.core.exceptions import ApiError
from app.llm.errors import ModelError
from app.llm.schemas import CONTENT_SCHEMAS, PLAN_TYPES
from app.llm.observability import capture_call
from app.services.ai_support import (
    now, ref, unique_actions, require_diagnosis_unlocked, selected_diagnosis,
)
from app.rules.budgets import validate_budget

AGENTS = {
    "diagnosis": (analysis, "analysis"), "review_report": (analysis, "analysis"),
    "main_image_plan": (creative, "creative"), "video_script": (creative, "creative"),
    "title_plan": (creative, "creative"), "ad_recommendation": (strategy, "strategy"),
}


def validate_evidence(input_data, outputs):
    known = {}
    def collect(value):
        if isinstance(value, dict):
            if "id" in value and "version" in value:
                known.setdefault(value["id"], set()).add(value["version"])
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(input_data)
    def check(value):
        if isinstance(value, dict):
            if {"kind", "resource_id", "resource_version", "field", "excerpt"} <= value.keys():
                resource_id, version = value["resource_id"], value["resource_version"]
                if resource_id and (resource_id not in known or version not in known[resource_id]):
                    raise ModelError("AI_OUTPUT_INVALID", "模型引用了输入快照中不存在的证据版本")
                if not resource_id and value["kind"] != "user_input":
                    raise ModelError("AI_OUTPUT_INVALID", "业务证据必须引用输入中的实际资源")
            if value.get("certainty") == "observed" and not value.get("evidence"):
                raise ModelError("AI_OUTPUT_INVALID", "已观察结论缺少证据引用")
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
    check(outputs)


def execute_text(kind: str, input: dict, config: dict) -> list[dict]:
    if kind not in AGENTS:
        raise ModelError("JOB_EXECUTION_FAILED", "不支持的文本任务类型")
    agent, _ = AGENTS[kind]
    outputs = agent.run(kind, input, config)
    try:
        if kind == "review_report":
            for output in outputs:
                for action in output["content"]["next_actions"]:
                    action["action_id"] = str(uuid4())
                limitations = output["content"]["limitations"]
                mandatory = input.get("warnings", []) + [
                    "转化数按归属支付订单数统计，不等于独立支付人数；需考虑平台归因延迟。",
                    "ROAS为收入与广告花费之比；缺少完整成本与退款数据，本报告不计算利润ROI。",
                ]
                # Reserve room for deterministic warnings without exceeding the contract.
                output["content"]["limitations"] = list(dict.fromkeys(mandatory + limitations))[:100]
                unique_actions(output["content"])
        for output in outputs:
            validate_schema(CONTENT_SCHEMAS[kind], output["content"])
            constraints = input.get('media_constraints', {})
            content = output['content']
            if constraints.get('reference_file_ids_must_be_empty') and content.get('reference_file_ids'):
                raise ModelError('AI_OUTPUT_INVALID', '当前图片模型要求纯文字方案，不能引用参考图')
            if constraints.get('allowed_duration_sec') and content.get('duration_sec') not in constraints['allowed_duration_sec']:
                raise ModelError('AI_OUTPUT_INVALID', '视频脚本时长不符合当前视频模型能力')
            if constraints.get('max_generation_prompt_characters') and len(content.get('generation_prompt', '')) > constraints['max_generation_prompt_characters']:
                raise ModelError('AI_OUTPUT_INVALID', '视频提示词超过当前模型允许长度')
            if constraints.get('max_reference_images') and len(content.get('reference_file_ids', [])) > constraints['max_reference_images']:
                raise ModelError('AI_OUTPUT_INVALID', '视频参考图片数量超过模型限制')
            if kind == "ad_recommendation":
                request = input["request"]
                validate_budget(output["content"], request["budget_cap"], request["daily_cap"], request["duration_days"])
                allowed_refs = [ref(asset) for asset in input["assets"]]
                title = ref(input["title_plan"]) if input.get("title_plan") else None
                for test in output["content"]["creative_tests"]:
                    if test["asset"] not in allowed_refs or test.get("title_plan") not in (None, title):
                        raise ModelError("AI_OUTPUT_INVALID", "模型引用了未提供的素材或标题版本")
                    target = Decimal(test["target_value"])
                    if (test["success_metric"] == "ctr" and target > 1) or (test["success_metric"] == "cpa" and target <= 0):
                        raise ModelError("AI_OUTPUT_INVALID", "模型实验目标超出指标范围")
            if kind == "video_script":
                content = output["content"]
                if sum(s["duration_sec"] for s in content["shots"]) != content["duration_sec"]:
                    raise ModelError("AI_OUTPUT_INVALID", "模型分镜时长之和与脚本总时长不一致")
                if [s["shot_no"] for s in content["shots"]] != list(range(1, len(content["shots"]) + 1)):
                    raise ModelError("AI_OUTPUT_INVALID", "模型分镜序号不连续")
            if kind in {"main_image_plan", "video_script"}:
                allowed = {r["id"] for r in input.get("reference_files", [])}
                if not set(output["content"]["reference_file_ids"]) <= allowed:
                    raise ModelError("AI_OUTPUT_INVALID", "模型引用了未提供的参考文件")
            if kind == "title_plan" and output["content"]["platform"] != input["snapshot"]["product"]["platform"]:
                raise ModelError("AI_OUTPUT_INVALID", "模型标题平台与商品平台不一致")
        validate_evidence(input, outputs)
    except ApiError:
        raise ModelError("AI_OUTPUT_INVALID", "模型结果未通过业务数据校验") from None
    return outputs


def execute_text_with_metadata(kind: str, input: dict, config: dict):
    """Optional worker entry point: output list plus private call audit metadata."""
    started = monotonic()
    with capture_call() as metadata:
        metadata.update({"job_kind": kind, "model_config_id": config.get("id"),
                         "model_config_version": config.get("version"), "model_name": config["model_name"],
                         "prompt_version": input.get("prompt_version", "v1"), "execution_mode": config["execution_mode"]})
        try:
            outputs = execute_text(kind, input, config)
        except ModelError as error:
            metadata["elapsed_seconds"] = round(monotonic() - started, 3)
            metadata["error_code"] = error.code
            error.audit_metadata = deepcopy(metadata)
            raise
        finally:
            metadata["elapsed_seconds"] = round(monotonic() - started, 3)
        return outputs, metadata


def publish_text(ctx, job, input, outputs):
    from app.services.ad_recommendations import validate_recommendation
    from app.services.creative import validate_content
    kind = job["job_kind"]
    pid, rid = input["product_id"], input["round_id"]
    product = ctx.require_product(pid, active=(kind != "review_report"), lock=True)
    round_row = ctx.require_round(pid, rid)
    if kind == "diagnosis":
        require_diagnosis_unlocked(ctx, rid)
    if kind in PLAN_TYPES or kind == "ad_recommendation":
        selected_diagnosis(ctx, pid, round_row, input["request"]["diagnosis"])
    expected = input["request"].get("count", 3) if kind in PLAN_TYPES else 1
    if len(outputs) != expected:
        raise ModelError("AI_OUTPUT_INVALID", "任务结果数量与请求不一致")
    config = input["model_config"]
    provenance = {
        "source_type": "ai", "agent": AGENTS[kind][1], "model_config_id": config["id"],
        "model_name": config["model_name"], "prompt_version": input["prompt_version"],
        "execution_mode": job["execution_mode"], "source_job_id": job["id"],
        "model_config_version": config["version"],
    }
    resources = []
    for index, output in enumerate(outputs):
        resource_id = str(uuid5(NAMESPACE_URL, "commerce-job:" + job["id"] + ":" + str(index)))
        base = {"id": resource_id, "product_id": pid, "round_id": rid,
                "content": deepcopy(output["content"]), "provenance": provenance}
        if kind == "diagnosis":
            resource_kind, resource_type = "Diagnosis", "diagnosis"
            base.update({"snapshot_id": input["snapshot"]["id"], "edit_remark": None})
        elif kind in PLAN_TYPES:
            resource_kind, resource_type = "CreativePlan", "creative_plan"
            validate_content(ctx, PLAN_TYPES[kind], base["content"], pid)
            base.update({"title": output["title"], "rationale_text": output["rationale_text"],
                         "plan_type": PLAN_TYPES[kind], "status": "draft", "diagnosis": input["request"]["diagnosis"],
                         "snapshot_id": input["snapshot"]["id"]})
        elif kind == "ad_recommendation":
            resource_kind, resource_type = "AdRecommendation", "ad_recommendation"
            request = input["request"]
            validate_recommendation(ctx, base["content"], pid, rid, request,
                                    allowed_assets=request["asset_refs"], allowed_title=request.get("title_plan"),
                                    execution_mode=job["execution_mode"])
            # Absence of a supplied title forbids an invented optional title reference.
            if not request.get("title_plan") and any(t.get("title_plan") for t in base["content"]["creative_tests"]):
                raise ModelError("AI_OUTPUT_INVALID", "模型添加了未提供的标题引用")
            base.update({"diagnosis": request["diagnosis"], "budget_cap": request["budget_cap"],
                         "daily_cap": request["daily_cap"], "duration_days": request["duration_days"],
                         "confirm_status": "pending", "latest_confirmation": None})
        elif kind == "review_report":
            resource_kind, resource_type = "ReviewReport", "review_report"
            request = input["request"]
            base.update({"period_start": request["period_start"], "period_end": request["period_end"],
                         "granularity": request["granularity"], "experiment_ids": request.get("experiment_ids", []),
                         "performance_record_refs": [ref(r) for r in input["performance_records"]],
                         "metric_snapshot": input["metric_snapshot"]})
        else:
            raise ModelError("JOB_EXECUTION_FAILED", "不支持的文本任务类型")
        existing = ctx.repo.get(resource_kind, resource_id)
        if existing:
            if existing["provenance"]["source_job_id"] != job["id"]:
                raise ModelError("JOB_EXECUTION_FAILED", "任务结果标识冲突")
            row = existing
        else:
            row = ctx.repo.create(resource_kind, base)
        validate_schema(resource_kind, row)
        ctx.save_revision(resource_kind, row, "AI任务生成")
        resources.append({"resource_type": resource_type, "resource_id": row["id"], "version": row["version"]})
    if kind in {"diagnosis", "review_report"}:
        field = "last_diagnosis_at" if kind == "diagnosis" else "last_review_at"
        ctx.repo.update("Product", pid, {field: now()})
    return resources
