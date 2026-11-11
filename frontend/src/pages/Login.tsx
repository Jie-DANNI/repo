import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage } from '../lib/api'
import { useAuth } from '../store/auth'

export default function Login() {
  const navigate = useNavigate()
  const { login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      if (mode === 'login') await login(email.trim(), password)
      else await register(email.trim(), nickname.trim(), password)
      navigate('/', { replace: true })
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6 bg-gradient-to-b from-slate-50 to-brand-50/40">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-card p-8">
        <div className="text-center">
          <div className="text-4xl">🧠</div>
          <h2 className="mt-3 text-xl font-semibold text-slate-900">
            {mode === 'login' ? '登录忆循环' : '创建账号'}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {mode === 'login' ? '复习不是重复看，而是递进地记住' : '开始你的记忆管理'}
          </p>
        </div>

        <form onSubmit={submit} className="mt-6 space-y-3">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            placeholder="邮箱"
            autoComplete="email"
          />
          {mode === 'register' && (
            <input
              required
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              placeholder="昵称"
              maxLength={32}
            />
          )}
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            placeholder={mode === 'register' ? '密码（至少8位，含字母和数字）' : '密码'}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          />

          {err && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">{err}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-brand-600 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-60"
          >
            {busy ? '处理中…' : mode === 'login' ? '登录' : '注册并登录'}
          </button>
        </form>

        <div className="mt-5 flex items-center justify-between text-xs text-slate-400">
          <button
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setErr('')
            }}
            className="hover:text-brand-600"
          >
            {mode === 'login' ? '没有账号？去注册' : '已有账号？去登录'}
          </button>
          <Link to="/" className="hover:text-brand-600">
            返回首页
          </Link>
        </div>

        <p className="mt-6 rounded-lg bg-slate-50 px-3 py-2 text-[11px] leading-relaxed text-slate-400">
          评审演示账号：demo@memoloop.cn / Demo@2026
        </p>
      </div>
    </div>
  )
}
