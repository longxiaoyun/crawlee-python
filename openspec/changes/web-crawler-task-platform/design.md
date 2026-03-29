## Context

This repository ships the **Crawlee for Python** library (`src/crawlee/`): crawlers, storage clients, HTTP clients, sessions, and events. The desired product is a **hosted console** comparable in workflow to **Apify**: users author **Python** crawl logic (calling Crawlee) in the browser, run **debug** sessions, **deploy** repeatable production jobs, view **logs and history**, optionally use **AI** to draft tasks, and operate workers as **Docker** images with **visible monitoring**.

Constraints implied by the proposal:

- Production execution MUST remain **Crawlee-based** (no replacing the engine with ad-hoc requests-only runners unless explicitly scoped later).
- User code is **untrusted** relative to the platform: isolation, resource limits, and secret handling are first-class.
- The console is **greenfield** relative to the core library: avoid entangling UI concerns into `src/crawlee/` beyond optional thin hooks (e.g., structured logging or metric labels) if truly needed.

## Goals / Non-Goals

**Goals:**

- Deliver a **multi-page console** for task lifecycle: create/edit metadata, open the code editor, trigger debug or production runs, inspect run output.
- Provide **log streaming** and **run records** (timestamps, status, errors, correlation IDs) tied to a task version.
- Support **AI-assisted authoring** with **human-in-the-loop** apply to the editor (no silent overwrites without user action).
- Publish a **Docker image** for the worker that loads a frozen task bundle and executes it with Crawlee.
- Surface **operational monitoring** in the UI: at minimum run success/failure rates, queue depth or concurrency, and worker health; extend to resource signals as instrumentation matures.

**Non-Goals:**

- **Full feature parity** with Apify Marketplace, actors pricing, or Apify proxy product lines in v1.
- **Multi-tenant billing**, advanced org RBAC, or compliance certifications (may be layered later).
- **Replacing** Crawlee with another crawl framework.
- **Serverless-only** execution model as the only deployment path (Docker-first; other schedulers can wrap the same image).

## Decisions

1. **Monorepo layout vs. separate repo**  
   - **Decision**: Add a `platform/` (or `apps/`) tree in this repo for API, web, and worker packaging; keep `src/crawlee/` as the installable library.  
   - **Rationale**: Second-party fork can track upstream Crawlee while iterating on the console; CI can still publish the library wheel independently of platform images.  
   - **Alternatives**: Separate repo (harder to keep Crawlee pin in sync); embedding UI inside the library package (pollutes PyPI artifact).

2. **API + web technology**  
   - **Decision**: **Backend for Frontend (BFF) REST/JSON API** (e.g., FastAPI) + **SPA** (e.g., React or SvelteKit). WebSocket or SSE for logs.  
   - **Rationale**: Familiar split; streaming fits run logs; Crawlee remains Python on the worker.  
   - **Alternatives**: Django full-stack (heavier for rich IDE UX); Next.js alone (still needs Python worker).

3. **Execution topology**  
   - **Decision**: **Control plane** (API + DB + object store for code bundles) + **data plane** (**worker** processes consuming run jobs). For debug runs, either **dedicated low-priority worker pool** or **short-lived containers** with strict CPU/time/network quotas.  
   - **Rationale**: Mirrors Apify-style separation; scales worker horizontally.  
   - **Alternatives**: Run user code in API process (unsafe); one global process (no isolation).

4. **User code packaging**  
   - **Decision**: Store **immutable task versions** (source snapshot + `pyproject`/`requirements` fragment or locked deps policy). Worker image pins **Crawlee version**; user layer installs **only declared third-party deps** from an allowlist or pre-approved set in v1.  
   - **Rationale**: Reproducibility and supply-chain control.  
   - **Alternatives**: Arbitrary `pip install` at runtime (slow, risky); single shared env (version hell).

5. **AI integration**  
   - **Decision**: **Provider-pluggable** service behind the API; store **prompt, model ID, and assistant message history** per task/session; all **code writes** go through explicit user **Apply** to editor.  
   - **Rationale**: Auditability and safety.  
   - **Alternatives**: Direct file writes from model (unsafe); no persistence of chats (poor UX).

6. **Observability**  
   - **Decision**: **Structured logs** (JSON) from worker with `run_id`, `task_id`, `version`; metrics via **OpenTelemetry** or **Prometheus** endpoints on API/worker; console reads aggregated series from the observability backend or a thin query layer.  
   - **Rationale**: Operators need dashboards; Crawlee events can be bridged into OTEL spans in a later iteration.  
   - **Alternatives**: Plain stderr only (weak UI); vendor lock-in without abstraction.

## Risks / Trade-offs

- **[Risk] Arbitrary Python execution** → **Mitigation**: containers, seccomp/AppArmor where available, read-only root, egress allowlists for debug, no host mounts, secrets via env injection from control plane only.  
- **[Risk] Playwright-heavy tasks blow image size** → **Mitigation**: separate **slim** and **playwright** worker image tags; task metadata selects base image family.  
- **[Risk] Log volume and cost** → **Mitigation**: retention policies, log sampling for debug, link to object storage for large artifacts.  
- **[Risk] AI-generated unsafe or illegal crawling** → **Mitigation**: policy text, rate limits, optional blocklists, human review, terms of use; no bypass of auth in generated code templates.  
- **[Trade-off] Strict dep allowlist** vs developer freedom → start **narrow**, expand based on need.

## Migration Plan

1. Land **platform skeleton** (API, empty UI, docker-compose for Postgres + API + one worker).  
2. Implement **task CRUD + versioning** and **run queue** with **stdout/stderr streaming** to UI.  
3. Add **debug** vs **prod** run policies and **Docker** release pipeline for worker.  
4. Layer **AI** and **dashboards**; tune quotas and retention.  
5. **Rollback**: disable AI feature flag; revert worker image tag; runs remain auditable via DB.

## Open Questions

- **Identity**: Single-user vs multi-tenant auth (OIDC, API keys) for v1?  
- **Scheduler**: Kubernetes Job per run vs dedicated worker long-polling queue?  
- **Storage for crawl outputs**: Piggyback on Crawlee storages inside container only vs centralized dataset API?  
- **Dependency policy**: Exact allowlist mechanism and approval workflow.  
- **Playwright**: Licensing and headless browser security model in shared clusters.
