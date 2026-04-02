import type * as Auth from "./type"
import { request } from "@/http/axios"

/** 获取登录验证码 */
export function getCaptchaApi() {
  if (import.meta.env.VITE_SKIP_MOCK_LOGIN === "true") {
    return Promise.resolve<Auth.CaptchaResponseData>({
      code: 0,
      data: "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
      message: "ok"
    })
  }
  return request<Auth.CaptchaResponseData>({
    url: "auth/captcha",
    method: "get"
  })
}

/** 登录并返回 Token */
export function loginApi(data: Auth.LoginRequestData) {
  if (import.meta.env.VITE_SKIP_MOCK_LOGIN === "true") {
    return Promise.resolve<Auth.LoginResponseData>({
      code: 0,
      data: { token: `crawlee-dev-${data.username}` },
      message: "ok"
    })
  }
  return request<Auth.LoginResponseData>({
    url: "auth/login",
    method: "post",
    data
  })
}
