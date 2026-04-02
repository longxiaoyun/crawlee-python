import type * as T from "./type"
import { crawleeRequest } from "@/http/crawlee-axios"

export function fetchTasksApi() {
  return crawleeRequest<T.CrawleeTaskListRow[]>({ url: "/api/tasks", method: "get" })
}

export function createTaskApi(data: { name: string, description?: string }) {
  return crawleeRequest<T.CrawleeTask>({ url: "/api/tasks", method: "post", data })
}

export function fetchTaskApi(taskId: string) {
  return crawleeRequest<T.CrawleeTask>({ url: `/api/tasks/${taskId}`, method: "get" })
}

export function patchTaskApi(taskId: string, data: {
  name?: string
  description?: string
  settings?: Record<string, unknown>
}) {
  return crawleeRequest<T.CrawleeTask>({
    url: `/api/tasks/${taskId}`,
    method: "patch",
    data
  })
}

export function fetchVersionsApi(taskId: string) {
  return crawleeRequest<T.CrawleeTaskVersion[]>({ url: `/api/tasks/${taskId}/versions`, method: "get" })
}

export function createVersionApi(taskId: string, data: {
  source_code: string
  requirements_txt?: string
  meta?: Record<string, unknown>
  created_by?: string
}) {
  return crawleeRequest<T.CrawleeTaskVersion>({
    url: `/api/tasks/${taskId}/versions`,
    method: "post",
    data
  })
}

export function promoteVersionApi(taskId: string, versionId: string) {
  return crawleeRequest<T.CrawleeTask>({
    url: `/api/tasks/${taskId}/promote`,
    method: "post",
    data: { version_id: versionId }
  })
}

export function enqueueRunApi(taskId: string, data: { version_id: string, kind: "debug" | "production" }) {
  return crawleeRequest<T.CrawleeRun>({
    url: `/api/tasks/${taskId}/runs`,
    method: "post",
    data
  })
}

export function fetchRunsApi(taskId: string) {
  return crawleeRequest<T.CrawleeRun[]>({ url: `/api/tasks/${taskId}/runs`, method: "get" })
}

export function fetchRunApi(runId: string) {
  return crawleeRequest<T.CrawleeRun>({ url: `/api/runs/${runId}`, method: "get" })
}

export function fetchRunLogsApi(runId: string) {
  return crawleeRequest<T.CrawleeLogLine[]>({ url: `/api/runs/${runId}/logs`, method: "get" })
}

export function fetchRunDatasetItemsApi(runId: string) {
  return crawleeRequest<T.CrawleeRunDatasetItem[]>({ url: `/api/runs/${runId}/dataset-items`, method: "get" })
}

export function fetchOverviewApi() {
  return crawleeRequest<T.CrawleeOverview>({ url: "/api/overview", method: "get" })
}

export function chatApi(taskId: string, message: string) {
  return crawleeRequest<{ reply: string, correlation_id: string, model_id: string | null }>({
    url: `/api/tasks/${taskId}/chat`,
    method: "post",
    data: { message }
  })
}

export function fetchChatHistoryApi(taskId: string) {
  return crawleeRequest<{ role: string, content: string }[]>({
    url: `/api/tasks/${taskId}/chat`,
    method: "get"
  })
}

export function deployTaskApi(taskId: string, data?: { version_id?: string, environment?: "production" | "staging" }) {
  return crawleeRequest<T.CrawleeDeployOut>({
    url: `/api/tasks/${taskId}/deploy`,
    method: "post",
    data: data ?? {}
  })
}

/** 部署页展示用；失败时由页面内提示处理，避免全局 Toast 刷「Not Found」 */
export function fetchDeployInfoApi() {
  return crawleeRequest<T.CrawleeDeployInfo>({
    url: "/api/deploy-info",
    method: "get",
    skipGlobalErrorMessage: true
  })
}

export function createWizardSessionApi() {
  return crawleeRequest<{ session_id: string }>({ url: "/api/ai/task-wizard/sessions", method: "post" })
}

export function fetchWizardSessionsApi(limit = 50) {
  return crawleeRequest<
    {
      session_id: string
      status: string
      created_at: string
      updated_at: string
      preview: string
      message_count: number
    }[]
  >({
    url: "/api/ai/task-wizard/sessions",
    method: "get",
    params: { limit }
  })
}

export function fetchWizardSessionMetaApi(sessionId: string) {
  return crawleeRequest<{
    session_id: string
    status: string
    created_at: string
    updated_at: string
  }>({
    url: `/api/ai/task-wizard/sessions/${sessionId}`,
    method: "get"
  })
}

export function fetchWizardMessagesApi(sessionId: string) {
  return crawleeRequest<{ role: string, content: string }[]>({
    url: `/api/ai/task-wizard/sessions/${sessionId}/messages`,
    method: "get"
  })
}

export function postWizardMessageApi(sessionId: string, message: string) {
  return crawleeRequest<{ reply: string, draft: Record<string, unknown> | null }>({
    url: `/api/ai/task-wizard/sessions/${sessionId}/messages`,
    method: "post",
    data: { message }
  })
}

export function finalizeWizardApi(
  sessionId: string,
  data: {
    name: string
    description: string
    source_code: string
    requirements_txt: string
    settings: Record<string, unknown>
  }
) {
  return crawleeRequest<{ task_id: string, version_id: string }>({
    url: `/api/ai/task-wizard/sessions/${sessionId}/finalize`,
    method: "post",
    data
  })
}
