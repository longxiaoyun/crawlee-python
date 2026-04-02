export interface CrawleeTask {
  id: string
  name: string
  description: string
  production_version_id: string | null
  /** 控制台扩展配置（Webhook、可见性说明等） */
  settings: Record<string, unknown>
  created_at: string
  updated_at: string
}

/** GET /api/tasks row (includes aggregates for list UI). */
export interface CrawleeTaskListRow extends CrawleeTask {
  total_builds: number
  total_runs: number
  default_build_display: string
  last_run_at: string | null
  last_run_status: string | null
  last_run_duration_sec: number | null
}

export interface CrawleeTaskVersion {
  id: string
  task_id: string
  version_number: number
  source_code: string
  requirements_txt: string
  meta: Record<string, unknown>
  created_at: string
  created_by: string
}

export interface CrawleeRun {
  id: string
  task_id: string
  version_id: string
  kind: string
  status: string
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface CrawleeOverview {
  worker_heartbeat_at: string | null
  worker_stale: boolean
  recent_success_ratio: number
  queued_runs: number
  running_runs: number
}

export interface CrawleeLogLine {
  line_no: number
  content: string
}

/** Persisted default Crawlee dataset rows for a run (see GET /api/runs/{id}/dataset-items). */
export interface CrawleeRunDatasetItem {
  seq: number
  item: Record<string, unknown>
}

export interface CrawleeDeployOut {
  task_id: string
  version_id: string
  environment: "production" | "staging"
  runtime: string
  entrypoint: string
  deployed_at: string
  status: string
  image_ref?: string | null
  remote_host?: string | null
  remote_ok?: boolean | null
  detail?: string | null
}

/** GET /api/deploy-info — registry / SSH 目标等非敏感配置 */
export interface CrawleeDeployInfo {
  docker_deploy_enabled: boolean
  acr_registry: string
  acr_namespace: string
  acr_repository: string
  image_repository: string
  deploy_ssh_host: string
  deploy_ssh_user: string
  deploy_ssh_port: number
  deploy_container_name: string
  deploy_skip_ssh: boolean
}
