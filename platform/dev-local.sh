#!/usr/bin/env bash
# 本地一键启动：API + Worker + Web（Ctrl+C 会结束全部子进程）
# 前端基于 v3-admin-vite（Vue3），默认开发端口 3333
set -euo pipefail

PLATFORM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$PLATFORM_ROOT/api"
WEB_DIR="$PLATFORM_ROOT/web"

export PLATFORM_API_KEY="${PLATFORM_API_KEY:-dev-api-key}"
export PLATFORM_DATABASE_URL="${PLATFORM_DATABASE_URL:-sqlite+aiosqlite:///./platform.db}"

API_PID=""
WORKER_PID=""

cleanup() {
  if [[ -n "$WORKER_PID" ]] && kill -0 "$WORKER_PID" 2>/dev/null; then
    kill "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
  fi
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ "${1:-}" == "--install" ]]; then
  (cd "$API_DIR" && uv sync --extra dev)
  if command -v pnpm >/dev/null 2>&1; then
    (cd "$WEB_DIR" && pnpm install)
  else
    echo "请先安装 pnpm: npm i -g pnpm  （v3-admin-vite 推荐 pnpm 10+）"
    exit 1
  fi
fi

if [[ ! -d "$API_DIR/.venv" ]]; then
  echo "未找到 platform/api/.venv，请先执行: $0 --install"
  exit 1
fi

if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  echo "未找到 platform/web/node_modules，请先执行: $0 --install"
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "未找到 pnpm，请安装: npm i -g pnpm"
  exit 1
fi

echo "API + Worker 数据库: ${API_DIR}/platform.db"
# 说明里不要写 $VITE_...，否则在 set -u 下会被当作未定义变量展开
echo "API Key: ${PLATFORM_API_KEY} — 请与 platform/web/.env.development 里的 VITE_PLATFORM_API_KEY 保持一致"
echo "启动 API (8000) …"
(
  cd "$API_DIR"
  uv run uvicorn crawlee_platform.api_app:app --host 0.0.0.0 --port 8000
) &
API_PID=$!

echo "启动 Worker …"
(
  cd "$API_DIR"
  uv run crawlee-platform-worker
) &
WORKER_PID=$!

sleep 1
echo "启动 Web（v3-admin-vite，默认 http://localhost:3333 ）…"
cd "$WEB_DIR"
pnpm dev
