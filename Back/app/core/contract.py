"""The checked-in OpenAPI contract is shared by validation and API documentation."""
import copy
import json
from pathlib import Path
from functools import lru_cache

from jsonschema import Draft202012Validator, FormatChecker
from app.core.exceptions import ApiError

SPEC = json.loads((Path(__file__).resolve().parents[2] / 'contracts/openapi.json').read_text(encoding='utf-8'))
SCHEMAS = SPEC['components']['schemas']


def resolve(schema):
    if '$ref' in schema:
        value = SPEC
        for part in schema['$ref'].removeprefix('#/').split('/'):
            value = value[part]
        return value
    return schema


@lru_cache
def validator(name):
    return Draft202012Validator({'$ref': '#/components/schemas/' + name, 'components': SPEC['components']}, format_checker=FormatChecker())


def validate_schema(name, data):
    errors = list(validator(name).iter_errors(data))[:30]
    if errors:
        raise ApiError(422, 'VALIDATION_ERROR', '数据不符合接口契约', details=[{
            'field': '.'.join(map(str, e.path))[:300] or None,
            'row_number': None, 'code': str(e.validator), 'message': '字段类型、格式、范围或必填条件不符合要求',
        } for e in errors])


def validate_value(schema, value):
    doc = {**schema, 'components': SPEC['components']}
    if not Draft202012Validator(doc, format_checker=FormatChecker()).is_valid(value):
        raise ApiError(422, 'VALIDATION_ERROR', '请求参数格式不正确')


def schema_defaults(name, data):
    result = copy.deepcopy(data)
    schema = resolve(SCHEMAS[name])
    if 'oneOf' in schema:
        for option in schema['oneOf']:
            opt = resolve(option)
            prop = opt.get('properties', {}).get('plan_type', {})
            if result.get('plan_type') in prop.get('enum', [prop.get('const')]):
                schema = opt
                break
    for key, spec in schema.get('properties', {}).items():
        if key in result:
            continue
        spec = resolve(spec)
        if 'default' in spec:
            result[key] = copy.deepcopy(spec['default'])
        elif spec.get('type') == 'array':
            result[key] = []
        elif spec.get('type') == 'null' or any(x.get('type') == 'null' for x in spec.get('anyOf', [])):
            result[key] = None
    return result
