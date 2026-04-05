# 生产环境：控制面 MySQL 清单

本文档说明 **Crawlee Platform 控制面**（任务、运行、日志、`run_dataset_items` 等）在生产环境使用 MySQL 时的配置与核对项。

> **与业务库区分**：爬虫任务写入的「业务 MySQL」（表名、采集落库）由任务代码与环境变量如 `WIZARD_MYSQL_*` 等约定，见 [`platform/docs/WIZARD_MYSQL.md`](../../platform/docs/WIZARD_MYSQL.md)。控制面与业务库可以是同一 MySQL 实例上的不同 database，也可以完全分离。

## 安全原则

- 密码、连接串中的凭据 **仅通过环境变量、密钥管理或编排 Secret 注入**，不要写入仓库、镜像层或 `platform.deploy.json` 明文字段。
- 轮换密码后同步更新运行 API / Worker 的环境。

## 环境变量（控制面）

前缀均为 `PLATFORM_`（见 `platform/api/src/crawlee_platform/config.py`）。

| 变量 | 说明 |
|------|------|
| `PLATFORM_MYSQL_HOST` | MySQL 主机（与下面 `mysql_*` 一起设置时，优先尝试连接 MySQL） |
| `PLATFORM_MYSQL_PORT` | 端口，默认 `3306` |
| `PLATFORM_MYSQL_USER` | 用户名 |
| `PLATFORM_MYSQL_PASSWORD` | 密码（必用 Secret，勿提交） |
| `PLATFORM_MYSQL_DATABASE` | 数据库名 |
| `PLATFORM_MYSQL_CHARSET` | 可选，默认 `utf8mb4` |

**二选一配置方式：**

1. **分项变量**：设置上表中的 `HOST` + `USER` + `DATABASE`（及 `PASSWORD`、`PORT` 等），运行时由后端拼出 `mysql+aiomysql://...`。
2. **完整 URL**：设置 `PLATFORM_DATABASE_URL` 为异步驱动形式，例如  
   `mysql+aiomysql://user:password@host:3306/dbname?charset=utf8mb4`  
   （凭据仍只放在 Secret / 环境中。）

## 连接失败时的行为

| 变量 | 说明 |
|------|------|
| `PLATFORM_SQLITE_FALLBACK_URL` | MySQL 不可用时使用的 SQLite 路径，默认 `sqlite+aiosqlite:///./platform.db` |

生产环境若希望 **严禁** 静默落回 SQLite，应保证 MySQL 高可用、网络与白名单正确，并监控 `/health` 中的 `database` 字段（见下）。

## 部署后核对

- [ ] API 与 Worker 使用 **同一套** `PLATFORM_*` 数据库配置（否则任务状态与数据集预览会不一致）。
- [ ] 调用 `GET /health`，响应中含当前使用的数据库后端标识（`mysql` 或 `sqlite`），生产应长期为 `mysql`。
- [ ] MySQL 用户具备目标库上的 DDL/DML 权限；首次启动会 `create_all` 建表。
- [ ] 防火墙 / 安全组允许 **API 与 Worker 所在主机** 访问 MySQL 端口。
- [ ] 字符集与排序规则与 `utf8mb4` 兼容（默认连接参数已带 `charset`）。

## 从现有 SQLite 迁到 MySQL

一次性迁移脚本：`platform/api/scripts/migrate_sqlite_to_mysql.py`（脚本内注释含用法）。

**注意：** 脚本会对目标 MySQL 执行 `drop_all` / `create_all` 再拷贝数据，执行前请 **备份 SQLite 与 MySQL**，并仅在维护窗口操作。

## 相关代码路径

- 连接解析与回退：`platform/api/src/crawlee_platform/db.py`（`init_database`）
- 应用启动建表：`platform/api/src/crawlee_platform/api_app.py`（lifespan）
- Worker：`platform/api/src/crawlee_platform/worker/main.py`
