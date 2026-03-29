## 1. Repository and platform skeleton

- [x] 1.1 Add `platform/` (or `apps/`) tree with separate packages or folders for `api`, `web`, and `worker` without modifying `src/crawlee/` behavior
- [x] 1.2 Document local development via `docker-compose` (or equivalent) for database, API, web dev server, and one worker replica
- [x] 1.3 Add root-level README section linking platform docs and Crawlee library docs

## 2. Control plane data model and API

- [x] 2.1 Define persistence schema for tasks, immutable task versions, production pointer, runs, and run log object references
- [x] 2.2 Implement authenticated REST API for task CRUD, version save, version listing, and production promote
- [x] 2.3 Implement REST endpoints to enqueue debug and production runs bound to a specific task version
- [x] 2.4 Implement run status polling endpoints and WebSocket or SSE endpoint for live logs keyed by `run_id`
- [x] 2.5 Add authorization hooks (minimal viable: API key or single-user token) enforced on all mutating routes

## 3. Worker runtime and job execution

- [x] 3.1 Implement job consumer that loads task bundle (source tarball or git-like snapshot) into an ephemeral workspace
- [x] 3.2 Implement worker entrypoint that installs declared dependencies per policy and invokes documented task entry module using Crawlee
- [x] 3.3 Emit structured JSON log lines prefixed or fields for `run_id`, `task_id`, `version`, and severity on stdout
- [x] 3.4 Enforce debug versus production resource limits (wall time, concurrency, memory) with clear terminal status reporting
- [x] 3.5 Upload or stream persisted log segments to object storage or DB for completed runs

## 4. Console UI (Apify-like workflow)

- [x] 4.1 Scaffold SPA with routing for task list, task detail, editor plus runs panel, and monitoring overview
- [x] 4.2 Integrate code editor component with syntax highlighting for Python and save-to-new-version action
- [x] 4.3 Implement version history browser with read-only preview of prior versions
- [x] 4.4 Wire debug run and production run buttons to API including optimistic UI and error surfacing
- [x] 4.5 Implement log panel with streaming updates for active runs and fetch for completed runs

## 5. AI-assisted authoring

- [x] 5.1 Add backend module for chat completion with pluggable provider and configuration via environment secrets
- [x] 5.2 Persist per-task conversation turns with model identifier and correlation identifiers
- [x] 5.3 Implement UI chat panel and **Apply** flow that patches editor content only after explicit confirmation
- [x] 5.4 Record audit metadata when a version is created from an applied assistant proposal

## 6. Docker images and deployment contract

- [x] 6.1 Author `Dockerfile`(s) for default worker and optional Playwright-enriched worker tag with pinned Crawlee install
- [x] 6.2 Document required environment variables, task bundle layout, entry module name, and exit code semantics
- [x] 6.3 Add CI job to build and optionally push images with semver or git SHA tags
- [x] 6.4 Provide example Kubernetes Job or nominal orchestration manifest for production runs

## 7. Observability and monitoring UI

- [x] 7.1 Expose Prometheus-compatible metrics or OTLP from API and worker for runs queued, running, succeeded, failed, and backlog depth
- [x] 7.2 Implement console overview widgets for worker heartbeat or stale indicator and recent success ratio
- [x] 7.3 Define log and metrics retention defaults and operator configuration

## 8. Verification

- [x] 8.1 Add integration tests for API run lifecycle with a fake fast worker or test double
- [x] 8.2 Add smoke test that runs sample Crawlee task inside worker image in CI (optional network gated job)
- [x] 8.3 Document threat model summary for user code execution and known limitations
