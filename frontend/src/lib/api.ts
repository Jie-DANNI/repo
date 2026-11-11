import axios from 'axios'

/** 统一 API 客户端：自动附带 token，401 时清理登录态并回登录页 */
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

const TOKEN_KEY = 'memoloop_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      setToken(null)
      localStorage.removeItem('memoloop_user')
      if (!location.pathname.startsWith('/login')) {
        location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

/** 从后端错误结构里提取可展示的中文提示 */
export function errorMessage(err: unknown): string {
  const anyErr = err as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = anyErr?.response?.data?.detail
  if (typeof detail === 'string') return detail
  // pydantic 校验错误是数组
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace('Value error, ', '')
  return anyErr?.message ?? '请求失败，请稍后重试'
}

export default api
