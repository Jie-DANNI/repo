import { useEffect, useState } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import axios from 'axios'

/** 首页占位：P0 阶段用于验证前后端联通，P9 阶段替换为正式工作台 */
function Home() {
  const [health, setHealth] = useState<'checking' | 'ok' | 'fail'>('checking')
  const [dbVersion, setDbVersion] = useState('')

  useEffect(() => {
    axios
      .get('/api/health')
      .then((r) => {
        setHealth(r.data.status === 'ok' ? 'ok' : 'fail')
        setDbVersion(r.data.db_version ?? '')
      })
      .catch(() => setHealth('fail'))
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-xl w-full bg-white rounded-2xl shadow-card p-10 text-center">
        <div className="text-5xl mb-4">🧠</div>
        <h1 className="text-2xl font-semibold text-slate-900">忆循环 MemoLoop</h1>
        <p className="mt-2 text-slate-500">
          AI 遗忘曲线学习管家 · 复习不是重复看，而是递进地记住
        </p>

        <div className="mt-8 flex items-center justify-center gap-2 text-sm">
          <span className="text-slate-400">后端状态</span>
          <span
            className={
              'px-3 py-1 rounded-full font-medium ' +
              (health === 'ok'
                ? 'bg-emerald-50 text-emerald-600'
                : health === 'fail'
                  ? 'bg-red-50 text-red-600'
                  : 'bg-slate-100 text-slate-500')
            }
          >
            {health === 'checking' ? '检测中…' : health === 'ok' ? '连接正常' : '未连接'}
          </span>
        </div>
        {dbVersion && (
          <p className="mt-3 text-xs text-slate-400 break-all">DB: {dbVersion}</p>
        )}

        <p className="mt-8 text-xs text-slate-400">
          P0 脚手架 · 后续将接入 登录 / 资料上传 / 知识库 / 今日复习 / 学习统计
        </p>
        <Link
          to="/login"
          className="inline-block mt-6 px-5 py-2.5 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition"
        >
          进入登录页（占位）
        </Link>
      </div>
    </div>
  )
}

function Login() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-card p-8">
        <h2 className="text-xl font-semibold text-slate-900">登录忆循环</h2>
        <p className="mt-1 text-sm text-slate-500">P1 阶段实现真实认证</p>
        <input
          className="mt-6 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none focus:border-brand-500"
          placeholder="邮箱"
        />
        <input
          type="password"
          className="mt-3 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none focus:border-brand-500"
          placeholder="密码"
        />
        <button className="mt-4 w-full rounded-xl bg-brand-600 py-2.5 text-sm font-medium text-white hover:bg-brand-700 transition">
          登录
        </button>
        <Link to="/" className="mt-4 block text-center text-xs text-slate-400 hover:text-brand-600">
          返回首页
        </Link>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="*" element={<Home />} />
    </Routes>
  )
}
