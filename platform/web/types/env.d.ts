/** 声明 vite 环境变量的类型（如果未声明则默认是 any） */
interface ImportMetaEnv {
  readonly VITE_APP_TITLE: string
  readonly VITE_BASE_URL: string
  readonly VITE_ROUTER_HISTORY: "hash" | "html5"
  readonly VITE_PUBLIC_PATH: string
  /** 跳过 Apifox mock，登录/用户信息走本地假数据（与 Crawlee 后端并行开发） */
  readonly VITE_SKIP_MOCK_LOGIN?: string
  /** 浏览器访问 Crawlee Platform API 的 Key（须与 PLATFORM_API_KEY 一致） */
  readonly VITE_PLATFORM_API_KEY?: string
  /** Vite 代理 Crawlee 后端地址 */
  readonly VITE_CRAWLEE_API_TARGET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
