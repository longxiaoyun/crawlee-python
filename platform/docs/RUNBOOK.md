# Platform runbook

## Environment variables

| Variable | Purpose |
|----------|---------|
| `PLATFORM_DATABASE_URL` | SQLAlchemy async URL (`sqlite+aiosqlite:///...` or `postgresql+asyncpg://...`) |
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

## Task bundle layout (worker)

- `main.py` — user entrypoint executed as `python main.py`
- `requirements.txt` — optional; `pip install --target deps` into workspace; `PYTHONPATH` includes `deps/`

## Exit codes

- Worker subprocess: non-zero indicates failed run; platform stores `failed` with message.
- Limit exceeded: status `limit_exceeded` (timeout).

## Metrics

- `GET /metrics` — Prometheus text (requires `X-API-Key`).

## Frontend

- `VITE_PLATFORM_API_KEY` — must match `PLATFORM_API_KEY` for browser `fetch` calls.
