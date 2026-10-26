# 电商运营助手后端

本目录是单店铺电商运营助手后端，使用 FastAPI、SQLAlchemy、PostgreSQL 和 MinIO。前端仍位于 `D:\E_commerce_Assistant\Front`，接口以 `contracts/openapi.json` 和中文接口契约为准，统一前缀 `/api/v1`。

当前提供账号权限、商品/SKU/库存、竞品、运营轮次、六类 AI 判断任务、素材审核、推广链接、投放建议、人工实验、经营数据、导入、复盘和下一轮衔接。系统只记录人工在外部平台的投放执行，不自动花钱或修改平台预算。平台授权为占位流程。

三个 Agent 是同一后端内的逻辑模块：分析 Agent 负责诊断和复盘，创意 Agent 负责主图方案/脚本/标题及媒体流程，策略 Agent 负责投放建议。指标、库存建议、链接和实验展开用确定性代码计算。

文本判断使用 DeepSeek Flash；图片使用智谱 GLM-Image，视频使用智谱 CogVideoX-3，均通过官方 API 调用。生成文件验证后写入私有 MinIO，并登记为待人工审核素材；也可以上传已有素材。密钥仅保存在服务端环境变量，真实模式不会静默返回演示内容。媒体参数、恢复策略与验收见 `docs/zhipu-media.md`。

可选演示初始化要求管理员、完全空的业务空间、服务端 `DEMO_ENABLED=true` 与系统设置 `demo_data_enabled=true` 同时满足，再显式调用 `POST /api/v1/workspace/demo-data`，请求为 `{"dataset_version":"v1","mode":"create_if_empty"}`。它在一个数据库事务内创建两轮带演示标识的完整流程，不调用真实模型或广告平台。样例照片必须实际写入私有 MinIO，存储失败则不保留半套业务；已存在店铺或文件时拒绝初始化。默认配置保持关闭，当前业务库没有通过此接口初始化样例。演示的数字不代表真实经营数据；图片来源见 `demo-assets/README.md`。

## 本地启动

Windows 使用 Python 3.12，已有 `.venv`。以下命令在 PowerShell 中执行。保持 PostgreSQL 和 MinIO 所需 SSH 隧道运行。

```powershell
Set-Location 'D:\E_commerce_Assistant\Back'
```

先核对 `D:\E_commerce_Assistant\Back\.env`：

| 配置 | 本地用途 |
|---|---|
| `PG_HOST=127.0.0.1`、`PG_PORT=15433` | SSH 转发后的 PostgreSQL |
| `MINIO_ENDPOINT=127.0.0.1:19000` | MinIO S3 文件接口，后端上传/读取使用 |
| `MINIO_PUBLIC_ENDPOINT=127.0.0.1:19000` | 浏览器访问签名文件地址使用 |
| `MINIO_BUCKET=ecom-assistant-private` | 专用私有文件桶 |
| `PUBLIC_BASE_URL=http://127.0.0.1:5173` | 当前前端地址，生成推广链接使用 |
| `ZHIPU_API_KEY` | 智谱图片与视频生成共用的服务端密钥 |
| `JWT_SECRET` | 至少 64 字符的随机密钥，API/Worker 使用相同配置 |

账号密码由实际环境配置，本说明不提供固定密码。`.env.example` 只有占位示例。**19001 是 MinIO 控制台端口，打开控制台不代表 19000 的 S3 上传接口已连通。**

首次安装或更新依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

执行数据库迁移和初始化：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.bootstrap
```

初始化只创建运行配置和首个真实管理员，不创建商品、库存、投放或复盘假数据。数据库已有用户时不会覆盖密码。首次成功创建管理员后，凭据保存在：

```text
D:\E_commerce_Assistant\Back\.local\initial-admin.txt
```

登录后在用户管理中修改初始密码。这个文件和 `.env` 都不应提交版本库。

如果初始密码文件已删除且忘记密码，请在 Back 目录的 PowerShell/Terminal 中运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.reset_admin_password
```

输入已有管理员用户名和两次新密码（12—128 个字符，输入时不显示）。脚本只修改指定有效管理员的密码并撤销其旧登录会话，不会创建新账号，也不会将密码重新写入文本文件。数据库及 SSH 隧道须可用；不要在不支持隐藏密码输入的 IDE Run 控制台执行。

然后启动 API、Worker 和调度器：

```powershell
.\scripts\start-backend.ps1
```

脚本在后台启动进程，日志在 `D:\E_commerce_Assistant\Back\.local\logs`。默认端口被其他程序占用时会停止启动，不会结束其他程序。若只需要 API 与 Worker，可加 `-WithoutScheduler`。

