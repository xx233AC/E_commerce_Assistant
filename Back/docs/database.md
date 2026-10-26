# 数据库设计与迁移

数据库采用 PostgreSQL。业务对象按实际字段建关系表，UUID 作为主键；金额使用 NUMERIC(14,2)，比率使用 NUMERIC(18,6)，计数使用整数或 BIGINT，经营日使用 DATE，时刻使用 TIMESTAMP WITH TIME ZONE。API 序列化金额为两位小数字符串、时刻为 UTC Z。

JSONB 只用于数组、AI 结构化内容、调用上下文及不可变历史快照；商品、库存、任务、投放预算和经营数据等可查询字段均有独立类型列。数据库列和公开接口 DTO 分开，内部存储地址、授权状态散列、任务输入、用户密码等不会混入公开对象。

## 表与职责

| 模块 | 表 | 关联与说明 |
|---|---|---|
| 认证 | users、login_sessions、login_limits | 用户、可撤销会话、持久化失败次数 |
| 店铺 | stores、platform_accounts、authorization_sessions、authorization_states | singleton_key 限制唯一店铺；平台授权仅占位元数据 |
| 商品 | products、platform_mappings、skus | 商品归店铺，SKU 归商品，sku_code 全店唯一 |
| 库存 | inventories、inventory_movements | 每 SKU 一份库存；调整流水与库存修改同事务 |
| 竞品 | competitors、competitor_monitors、monitor_snapshots、parse_results、monitor_dispatches | 每竞品一个监控；解析只产候选；按监控和计划时间去重 |
| 轮次 | operating_rounds、round_snapshots | 轮次归商品，快照不可变；前轮和来源报告版本保留 |
| AI 内容 | diagnoses、creative_plans、ad_recommendations、review_reports | 结构化内容 JSONB；product_id、round_id 与引用版本独立列 |
| 历史 | resource_revisions、confirmations、performance_revisions | 不可变 AI 修订、人工确认记录、经营数据更正快照 |
| 文件素材 | files、file_storage、assets | 公开文件元数据与内部 MinIO bucket/key 分开；真实素材关联文件与任务 |
| 链接 | promotion_links、click_events | 唯一 tracking_code；点击事件只保存去重散列，不存明文 IP/UA |
| 实验数据 | ad_experiments、performance_records | 人工执行实验；日经营数据按商品/实验口径分别去重 |
| 任务 | generation_jobs、job_events、job_runtime、job_outputs | 持久化任务、顺序事件、租约和恢复状态、输出去重 |
| 导入 | import_batches、import_state | 批次状态与私有预览行；预览不写业务表 |
| 配置 | model_configs、system_settings、queue_settings | 配置密钥只引用环境变量名；系统和队列配置各一个单例 |
| 可追踪性 | idempotency_records、audit_logs、model_calls | 24 小时幂等重放、业务操作审计、模型用量与版本，无敏感原文 |

当前共 45 张表。`alembic_version` 由 Alembic 额外管理。第二迁移允许平台归因计数出现点击大于曝光、订单大于点击等情况，由业务汇总给出警告；第三迁移统一系统和队列配置表名称。

## 数据库强制约束

- stores.singleton_key 固定 1 且唯一，数据库保证单店铺。
- operating_rounds 对 status='active' 的 product_id 建部分唯一索引；同商品轮次号唯一。
- creative_plans 对 status='selected' 的 (round_id,plan_type) 建部分唯一索引。
- SKU 编号唯一，每 SKU 库存唯一，库存非负且 locked_qty 固定 0。
- 有效商品日数据唯一键为 (product_id,record_date)，有效实验日数据为 (experiment_id,record_date)，均排除 voided=true。round_id 不参与该去重。
- resource_revisions 唯一键为 (resource_type,resource_id,version)；performances 历史以 (record_id,version) 去重。
- job_outputs 以 (job_id,output_index) 唯一；素材同时保留 (source_job_id,output_index) 唯一约束。
- job_events 的 (job_id,sequence) 唯一；monitor_dispatches 的 (monitor_id,scheduled_at) 唯一。
- 实验计划/实际结束不得早于开始；计数、金额、枚举按契约施加 CHECK 约束。

ResourceRef 在关系表中拆为资源 ID 和版本列；Repo 接收和返回仍为 `{id,version}`。资源 ID 有外键约束，历史版本存在性与同商品同轮次归属由服务层在事务内验证。

数据库触发器禁止对 resource_revisions、round_snapshots、performance_revisions、job_outputs 做 UPDATE/DELETE，禁止修改 job_runtime.input 和 job_id；任务可更新心跳、租约和恢复结果。后续新增修订必须 INSERT，不能覆写旧快照。

## 事务与接口数据

Repo 只 flush，不 commit；HTTP 服务和 Worker 的事务边界决定最终提交。并发修改先锁定资源并检查 If-Match，再同时保存业务对象、修订、审计和幂等结果。库存调整与流水、任务成功与输出登记、导入行状态与业务写入应同事务提交。

Store 的商品/低库存数量实时查询；Inventory 的 available_qty 与 is_low_stock 实时计算；ModelConfig.secret_configured 根据服务端环境变量是否存在计算，均不维护容易失真的冗余列。

公开业务 kind 只序列化契约字段。内部 kind（JobRuntime、FileStorage、ImportState 等）返回内部列，仅供后端调用，不可直接作为 HTTP 响应。默认分页排序为 updated_at DESC,id DESC；缺 updated_at 的对象使用 created_at DESC,id DESC。

## 迁移方法

`migrations/versions/20261023_0001_initial.py` 是冻结的首迁移，含表、索引、外键和不可变触发器；后续变动由 0002、0003 顺序执行。迁移运行时不导入当前模型重建结构，因此后续模型变动不会改变旧迁移。

先检查目标库，再运行 `python -m alembic upgrade head`；禁止在应用启动中自动 create_all。可以用 `python -m alembic upgrade head --sql` 离线审阅 DDL，该命令不连接数据库。已有版本上线后，字段变更生成新的迁移并人工检查，不能重新生成覆盖首迁移。

`scripts/build_business_models.py` 和 `scripts/build_initial_migration.py` 是本次初始设计的生成辅助工具；运行时不依赖它们。前者输出可直接阅读的静态 SQLAlchemy 模型，后者仅用于首次发布前冻结迁移。

## 已验证范围

本模块已离线编译全部 PostgreSQL 建表与索引语句，并对默认分页排序、金额/日期/UUID/版本引用转换、内部字段隔离、不可变仓储操作、关键部分唯一索引运行单元测试。真实 PostgreSQL 的迁移与业务闭环需在集成测试阶段另行验证，离线测试不等同真实数据库验收。
