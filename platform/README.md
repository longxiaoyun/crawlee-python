# Crawlee web platform (optional)

Apify-like console for authoring **Crawlee for Python** tasks in the browser: edit `main.py`, debug and production runs, logs, basic monitoring, and optional AI-assisted drafting. Execution remains **Crawlee**-backed; workers package as Docker images.

## Layout

| Path | Role |
|------|------|
| `api/` | FastAPI control plane + worker package (`crawlee-platform` on PyPI layout) |
| `web/` | [v3-admin-vite](https://github.com/un-pany/v3-admin-vite)（Vue3 + Element Plus）控制台 |
| `docker/` | Container build definitions (build context = **repository root**) |
| `docs/` | Runbook, env vars, threat model |

## Quick start (Docker Compose)

From repository root:

```bash
docker compose -f platform/docker-compose.yml up --build
```

- API: `http://localhost:8000`
- Web: `http://localhost:3333`（模板默认端口）
- Set `PLATFORM_API_KEY` / `VITE_PLATFORM_API_KEY` in compose to match.

Worker and API share a SQLite file on a Docker volume by default. For Postgres, set `PLATFORM_DATABASE_URL` to async URL.

## Local (without Docker)

### 一键启动（推荐）

在仓库里执行（首次可加 `--install` 安装依赖）：

```bash
chmod +x platform/dev-local.sh   # 只需一次
./platform/dev-local.sh --install   # 首次：装 uv + 前端 pnpm 依赖（需全局 `pnpm`）
./platform/dev-local.sh             # 之后直接启动
```

默认：`dev-api-key`；浏览器侧见 `platform/web/.env.development` 中 `VITE_PLATFORM_API_KEY`。数据库为 `platform/api/platform.db`。改密钥可：

```bash
export PLATFORM_API_KEY='your-secret'
./platform/dev-local.sh
```

按 **Ctrl+C** 会同时退出 Web、API 和 Worker。

### 手动三个终端（等价）

Terminal 1 — API：

```bash
cd platform/api
uv sync --extra dev
export PLATFORM_API_KEY=dev-api-key
export PLATFORM_DATABASE_URL=sqlite+aiosqlite:///./platform.db
uv run uvicorn crawlee_platform.api_app:app --host 0.0.0.0 --port 8000
```

Terminal 2 — worker：

```bash
cd platform/api
export PLATFORM_DATABASE_URL=sqlite+aiosqlite:///./platform.db
uv run crawlee-platform-worker
```

Terminal 3 — web（[v3-admin-vite](https://github.com/un-pany/v3-admin-vite)，默认 **3333**）：

```bash
cd platform/web
pnpm install
pnpm dev
# 登录页任意填验证码后点登录（VITE_SKIP_MOCK_LOGIN 已启用本地假 Token）
```

## Tests (platform)

```bash
cd platform/api
uv run pytest tests/ --config-file=pyproject.toml
```

## Library docs

Crawlee Python library documentation: [crawlee.dev/python/](https://crawlee.dev/python/)
