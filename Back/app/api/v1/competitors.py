from app.services import competitors

HANDLERS = {
    'GET /products/{product_id}/competitors': competitors.list_competitors,
    'POST /products/{product_id}/competitors': competitors.create_competitor,
    'PATCH /products/{product_id}/competitors/{competitor_id}': competitors.patch_competitor,
    'POST /products/{product_id}/competitors/import-url-tasks': competitors.create_parse_task,
    'GET /products/{product_id}/link-parse-tasks': competitors.list_parse_tasks,
    'GET /products/{product_id}/link-parse-tasks/{task_id}': competitors.get_parse_task,
    'POST /products/{product_id}/link-parse-tasks/{task_id}/run': competitors.run_parse_task,
    'GET /products/{product_id}/link-parse-tasks/{task_id}/result': competitors.get_parse_result,
    'POST /products/{product_id}/competitors/{competitor_id}/monitor': competitors.create_monitor,
    'GET /products/{product_id}/competitors/{competitor_id}/monitor': competitors.get_monitor,
    'PATCH /products/{product_id}/competitors/{competitor_id}/monitor': competitors.patch_monitor,
    'GET /products/{product_id}/competitors/{competitor_id}/monitor/snapshots': competitors.list_snapshots,
}
