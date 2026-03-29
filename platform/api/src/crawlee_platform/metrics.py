"""Prometheus metrics."""

from prometheus_client import Counter, Gauge

runs_queued = Gauge('platform_runs_queued', 'Number of runs waiting in queue')
runs_running = Gauge('platform_runs_running', 'Number of runs currently executing')
runs_succeeded = Counter('platform_runs_succeeded_total', 'Finished runs in succeeded state', ['kind'])
runs_failed = Counter('platform_runs_failed_total', 'Finished runs in failed state', ['kind'])
runs_limit_exceeded = Counter(
    'platform_runs_limit_exceeded_total', 'Runs stopped due to resource limits', ['kind']
)
worker_last_heartbeat_unix = Gauge(
    'platform_worker_last_heartbeat_timestamp_seconds',
    'Unix time of last worker heartbeat',
)
