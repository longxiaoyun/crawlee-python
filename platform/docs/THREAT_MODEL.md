# Threat model (user code execution)

## Trust boundaries

- **Operators** trust the **control plane** (API + DB) and container host.
- **User-authored task code** is **untrusted**: it can attempt network access, CPU/memory exhaustion, and dependency confusion.

## Mitigations (current / intended)

- Runs execute in **ephemeral workspaces**; filesystem is discarded after the run.
- **Wall-clock timeouts** differ for debug vs production runs.
- **Debug** runs cap `requirements.txt` line count to limit `pip` blast radius.
- **Secrets**: platform credentials must be injected by the host (`PLATFORM_*`, orchestrator secrets), not committed in task source.
- **AI**: assistant output is applied only after explicit user confirmation in the UI; versions may record `meta.source=ai_apply` and correlation ids for audit.

## Known limitations

- `pip install --target` still runs **arbitrary packages** from user `requirements.txt` in production runs; use **dependency allowlists** and registry proxies for stronger guarantees (not enforced in this skeleton).
- No hardened sandbox (seccomp/AppArmor/gVisor) is configured in the reference Dockerfiles; deployers should add them for multi-tenant exposure.
- Log and metrics endpoints share the same API key as mutating routes; split read-only credentials or OIDC for production.
- Browser `EventSource` cannot send custom headers; the UI **polls** logs with `X-API-Key` instead.

## Out of scope (v1 skeleton)

- Per-tenant network egress policies, syscall filtering, and cgroup limits beyond subprocess timeouts.
