from functools import partial

from app.services import imports

HANDLERS = {
    'POST /workspace/imports': imports.create_import,
    'GET /workspace/imports': imports.list_imports,
    'GET /workspace/imports/{import_id}': imports.get_import,
    'GET /workspace/imports/{import_id}/preview': imports.preview,
    'GET /workspace/imports/{import_id}/errors': imports.errors,
    'POST /workspace/imports/{import_id}/commit': imports.commit_import,
    'POST /products/{product_id}/performance-records/import': imports.create_performance_import,
    'GET /workspace/templates/products': partial(imports.template, kind='products'),
    'GET /workspace/templates/sku-inventory': partial(imports.template, kind='sku_inventory'),
    'GET /workspace/templates/performance-records': partial(imports.template, kind='performance_records'),
    'GET /workspace/templates/platform-mappings': partial(imports.template, kind='platform_mappings'),
}
