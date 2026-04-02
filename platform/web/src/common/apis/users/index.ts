import type * as Users from "./type"
import { request } from "@/http/axios"

/** 获取当前登录用户详情 */
export function getCurrentUserApi() {
  if (import.meta.env.VITE_SKIP_MOCK_LOGIN === "true") {
    return Promise.resolve<Users.CurrentUserResponseData>({
      code: 0,
      data: { username: "Goose Operator", roles: ["admin"] },
      message: "ok"
    })
  }
  return request<Users.CurrentUserResponseData>({
    url: "users/me",
    method: "get"
  })
}
