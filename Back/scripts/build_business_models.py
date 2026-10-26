"""Generate explicit relational columns from the approved DTO contract.

Developer tool only. Runtime does not generate database tables or models.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = json.loads((ROOT.parent / 'Front/contracts/openapi.json').read_text(encoding='utf-8'))['components']['schemas']
GROUPS = {
    'store': ['Store', 'PlatformAccount', 'AuthorizationSession'],
    'product': ['Product', 'PlatformMapping'],
    'inventory': ['Sku', 'Inventory', 'InventoryMovement'],
    'competitor': ['Competitor', 'CompetitorMonitor', 'MonitorSnapshot', 'ParseResult'],
    'round': ['OperatingRound', 'RoundSnapshot'],
    'diagnosis': ['Diagnosis'],
    'creative': ['CreativePlan'],
    'job': ['GenerationJob', 'JobEvent'],
    'file': ['FileObject'],
    'asset': ['Asset'],
    'promotion_link': ['PromotionLink'],
    'ad_recommendation': ['AdRecommendation', 'Confirmation'],
    'ad_experiment': ['AdExperiment'],
    'performance': ['PerformanceRecord'],
    'review': ['ReviewReport'],
    'revision': ['ResourceRevision'],
    'import_batch': ['ImportBatch'],
    'settings': ['ModelConfig', 'SystemSettings', 'QueueSettings'],
    'audit_log': ['AuditLog'],
}
TABLES = {name: re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower() + 's' for names in GROUPS.values() for name in names}
TABLES.update({'Inventory': 'inventories', 'Diagnosis': 'diagnoses', 'ImportBatch': 'import_batches', 'FileObject': 'files', 'GenerationJob': 'generation_jobs', 'SystemSettings': 'system_settings', 'QueueSettings': 'queue_settings', 'User': 'users'})
KEYS = {'AuthorizationSession': 'authorization_session_id', 'ResourceRevision': 'revision_id'}
SYNTHETIC = {'SystemSettings', 'QueueSettings', 'ParseResult'}
SINGLETONS = {'SystemSettings', 'QueueSettings'}
DIRECT_FKS = {
    'store_id': 'Store', 'product_id': 'Product', 'sku_id': 'Sku',
    'round_id': 'OperatingRound', 'previous_round_id': 'OperatingRound',
    'snapshot_id': 'RoundSnapshot', 'competitor_id': 'Competitor',
    'monitor_id': 'CompetitorMonitor', 'file_id': 'FileObject',
    'main_image_file_id': 'FileObject', 'creative_plan_id': 'CreativePlan',
    'job_id': 'GenerationJob', 'source_job_id': 'GenerationJob',
    'parent_asset_id': 'Asset', 'related_link_id': 'PromotionLink',
    'promotion_link_id': 'PromotionLink', 'experiment_id': 'AdExperiment',
    'import_id': 'ImportBatch', 'model_config_id': 'ModelConfig',
    'text_model_config_id': 'ModelConfig', 'image_model_config_id': 'ModelConfig',
    'video_model_config_id': 'ModelConfig', 'operator_id': 'User',
    'created_by': 'User', 'reviewed_by': 'User', 'confirmed_by': 'User',
    'submitted_by': 'User', 'actor_id': 'User',
}
REF_FKS = {
    'diagnosis': 'Diagnosis', 'selected_diagnosis': 'Diagnosis',
    'source_review': 'ReviewReport', 'related_asset': 'Asset',
    'title_plan': 'CreativePlan', 'recommendation': 'AdRecommendation',
    'creative_plan': 'CreativePlan', 'generated_asset': 'Asset',
}
COMPUTED = {'Store': {'product_count', 'low_stock_sku_count'}, 'Inventory': {'available_qty', 'is_low_stock'}, 'ModelConfig': {'secret_configured'}}
INTERNAL_COLUMNS = {
    'Store': ["singleton_key = mapped_column(Integer, nullable=False, default=1, server_default='1', unique=True)"],
    'AuthorizationSession': ["account_id = mapped_column(Uuid(as_uuid=True), ForeignKey('platform_accounts.id'), nullable=False, index=True)", "consumed_at = mapped_column(DateTime(timezone=True), nullable=True)"],
    'ParseResult': ["job_id = mapped_column(Uuid(as_uuid=True), ForeignKey('generation_jobs.id'), nullable=False, unique=True)"],
    'RoundSnapshot': ["product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True)"],
    'Confirmation': ["recommendation_id = mapped_column(Uuid(as_uuid=True), ForeignKey('ad_recommendations.id'), nullable=False, index=True)", "product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True)", "round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=True, index=True)"],
    'ResourceRevision': ["product_id = mapped_column(Uuid(as_uuid=True), ForeignKey('products.id'), nullable=False, index=True)", "round_id = mapped_column(Uuid(as_uuid=True), ForeignKey('operating_rounds.id'), nullable=True, index=True)"],
    'Asset': ["output_index = mapped_column(Integer, nullable=True)"],
}


def unnullable(schema):
    if 'anyOf' in schema:
        variants = [s for s in schema['anyOf'] if s.get('type') != 'null']
        if len(variants) == 1:
            return variants[0], len(variants) != len(schema['anyOf'])
    return schema, schema.get('type') == 'null'


def dto(name):
    if name != 'CreativePlan':
        return SCHEMAS[name]
    result = copy.deepcopy(SCHEMAS['MainImagePlan'])
    result['properties']['plan_type']['enum'] = ['main_image', 'video_script', 'title']
    return result


HEADER = '''# Generated from Front/contracts/openapi.json. Review changes before migrations.
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column
from uuid import UUID, uuid4
from app.db.base import Base, utcnow

'''


def generate(name):
    schema = dto(name)
    table = TABLES[name]
    key = KEYS.get(name, 'id')
    properties = schema['properties']
    lines = [f'class {name}(Base):', f'    __tablename__ = {table!r}', f'    SCHEMA_NAME = {name!r}', f'    __dto_fields__ = {tuple(properties)!r}', f'    __pk_field__ = {key!r}']
    constraints, columns, refs, money, ratios = [], [], {}, [], []
    if name in SYNTHETIC:
        default = "lambda: UUID('00000000-0000-0000-0000-000000000001')" if name in SINGLETONS else 'uuid4'
        columns.append(f'id = mapped_column(Uuid(as_uuid=True), primary_key=True, default={default})')
    for field, raw in properties.items():
        if field in COMPUTED.get(name, set()):
            continue
        spec, nullable = unnullable(raw)
        nullable = nullable or field not in schema.get('required', [])
        if spec.get('$ref') == '#/components/schemas/ResourceRef':
            target = REF_FKS[field]
            refs[field] = (field + '_id', field + '_version')
            alter = ', use_alter=True' if name == 'OperatingRound' else ''
            columns += [f"{field}_id = mapped_column(Uuid(as_uuid=True), ForeignKey('{TABLES[target]}.id'{alter}), nullable={nullable}, index=True)", f"{field}_version = mapped_column(Integer, nullable={nullable})"]
            constraints.append(f"CheckConstraint('{field}_version >= 1', name='{field}_version_positive')")
            if nullable:
                constraints.append(f"CheckConstraint('({field}_id IS NULL) = ({field}_version IS NULL)', name='{field}_ref_complete')")
            continue
        fmt, typ = spec.get('format'), spec.get('type')
        args = []
        if fmt == 'uuid':
            sql_type = 'Uuid(as_uuid=True)'
            if field in DIRECT_FKS and field != key:
                args.append(f"ForeignKey('{TABLES[DIRECT_FKS[field]]}.id')")
        elif fmt == 'date-time':
            sql_type = 'DateTime(timezone=True)'
        elif fmt == 'date':
            sql_type = 'Date'
        elif typ == 'integer':
            sql_type = 'BigInteger' if spec.get('maximum', 0) > 2147483647 else 'Integer'
        elif typ == 'boolean':
            sql_type = 'Boolean'
        elif typ == 'number':
            sql_type = 'Numeric(20, 6)'
        elif typ == 'string' and '0,11' in spec.get('pattern', ''):
            if '[0-9]{2}' in spec['pattern']:
                sql_type = 'Numeric(14, 2)'
                money.append(field)
            else:
                sql_type = 'Numeric(18, 6)'
                ratios.append(field)
            constraints.append(f"CheckConstraint('{field} >= 0', name='{field}_nonnegative')")
        elif typ in ('object', 'array') or '$ref' in spec or 'oneOf' in spec:
            sql_type = 'JSONB'
        elif typ == 'null':
            sql_type = 'Numeric(18, 6)'
            constraints.append(f"CheckConstraint('{field} IS NULL', name='{field}_reserved_null')")
        else:
            max_len = spec.get('maxLength')
            sql_type = f'String({max_len})' if max_len else 'Text'
        if field == key:
            args += ['primary_key=True', 'default=uuid4']
        else:
            args.append(f'nullable={nullable}')
            if field in ('created_at', 'updated_at'):
                args.append('default=utcnow')
            elif field == 'version':
                args.append('default=1')
            elif typ == 'array' and spec.get('minItems', 0) == 0:
                args.append('default=list')
            elif 'default' in spec:
                args.append(f'default={spec["default"]!r}')
            if field in DIRECT_FKS:
                args.append('index=True')
        columns.append(f'{field} = mapped_column({sql_type}, {", ".join(args)})')
        if 'enum' in spec:
            values = ', '.join(repr(v) for v in spec['enum'])
            constraints.append(f'CheckConstraint({f"{field} IN ({values})"!r}, name={field + "_enum"!r})')
        if typ == 'integer':
            for bound, op in [('minimum', '>='), ('maximum', '<=')]:
                if bound in spec:
                    constraints.append(f"CheckConstraint('{field} {op} {spec[bound]}', name='{field}_{bound}')")
    columns += INTERNAL_COLUMNS.get(name, [])
    extras = {
        'Store': ["CheckConstraint('singleton_key = 1', name='single_store')"],
        'SystemSettings': ["CheckConstraint(\"id = '00000000-0000-0000-0000-000000000001'\", name='singleton')"],
        'QueueSettings': ["CheckConstraint(\"id = '00000000-0000-0000-0000-000000000001'\", name='singleton')"],
        'Sku': ["UniqueConstraint('sku_code', name='uq_skus_code')"],
        'Inventory': ["UniqueConstraint('sku_id', name='uq_inventory_sku')", "CheckConstraint('stock_qty >= locked_qty', name='stock_locked')"],
        'CompetitorMonitor': ["UniqueConstraint('competitor_id', name='uq_monitor_competitor')"],
        'OperatingRound': ["UniqueConstraint('product_id', 'round_no', name='uq_round_product_number')", "Index('uq_round_active_product', 'product_id', unique=True, postgresql_where=text(\"status = 'active'\"))"],
        'CreativePlan': ["Index('uq_plan_selected_kind', 'round_id', 'plan_type', unique=True, postgresql_where=text(\"status = 'selected'\"))"],
        'JobEvent': ["UniqueConstraint('job_id', 'sequence', name='uq_job_event_sequence')"],
        'Asset': ["UniqueConstraint('source_job_id', 'output_index', name='uq_asset_job_output')", "CheckConstraint('output_index IS NULL OR output_index >= 0', name='output_index_nonnegative')", "CheckConstraint('(creative_plan_id IS NULL) = (creative_plan_version IS NULL)', name='creative_ref_complete')"],
        'PromotionLink': ["UniqueConstraint('tracking_code', name='uq_promotion_tracking')"],
        'PerformanceRecord': ["Index('uq_performance_product_day', 'product_id', 'record_date', unique=True, postgresql_where=text(\"NOT voided AND granularity = 'product_day'\"))", "Index('uq_performance_experiment_day', 'experiment_id', 'record_date', unique=True, postgresql_where=text(\"NOT voided AND granularity = 'experiment_day'\"))", "CheckConstraint(\"(granularity = 'product_day' AND experiment_id IS NULL) OR (granularity = 'experiment_day' AND experiment_id IS NOT NULL)\", name='granularity_reference')"],
        'ResourceRevision': ["UniqueConstraint('resource_type', 'resource_id', 'version', name='uq_resource_revision_version')"],
        'AdExperiment': ["CheckConstraint('planned_end_date >= planned_start_date', name='planned_dates')", "CheckConstraint('actual_end_at IS NULL OR actual_start_at IS NULL OR actual_end_at >= actual_start_at', name='actual_dates')"],
        'ReviewReport': ["CheckConstraint('period_end >= period_start', name='period_dates')"],
        'AuthorizationSession': ["UniqueConstraint('state', name='uq_auth_placeholder_state')"],
        'PlatformMapping': ["CheckConstraint('(sku_id IS NULL) = (platform_sku_id IS NULL)', name='sku_mapping_pair')", "Index('uq_mapping_external_sku', 'platform', 'platform_sku_id', unique=True, postgresql_where=text('platform_sku_id IS NOT NULL'))"],
    }
    constraints += extras.get(name, [])
    lines += [f'    __ref_fields__ = {refs!r}', f'    __money_fields__ = {tuple(money)!r}', f'    __ratio_fields__ = {tuple(ratios)!r}', f'    __computed_fields__ = {tuple(COMPUTED.get(name, set()))!r}']
    lines += ['    ' + c for c in columns]
    if constraints:
        lines += ['    __table_args__ = ('] + ['        ' + c + ',' for c in constraints] + ['    )']
    return '\n'.join(lines) + '\n\n'


def main():
    folder = ROOT / 'app/models'
    folder.mkdir(parents=True, exist_ok=True)
    imports = []
    for module, names in GROUPS.items():
        (folder / f'{module}.py').write_text(HEADER + '\n'.join(generate(name) for name in names), encoding='utf-8')
        imports.append(f'from app.models.{module} import ' + ', '.join(names))
    names = [n for ns in GROUPS.values() for n in ns]
    registry = '\n'.join(imports) + '\nfrom app.models.internal import *\n\nMODELS = {\n' + ''.join(f'    {n!r}: {n},\n' for n in names) + '}\n'
    registry += '''
# The authentication model is maintained separately from generated business tables.
from app.models.user import User
from app.models.session import LoginSession
from app.models.login_limit import LoginLimit
User.SCHEMA_NAME = 'User'
User.__dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'username', 'display_name', 'role', 'status', 'last_login_at')
User.__pk_field__ = 'id'
User.__ref_fields__ = {}
User.__money_fields__ = ()
User.__ratio_fields__ = ()
User.__computed_fields__ = ()
MODELS['User'] = User
MODELS.update(INTERNAL_MODELS)
'''
    (folder / '__init__.py').write_text(registry, encoding='utf-8')
    print(f'Generated {len(names)} business models in {len(GROUPS)} modules')


if __name__ == '__main__':
    main()
