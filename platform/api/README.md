# Crawlee platform API and worker

Python control plane and worker process for the optional web console. See `../README.md` for how to run the stack locally.

Install and run API:

```bash
cd platform/api
uv sync --extra dev
export PLATFORM_API_KEY=dev
export PLATFORM_DATABASE_URL=sqlite+aiosqlite:///./platform.db
uv run crawlee-platform-api
```

Worker (separate terminal):

```bash
uv run crawlee-platform-worker
```
