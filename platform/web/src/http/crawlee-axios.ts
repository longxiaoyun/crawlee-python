/**
 * Axios 客户端：直连 Crawlee Platform FastAPI（非模板 mock 的 `{ code, data }` 格式）
 */
import type { AxiosRequestConfig } from "axios"
import axios from "axios"
import { get, merge } from "lodash-es"

const apiKey = import.meta.env.VITE_PLATFORM_API_KEY || "dev-api-key"

/** 为单次请求关闭全局 ElMessage（由调用方自行处理错误） */
export type CrawleeAxiosRequestConfig = AxiosRequestConfig & {
  skipGlobalErrorMessage?: boolean
}

function createInstance() {
  const instance = axios.create()
  instance.interceptors.response.use(
    (response) => {
      return response.data
    },
    (error) => {
      const cfg = error.config as CrawleeAxiosRequestConfig | undefined
      if (!cfg?.skipGlobalErrorMessage) {
        const status = get(error, "response.status")
        const detail = get(error, "response.data.detail")
        const msg = typeof detail === "string" ? detail : get(error, "response.data.message") || error.message
        ElMessage.error(msg || `请求失败 (${status ?? "?"})`)
      }
      return Promise.reject(error)
    }
  )
  return instance
}

const instance = createInstance()

export function crawleeRequest<T>(config: CrawleeAxiosRequestConfig): Promise<T> {
  const defaults: CrawleeAxiosRequestConfig = {
    baseURL: "",
    headers: {
      "X-API-Key": apiKey,
      "Content-Type": "application/json"
    },
    timeout: 120_000
  }
  return instance(merge(defaults, config)) as Promise<T>
}
