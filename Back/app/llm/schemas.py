from copy import deepcopy

from jsonschema import Draft202012Validator, FormatChecker

from app.core.contract import SCHEMAS
from app.llm.errors import ModelError

CONTENT_SCHEMAS = {
    "diagnosis": "DiagnosisContent", "main_image_plan": "MainImageContent",
    "video_script": "VideoScriptContent", "title_plan": "TitleContent",
    "ad_recommendation": "AdRecommendationContent", "review_report": "ReviewContent",
}
PLAN_TYPES = {"main_image_plan": "main_image", "video_script": "video_script", "title_plan": "title"}


def inline_schema(value):
    if isinstance(value, list):
        return [inline_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        return inline_schema(SCHEMAS[value["$ref"].split("/")[-1]])
    return {key: inline_schema(item) for key, item in value.items() if key not in {"examples", "discriminator"}}


def output_schema(kind, count):
    content = inline_schema(SCHEMAS[CONTENT_SCHEMAS[kind]])
    if kind == "review_report":
        action = content["properties"]["next_actions"]["items"]
        action["properties"].pop("action_id", None)
        action["required"].remove("action_id")
    properties = {"content": content}
    if kind in PLAN_TYPES:
        properties.update({
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "rationale_text": {"type": "string", "minLength": 1, "maxLength": 4000},
        })
    item = {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    return {"type": "object", "properties": {
        "items": {"type": "array", "items": item, "minItems": count, "maxItems": count},
    }, "required": ["items"], "additionalProperties": False}


def validate_output(schema, value):
    if not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(value):
        raise ModelError("AI_OUTPUT_INVALID", "模型输出不符合约定的数据结构")

