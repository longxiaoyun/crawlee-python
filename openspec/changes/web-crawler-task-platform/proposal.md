## Why

Crawlee for Python is a strong library for building crawlers, but using it still requires a local dev environment and code checkout. A hosted, Apify-style console on top of this repo would let teams **define crawl tasks in the browser**, iterate with **debug runs and visible logs**, and ship **repeatable Docker-based production runs**—including **AI-assisted authoring** and **clear operational visibility**—without replacing Crawlee as the execution engine.

## What Changes

- Add a **web application** (console) to create and manage crawl **tasks** whose implementation is **user-authored Python** using Crawlee APIs (not a separate DSL unless explicitly added later).
- Provide an **in-browser code editor** with **save/versioning**, **debug run** (short, constrained), **promote-to-production deploy**, **live log streaming**, and **run history** (status, duration, links to logs/artifacts).
- Add an **AI assistant** surface (chat in the UI) to **generate, explain, and revise** crawl scripts and task configuration, with human review before save/run.
- Package the **production worker** as a **Docker image** that runs stored task code against Crawlee (same major version as the platform), suitable for Kubernetes or a simple `docker run` stack.
- **Extend or add monitoring** so the console surfaces health, run throughput/errors, and resource signals that operators need (details in design/specs—may integrate with existing events/metrics in Crawlee where applicable).

## Capabilities

### New Capabilities

- `console-ui`: Apify-like pages for tasks, runs, settings, and navigation; auth/tenancy boundaries as decided in design.
- `script-editor-and-execution`: Online editor, validation, debug vs production execution modes, log tailing, run records, artifact references.
- `ai-assisted-tasks`: Chat UX and backend integration for generating/updating task code and metadata with guardrails and audit trail.
- `worker-docker-runtime`: Docker image(s), entrypoints, env/config contract, and how the platform schedules or pulls workers.
- `platform-observability`: Metrics, dashboards, and alerting hooks exposed in the UI (and optionally to external systems).

### Modified Capabilities

<!-- No existing capabilities under openspec/specs/ in this repo at proposal time; library-level behavior changes (if any) will be tracked as implementation notes in design/tasks, not as delta specs unless formal baseline specs are added later. -->

## Impact

- **New services and UI**: separate from the `crawlee` Python package (likely new top-level app(s), API, and worker process).
- **Dependencies**: web stack (frontend + API framework), container build pipeline, optional AI provider SDKs and secrets management.
- **Operations**: runtime isolation for user code (sandboxes, quotas), log storage, image registry, and monitoring backend(s).
- **This repo**: may add directories for `apps/` or `platform/` while keeping `src/crawlee/` as the crawl engine dependency for workers.