也可以分别在三个终端手动启动，便于观察日志：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
.\.venv\Scripts\python.exe -m app.workers.main
```

```powershell
.\.venv\Scripts\python.exe -m app.workers.scheduler
```

API 接收请求；Worker 执行文本任务、媒体恢复和导入；调度器定期处理到期竞品监控。只启动 API 时，异步任务会排队等待。

接口文档：<http://127.0.0.1:8000/docs>。存活检查：<http://127.0.0.1:8000/health>，只证明 API 进程能响应，不代表数据库、MinIO 或模型供应商均可用。

启动前端：

```powershell
Set-Location 'D:\E_commerce_Assistant\Front'
npm run dev
```

前端默认通过 Vite 将 `/api` 请求转发到 `http://127.0.0.1:8000`。用真实管理员登录后开始创建唯一店铺。

停止由脚本启动的后端进程：

```powershell
Set-Location 'D:\E_commerce_Assistant\Back'
.\scripts\stop-backend.ps1
```

停止脚本通过进程路径与启动时刻核对身份，仅处理本项目脚本记录的进程，不删除数据库、MinIO 对象或凭据文件。手动启动的终端使用 Ctrl+C 停止。

## 业务操作顺序

1. 管理员登录，建立唯一店铺及运营/查看人员。
2. 建商品、SKU、原图和库存，补齐资料后启用商品。
3. 录入竞品，创建运营轮次，生成并人工选定诊断版本。
4. 生成主图方案、脚本、标题，选定方案；上传真实素材并审核。
5. 建立推广链接，生成投放建议，人工确认建议和实验。
6. 在外部平台人工执行，回填计划标识及实际时间。
7. 手工录入或导入日经营数据，生成复盘，完成本轮，再采纳复盘动作创建下一轮。

管理员具有配置和用户管理权限；运营人员完成日常业务；查看人员只读。权限、资源归属、轮次只读和版本冲突由后端执行。

## 目录与继续开发

| 目录 | 职责 |
|---|---|
| `app/api` | 认证路由及业务接口处理器注册 |
| `app/services` | 业务规则、事务组织和状态检查 |
| `app/models`、`app/db` | 关系表模型与仓储 |
| `app/agents`、`app/llm` | 三个 Agent、提示词、文本模型接入 |
| `app/integrations` | MinIO、公开页面和媒体供应商适配 |
| `app/workers` | 后台任务、租约恢复、导入和调度 |
| `contracts` | 后端使用的固定接口契约副本 |
| `migrations` | 可追溯数据库迁移 |
| `tests` | 单元及显式启用的 PostgreSQL 集成检查 |
| `deploy` | 复用现有 PostgreSQL/MinIO 的可选容器部署 |

详细说明：

- `D:\E_commerce_Assistant\Back\docs\database.md`：关系表、外键、唯一约束和迁移。
- `D:\E_commerce_Assistant\Back\docs\backend-integration.md`：前后端联调、协议与故障定位。
- `D:\E_commerce_Assistant\Back\docs\imports.md`：四类导入的预览和提交语义。
- `D:\E_commerce_Assistant\Back\deploy\README.md`：CentOS 7 容器部署与实际环境待验证项。

## 检查方法与实际边界

```powershell
.\.venv\Scripts\python.exe -m pytest
```

默认跳过真实 PostgreSQL 集成检查。显式启用：

```powershell
$env:RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests/integration
Remove-Item Env:\RUN_POSTGRES_TESTS
```

集成检查使用外层回滚事务，适合空业务测试库；部分测试会创建唯一店铺，已有业务店铺的库应使用单独测试数据库。文件/模型测试替身用于验证业务语义，不代表真实供应商生成或 MinIO 上传已经通过。

2026-10-24 本地验收：106 项后端单元/真实 PostgreSQL 回滚测试通过，另 1 项真实 MinIO 集成测试通过，合计 107 项；前端 26 项测试、构建及 128 个接口绑定检查通过。浏览器真实登录、工作台、DeepSeek 配置读取和注销已验证。真实模型已验证一次商品诊断，其他文本流程通过结构与业务测试，未逐项重复调用收费接口。

MinIO 集成测试使用真实马克杯照片，覆盖上传、幂等重放、签名读取、分段读取、匿名访问拒绝、素材登记和人工审核；结束后删除本测试创建的对象并回滚业务数据。当前工作空间只有初始化管理员和配置，没有测试店铺或商品。图片位于 `D:\E_commerce_Assistant\sample-assets\product-mug.jpg`，来源说明在同目录。

单独复核依赖及真实文件存储：

```powershell
.\.venv\Scripts\python.exe -m scripts.check_services
$env:RUN_POSTGRES_TESTS = '1'
$env:RUN_MINIO_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_storage_live.py -q
Remove-Item Env:\RUN_MINIO_TESTS
Remove-Item Env:\RUN_POSTGRES_TESTS
```

本地使用期间保持 PostgreSQL 15433 和 MinIO 19000 的 SSH 隧道运行。CentOS 7 宿主 Docker、镜像构建和部署兼容性尚未实机验证。
