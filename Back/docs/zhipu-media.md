# 智谱图片与视频接入

文本六类判断仍使用 `deepseek-flash`。图片使用 `glm-image`，视频使用 `cogvideox-3`。使用官方 REST 调用方式，与文档的 cURL 示例一致，通过项目已有 HTTP 客户端发送，不引入额外框架。

## 调用与参数

| 用途 | 官方接口 |
|---|---|
| 图片异步提交 | `POST https://open.bigmodel.cn/api/paas/v4/async/images/generations` |
| 视频异步提交 | `POST https://open.bigmodel.cn/api/paas/v4/videos/generations` |
| 查询结果 | `GET https://open.bigmodel.cn/api/paas/v4/async-result/{id}` |

认证使用 `Authorization: Bearer`，密钥来自 `Back/.env` 中的 `ZHIPU_API_KEY`。数据库和前端只保存变量名称、是否配置及模型信息。修改环境变量后重启 API/Worker。

- 图片：`quality=hd`。支持项目比例对应尺寸：1:1 为 1280×1280，3:4 为 1152×1536，4:3 为 1536×1152，9:16 为 1152×2048，16:9 为 2048×1152。每个本地任务可申请 1—4 张，后台逐张提交并分别记录供应商任务编号，计费按实际提交次数。当前官方 GLM-Image 接口为文生图，不接收参考图；方案或请求存在参考图时提前拒绝，不会悄悄忽略。负向提示合并为文字约束，不使用未公开的参数。
- 视频：`quality=quality`、`fps=30`、`with_audio=false`、`watermark_enabled=false`。仅 5 或 10 秒，脚本分镜时长合计须一致；提示词最多 512 字符。720p 对应横版 1280×720 或竖版 720×1280；1080p 对应 1920×1080 或 1080×1920。方形只能使用项目中的 1080p 档，对应供应商实际尺寸 1024×1024，表单中明确提示。最多两张 JPEG/PNG 首尾帧，每张 5MiB；用 Base64 发送，供应商不需要访问本地 SSH 地址。
- 温度：这两个媒体接口未定义 `temperature`，因此没有发送无效温度参数。文本保留现有 DeepSeek 配置；其默认思考模式下温度参数也不生效。
- 视频关闭水印需要智谱账号已开通去水印权限；按用户指定发送 false，不会在失败时偷偷改回 true。

## 业务流程与恢复

前端仍使用原来的两个 `/api/v1/products/{product_id}/creative-plans/{creative_plan_id}/images/generate`、`videos/generate` 接口，契约无变更。

1. 校验当前商品、轮次、已选定方案版本、模型能力和参考素材。
2. 将模型配置、创意方案和参数保存为任务输入快照，返回 202。
3. Worker 先记录提交意图，再调用智谱；收到编号立即持久化。轮询期间持续续租，支持取消、超时。
4. 下载结果时限制地址、重定向、大小和时间；验证文件内容、尺寸、视频时长，再写入私有 MinIO。
5. 在一个事务中创建 FileObject、FileStorage、Asset、JobOutput，并将任务标为成功。素材 `origin=generated`、`execution_mode=real`、`review_status=pending`，保留模型、来源任务和方案版本。
6. 用户审核通过后，才可进入投放建议与实验。

原 API 幂等重放不会重复入队。智谱的 request_id 只作追踪，不能当作防重复扣费保证。POST 超时、连接中断或响应不明会标记 `PROVIDER_SUBMISSION_UNKNOWN` 并阻止盲目重试；需要按后台记录核对智谱受理状态。已拿到任务编号而下载/存储失败时，手动重试继续同步原结果，不再次付费生成。供应商已确认 FAIL 时，须修改方案并重新发起生成。取消仅停止本地查询和结果发布，已提交的供应商任务可能继续生成并计费。

取消或失败后仅清理本任务未发布的存储对象；数据库提交结果不明时保留对象等待核对，避免误删成功素材。服务崩溃后已知任务编号可通过原任务重试继续查询；遗留未发布对象可在确认任务终态后调用 `cleanup_unpublished(job_id)` 核对清理。

## 配置和验证

在 Back 目录执行 `python -m scripts.configure_zhipu`，登记两个媒体模型并设为默认，文本模型不变。该脚本重复执行不会新增同名同端点模型，也不会创建商品或店铺。

自动测试：`RUN_POSTGRES_TESTS=1` 启用 `tests/integration/test_media_worker_postgres.py`，覆盖 HTTP 幂等、队列、图片/视频文件验证、素材审核、存储失败恢复、提交状态未知和取消清理。外部服务使用测试替身，数据库在结束后回滚。

真实调用：`python -m scripts.verify_zhipu image` 和 `python -m scripts.verify_zhipu video` 各进行一次付费生成并验证 MinIO 上传/签名读取。任务编号及结果保存在忽略目录 `.local/zhipu-verification`；重复运行继续查询保存的任务，不重新提交。该检查不创建测试店铺或商品，临时 MinIO 对象检查后删除，生成文件留在本地。

## 2026-10-24 实际验收

- 后端完整测试 125 项通过（含真实 PostgreSQL 和 MinIO 检查）；前端 26 项测试、生产构建、128 个接口绑定检查通过。
- GLM-Image 一次真实调用成功：1280×1280 JPEG，135,860 字节。
- CogVideoX-3 一次真实调用成功：1920×1080 MP4，实际约 5.19 秒，2,409,124 字节；请求为 5 秒且 watermark_enabled=false，供应商接受并完成。
- 两份生成文件均通过真实 MinIO 上传和签名读取。测试对象已删除，测试业务记录均回滚；文件留在 `.local/zhipu-verification`，没有创建假商品。
- API、Worker 和调度器已重启；经前端代理读取确认三个默认模型分别为 deepseek-flash、glm-image、cogvideox-3，均启用且服务端密钥已配置。

## 官方参考

- [图片异步生成](https://docs.bigmodel.cn/api-reference/模型-api/图像生成异步)
- [视频异步生成](https://docs.bigmodel.cn/api-reference/模型-api/视频生成异步)
- [查询异步结果](https://docs.bigmodel.cn/api-reference/模型-api/查询异步结果)
- [DeepSeek 思考模式参数说明](https://api-docs.deepseek.com/guides/thinking_mode/)
