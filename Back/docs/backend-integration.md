# 前后端联调说明

前端目录 `D:\E_commerce_Assistant\Front`，后端目录 `D:\E_commerce_Assistant\Back`。接口请求和响应以两端 `contracts/openapi.json` 为依据，业务状态规则以中文接口契约补充。当前契约为 128 个 HTTP 操作，后端采用中央适配层统一处理契约校验、角色、幂等、版本和响应封装。

## 请求如何到达后端

本地开发：浏览器 → Vite 5173 → `/api/v1/...` → FastAPI 8000。浏览器 Network 中出现 5173 是正常的，这是浏览器直接访问的代理地址。后端注册前缀 `/api/v1`，Vite 保留原路径转发，不截掉 `/api`。

容器部署：浏览器 → Nginx → 静态 React 页面或 `/api/v1/...` → API 容器。FastAPI、Worker、scheduler 复用相同 PostgreSQL 和 MinIO 配置。容器内部 localhost 指向自身，不能照抄 Windows SSH 隧道地址。

## 每次开发一个接口应看什么

| 位置 | 用途 |
|---|---|
| `Front/contracts/接口契约.md` | 业务边界、角色、状态机、闭环要求 |
| `Front/contracts/openapi.json` | 路径、方法、必填字段、枚举和响应结构 |
| `Front/src/api/client.ts` | 实际请求头、JSON/上传、错误和下载规则 |
| 对应 `Front/src/pages/*.tsx` | 页面提交字段、路径参数、查询条件及操作顺序 |
| 浏览器 Network → Headers/Payload/Response | 实际请求是否符合约定、实际返回什么 |
| 后端 API/Worker 日志 | HTTP 请求和异步任务处理发生在哪一环 |

## 全局协议

- 成功 JSON 为 `{ "data": ..., "meta": { "request_id": "UUID" } }`；列表还有分页元数据，以原契约为准。
- 错误为 `{ "error": { "code": "...", "message": "...", "details": [], "retryable": false }, "request_id": "UUID" }`。
- 登录返回 Bearer JWT 和用户信息；前端在 sessionStorage 保存令牌。有效期 7200 秒，每次请求还检查可撤销数据库会话。
- 业务 POST/PATCH 使用 UUID `Idempotency-Key`；相同用户、方法、路径、键和请求内容重放原成功结果，防止重复加库存、任务和导入。
- 契约标记需要并发保护的更新携带 `If-Match: "当前version"`，旧版本返回 412。重放已成功幂等请求时不因为当前版本前进而重复执行。
- 金额采用两位小数字符串，例如 `"100.00"`；经营日为 `YYYY-MM-DD`；时刻为 UTC Z，界面按 Asia/Shanghai 展示。
- 文件上传使用 multipart，浏览器自行设置 boundary；不能把 FormData 强行标成 application/json。
- 耗时生成返回 202 和 JobAccepted；导入返回 202 和 ImportAccepted。分别按返回的 poll_url 轮询，不把导入批次当作生成任务。

## 建议联调顺序

先完成登录、`/auth/me`、退出，再验证管理员/运营/查看者权限。接着验证店铺、商品、SKU、库存与真实文件上传，然后推进轮次、诊断、创意、素材、投放、实验、经营数据和复盘。

每个写接口至少检查：真实数据成功、错误字段、错误角色、错误资源归属、旧 If-Match、相同幂等键重放。任务接口再检查失败、重试、取消和迟到结果；导入检查预览无写入、部分成功、全量冲突回滚和同一行不会重复加库存。

## 文件与模型依赖

本地 PostgreSQL 使用 15433；MinIO S3 API 使用 19000；19001 控制台不能替代 S3 API。文件保存在专用私有桶，接口返回有效期约 5 分钟的签名访问地址。内部 MinIO endpoint 必须能被后端访问，public endpoint 必须能被浏览器访问。当前实现两者共用 MINIO_SECURE，因此都应使用一致的 HTTP/HTTPS 模式。

文本模型通过服务端环境变量保存密钥；模型配置里的 secret_env_name 只填变量名。创建模型配置、指定系统文本模型、开放准确的供应商域名后才调用真实服务。未配置时应返回明确错误，不伪造诊断和建议。

`/workspace/demo-data` 只用于管理员显式开启的空业务空间验证，默认关闭。服务端 `DEMO_ENABLED` 与系统 `demo_data_enabled` 必须同时为 true；请求 `{"dataset_version":"v1","mode":"create_if_empty"}` 返回异步任务。任务成功后可查看两个已完成轮次及第二轮的复盘引用。演示使用独立 demo 模型配置，不改变真实文本模型选择，不调用真实模型或广告平台。源照片真实存于私有 MinIO；价格、指标等预设内容均为演示，不能作为业务事实。

图片、视频现已接入智谱官方异步接口。图片模型 glm-image；视频模型 cogvideox-3，watermark_enabled=false。任务保存供应商编号，轮询结果并落入私有 MinIO；素材默认 pending，需人工审核。完整参数限制和恢复方式见 `zhipu-media.md`。

## 常见现象

| 现象 | 优先检查 |
|---|---|
| 登录 502 | API 是否启动、Vite 代理目标和8000端口；这通常不是密码错误 |
| 登录 401 | 账号密码、账号状态、令牌过期或数据库会话撤销 |
| 接口 422 | 对照 Payload 和 Schema 检查类型、必填字段及业务前置条件 |
| 接口 412 | 刷新当前资源版本，重新确认修改后提交 |
| 接口 409 | 状态冲突、重复业务记录、只读轮次、资源正在被引用等 |
| 页面提示响应不符合约定 | 检查 data/meta 外层、必填可空字段、金额字符串 |
| 文件上传 503 | 19000 S3 隧道、MinIO账号权限、私有桶可达性 |
| 图片地址打不开 | public endpoint 是否可从当前浏览器访问、签名是否过期 |
| 任务一直 pending | Worker 是否运行、队列配置和模型是否可用 |
| 导入一直 validating/committing | Worker 日志和 ImportBatch 状态；不要重复建任务来替代排查 |
| 竞品监控没有定期执行 | scheduler 是否运行、监控 next_run_at 与状态 |

浏览器看到 `/health` 返回 ok 只说明 API 存活。数据库、MinIO、真实模型调用和 CentOS 7 容器部署都需要各自验证，不能据此推断整个业务闭环已验收。

## 本轮联调记录（2026-10-24）

- PostgreSQL：45 张应用表及三个迁移已落库；106 项后端测试通过，其中业务测试使用真实 PostgreSQL 外层回滚。
- MinIO：真实商品照片上传、五分钟签名读取、HTTP Range、私有桶匿名拒绝、上传重放、素材登记与审核的独立测试通过；只删除该测试创建的对象。
- 前端：26 项测试通过，生产构建通过，128 个操作均绑定契约。修正新商品上传前必须先保存草稿，以及素材同步请求不应携带 round_id；大文件上传单独使用 15 分钟超时。
- 浏览器：真实登录进入空工作台、读取 DeepSeek Flash 配置通过；注销后的旧凭据返回 401。临时联调账号已经删除。
- 文本模型：DeepSeek Flash 已完成一次真实商品诊断并通过结构校验；六类文本判断均有提示词、结构和业务校验，未逐类重复消费真实模型额度。
- 契约勘误：登录失败的实际状态为 401，已补入前后端同份 OpenAPI 的 `/auth/login` 响应声明，路径和请求结构不变。
- 后续补充：图片/视频已接入智谱，媒体专项验收见 `zhipu-media.md`。CentOS 7 容器部署未在目标机实际执行。
