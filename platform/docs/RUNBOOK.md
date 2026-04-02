# Platform runbook

## Environment variables

| Variable | Purpose |
|----------|---------|
| `PLATFORM_DATABASE_URL` | SQLAlchemy async URL (`sqlite+aiosqlite:///...`, `postgresql+asyncpg://...`, or `mysql+aiomysql://user:pass@host/db` 等) |
| `PLATFORM_API_KEY` | Shared secret; send as `X-API-Key` from UI and tools |
| `PLATFORM_DEBUG_RUN_TIMEOUT_SEC` | Wall time for **debug** runs (default `300`) |
| `PLATFORM_PROD_RUN_TIMEOUT_SEC` | Wall time for **production** runs (default `86400`) |
| `PLATFORM_DEBUG_MAX_PIP_PACKAGES` | Max non-comment lines in `requirements.txt` for debug runs |
| `PLATFORM_OPENAI_API_KEY` | Optional; enables live AI chat (otherwise echo stub) |
| `PLATFORM_OPENAI_BASE_URL` | OpenAI-compatible API base URL |
| `PLATFORM_OPENAI_MODEL` | Model id for chat |
| `PLATFORM_CORS_ORIGINS` | Comma-separated allowed browser origins |
| `PLATFORM_LOG_RETENTION_DAYS` | Documented default for log retention policy (`30`) |
| `PLATFORM_METRICS_RETENTION_DAYS` | Documented default for metric retention (`90`) |
| `PLATFORM_WORKER_HEARTBEAT_STALE_SEC` | UI marks worker stale after this gap (`120`) |
| `PLATFORM_WORKER_ID` | Optional label stored in heartbeat row |
| `PLATFORM_ENABLE_SMART_TASK_WIZARD` | `true` / `false`：是否启用 `/api/ai/task-wizard/*` 智能创建任务 API（默认 `true`） |

## Task bundle layout (worker)

- `main.py` — user entrypoint executed as `python main.py`
- `requirements.txt` — optional; `pip install --target deps` into workspace; `PYTHONPATH` includes `deps/`

## Crawlee dataset → 控制台存储

- 任务在运行目录下使用 Crawlee 默认 **filesystem** 存储时，结果写入 `storage/datasets/default/*.json`。
- Worker 在删除临时工作区**之前**会把这些 JSON 导入表 `run_dataset_items`（与 `runs` 关联）。
- 前端「最近运行 → 输出 / 存储」通过 `GET /api/runs/{run_id}/dataset-items` 读取；**同一套** `PLATFORM_DATABASE_URL` 若指向 MySQL，则数据集行也落在 MySQL 中（需安装对应异步驱动，如 `aiomysql` 并在 URL 中使用 `mysql+aiomysql://...`）。
- 若任务只 `print` 文本而未 `push_data` / 写入 `Dataset`，则导入条数为 0；控制台仍可从日志行解析部分展示（兼容旧行为）。

## Exit codes

- Worker subprocess: non-zero indicates failed run; platform stores `failed` with message.
- Limit exceeded: status `limit_exceeded` (timeout).

## Metrics

- `GET /metrics` — Prometheus text (requires `X-API-Key`).

## Frontend

- `VITE_PLATFORM_API_KEY` — must match `PLATFORM_API_KEY` for browser `fetch` calls.
