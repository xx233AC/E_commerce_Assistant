# 导入中心

四类模板均只有表头，不含业务示例数据：`templates/imports/products.csv`、`sku-inventory.csv`、`performance-records.csv`、`platform-mappings.csv`。下载接口返回相同 UTF-8 BOM CSV 表头。

流程：上传 purpose=import 的文件 → 创建预览批次 → Worker 校验 → 查看预览和错误行 → 使用 preview_token 与 If-Match 显式提交 → 查看批次结果。经营数据快捷入口和统一入口共用相同逻辑，轮询对象是 ImportBatch。

CSV 限 UTF-8，可有 BOM；XLSX 仅读取首工作表，不执行公式。文件最大 10 MiB，最多 10000 数据行（系统设置可进一步缩小），最多 100 列，每格最多 12000 字符。重复表头、缺少必填列、未知映射、未知列或文件损坏使批次失败；字段值错误记录原文件行号并仍产生预览。空白数据行跳过但后续行号保留。

预览仅写 import_batches/import_state，不新建商品、SKU、映射或经营记录。映射和文件 SHA256 固化在私有批次上下文。预览令牌有效 30 分钟。重复业务行会将两份均标记无效，不由文件顺序决定覆盖关系。

产品只新建 draft。已有 SKU 的行只能调整库存增量、阈值和库位；填写 SKU 名称、规格或价格成本会报 SKU_EDIT_NOT_SUPPORTED。新 SKU 与库存增量同事务创建。经营数据在后台标记 source=import，遵守商品/实验日去重以及实际执行日期范围。

allow_partial=false 在一个事务中提交全部行，实时冲突使全部业务写入回滚并把批次标记失败。allow_partial=true 每行单独提交，业务写入与该行成功状态在同一事务，成功行永久跳过；任务恢复不会重复增加库存。无效预览行也计入终态 failed_rows。

Worker 入口 `process_import(ctx,batch_id)` 使用独立固定 PostgreSQL 连接持有会话 advisory lock，防止多个 Worker 交错提交同一批次。该入口只供后台调用；调用者不得携带未提交的写事务。进程崩溃后数据库释放连接锁，后续 Worker 可以恢复 pending 行。每次执行重新检查实际发起人的启用状态和写权限。

解析及契约单元测试不接外部服务。PostgreSQL 测试通过 `RUN_POSTGRES_TESTS=1` 显式运行，所有测试数据位于外层回滚事务，文件内容使用测试替身，不上传 MinIO；因此该测试验证数据库事务语义，不代表 MinIO 端到端上传验收。
