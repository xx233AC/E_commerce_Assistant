# 保留 CentOS 7 的应用部署方案

这份 Compose **只新增 API、Worker、scheduler 和 Nginx**，复用已经存在的 PostgreSQL、MinIO。不会修改项目根目录原有 `docker-compose.yml`，不会创建第二套数据库或删除已有数据卷。

CentOS 7 必须保留。本次没有在你的 CentOS 7 主机上执行镜像构建或部署，也没有验证该主机 Docker、Compose、内核和运行时的兼容性。Docker 当前官方 CentOS 安装文档列出受维护的 CentOS Stream，不能据此保证 CentOS 7 可安装或运行当前最新 Docker；请先核对现有运行环境，不执行自动升级脚本。[Docker 官方说明](https://docs.docker.com/engine/install/centos/)

## 部署目录

服务器上保留同样的相对布局，例如：

```text
/opt/E_commerce_Assistant/
├── Front/
│   └── dist/                    已构建的前端静态文件
└── Back/
    ├── app/
    ├── contracts/
    ├── migrations/
    ├── scripts/
    ├── pyproject.toml
    ├── alembic.ini
    ├── Dockerfile
    └── deploy/
        ├── docker-compose.yml
        ├── .env.production      手动按实际服务填写
        └── nginx/default.conf
```

前端可在 Windows 开发机构建，不要求在 CentOS 7 宿主安装 Node：

```powershell
Set-Location 'D:\E_commerce_Assistant\Front'
npm run build
```

将生成的 `Front/dist` 和后端源码放到上述位置。不要把 Windows 的 `.venv`、`.env`、`.local` 或 `node_modules` 作为部署依赖上传。后端 Dockerfile 使用 Linux Python 3.12 镜像并安装 ffmpeg/ffprobe，用于真实视频文件元数据检查。

## 先核实实际网络

在 CentOS 7 上查看已有工具版本：

```bash
docker --version
docker compose version
uname -r
uname -m
```

本方案采用 `docker compose` 命令。若主机只有旧版 `docker-compose`，需先确认配置支持情况及适配版本，再选择命令；本次不更换宿主运行时。

填写配置前明确两组地址：

1. **应用容器可以访问的 PostgreSQL/MinIO 地址。** 可使用已有服务所在服务器的可达内网地址和对外映射端口，或者把应用服务明确接入同一个现有 Docker 网络后使用服务名。不要默认数据库容器与本 Compose 同网。
2. **用户浏览器可以访问的应用和 MinIO 地址。** 签名链接直接指向 MINIO_PUBLIC_ENDPOINT，不能使用只有容器才认识的服务名。

容器中的 `127.0.0.1` 指该容器自身。Windows 的 `127.0.0.1:15433`、`127.0.0.1:19000` 是开发机 SSH 隧道，不是服务器容器的数据库/存储地址。没有确认真实映射端口前，不应假定 5432、9000 或任何已有端口可达。

## 准备配置

```bash
cd /opt/E_commerce_Assistant/Back/deploy
cp .env.production.example .env.production
chmod 600 .env.production
```

编辑 `.env.production`，替换所有 `CHANGE_ME`。PG_HOST/PG_PORT 填实际容器可达端点；MINIO_ENDPOINT 填 S3 API 的 `host:port`，不带 URL 协议；MINIO_PUBLIC_ENDPOINT 填浏览器可达的 `host:port`。19001/9001 控制台端口不能代替 S3 API。

应用只使用专用私有桶 `ecom-assistant-private`，如果设置其他桶名，应同样保持私有。当前 MINIO_SECURE 同时控制内部和公开端点的 HTTP/HTTPS，因此两者应使用相同模式。不要把现有共享桶修改成公开桶来解决签名访问问题。

JWT_SECRET 生成后保持稳定，API 与 Worker 使用同一配置。文本模型密钥作为服务器环境变量保存在此配置文件，模型管理页面只引用变量名。

HTTP_BIND_ADDRESS 默认 `127.0.0.1`，适合通过现有网关访问。需要直接通过服务器内网地址访问时，明确改为对应网卡地址或 `0.0.0.0`，并按实际入口调整 PUBLIC_BASE_URL。对外 HTTPS 可由已有网关终止；若添加网关，还要准确配置可信代理和转发协议。

镜像标签提供可调整默认值，正式部署可替换为你已验证过的固定 tag/digest。当前配置没有证明这些镜像能在你的具体 CentOS 7 Docker 版本上运行。

## 构建和启动

先校验配置；`config -q` 只返回是否有效，避免在终端展开真实密码：

```bash
docker compose --env-file .env.production -p ecom-app config -q
docker compose --env-file .env.production -p ecom-app build api
```

确认已对现有数据库做好常规备份，再执行应用迁移。迁移只创建/变更本应用表，不自动重建数据库：

```bash
docker compose --env-file .env.production -p ecom-app run --rm api python -m alembic upgrade head
docker compose --env-file .env.production -p ecom-app run --rm api python -m scripts.bootstrap
docker compose --env-file .env.production -p ecom-app up -d api worker scheduler nginx
```

bootstrap 首次创建管理员时，将凭据写入容器 `/app/.local/initial-admin.txt`，由应用专用 runtime_files 卷保存。可复制到当前受控目录自行查看；不在日志中自动输出密码：

```bash
docker compose --env-file .env.production -p ecom-app cp api:/app/.local/initial-admin.txt ./initial-admin.txt
chmod 600 ./initial-admin.txt
```

已有用户时不会重新生成初始凭据，因此该文件可能不存在，使用现有账号即可。登录后修改初始密码。

查看服务状态和日志：

```bash
docker compose --env-file .env.production -p ecom-app ps
docker compose --env-file .env.production -p ecom-app logs --tail=100 api worker scheduler
```

Nginx 静态文件与配置挂载使用只读和 SELinux 共享标签 `:ro,z`。仅挂载上述项目文件；不要把主机系统目录作为静态文件目录。API 只在 Compose 内部开放 8000，不发布到宿主；Nginx 覆盖客户端提供的转发 IP，API 只信任此隔离入口。

## Nginx 的作用

- 提供 React 构建后的静态文件，刷新 `/products/...` 等页面仍返回 index.html。
- 将 `/api/...` 原样转发到 `api:8000`，不截掉 `/api/v1`。
- 总请求体上限 512 MiB，为接口允许的 500 MiB 视频文件预留 multipart 开销；具体文件类型、用途和大小仍由后端校验。
- 上传采用不缓存请求体的方式转发，连接超时 10 秒，读写超时 300 秒。生成任务本身异步执行，不能靠无限延长 HTTP 超时代替 Worker。

`proxy_pass` 不带 URI 后缀以保留原始请求路径，相关行为见 [Nginx 反向代理官方文档](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)。请求体大小指令见 [Nginx client_max_body_size](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size)。

## 停止与更新

```bash
docker compose --env-file .env.production -p ecom-app stop
```

该命令只停止本应用项目。不要在这套应用部署命令中加入 `down -v`，也不要删除现有 PostgreSQL/MinIO 卷。

更新时先备份，替换源码与 Front/dist，重新构建 API 镜像，执行新迁移，再重新创建应用容器。数据库有不可变快照和任务历史，回滚应按迁移和备份流程处理，不能直接删表重新初始化。

## 部署验收

容器健康检查只验证 `/health` 存活。实际验收还包括：真实账号登录、创建店铺与商品、上传小图片到 MinIO、打开签名地址、导入 CSV 预览和确认、Worker 任务状态推进、权限拒绝、旧版本 412、幂等重放不重复写入。

本地 PostgreSQL 迁移和 MinIO 真实上传/读取已通过验证；智谱图片/视频已接入，详见 `../docs/zhipu-media.md`。部署时在 .env.production 配置 ZHIPU_API_KEY，并运行 python -m scripts.configure_zhipu 登记默认媒体模型。CentOS 7 宿主的 Docker/镜像兼容性、Nginx 配置加载、容器网络与 HTTPS 入口仍需现场验收。
