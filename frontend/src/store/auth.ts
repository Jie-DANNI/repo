import { create } from 'zustand'
import api, { getToken, setToken } from '../lib/api'

export interface User {
  id: number
  email: string
  nickname: string
  role: string
  created_at: string
}

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, nickname: string, password: string) => Promise<void>
  logout: () => void
  restore: () => Promise<void>
}

const USER_KEY = 'memoloop_user'

export const useAuth = create<AuthState>((set) => ({
  user: JSON.parse(localStorage.getItem(USER_KEY) ?? 'null'),
  loading: false,

  async login(email, password) {
    const { data } = await api.post('/auth/login', { email, password })
    setToken(data.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    set({ user: data.user })
  },

  async register(email, nickname, password) {
    const { data } = await api.post('/auth/register', { email, nickname, password })
    setToken(data.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    set({ user: data.user })
  },

  logout() {
    setToken(null)
    localStorage.removeItem(USER_KEY)
    set({ user: null })
  },

  /** 页面刷新后用 token 换取最新用户信息，token 失效则清空 */
  async restore() {
    if (!getToken()) return
    set({ loading: true })
    try {
      const { data } = await api.get('/auth/me')
      localStorage.setItem(USER_KEY, JSON.stringify(data))
      set({ user: data })
    } catch {
      set({ user: null })
    } finally {
      set({ loading: false })
    }
  },
}))
