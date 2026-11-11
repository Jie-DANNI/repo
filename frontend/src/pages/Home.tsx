import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../store/auth'

/** 登录后的工作台占位页：P2 起将替换为资料上传 + 今日复习入口 */
export default function Home() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [health, setHealth] = useState<'checking' | 'ok' | 'fail'>('checking')

  useEffect(() => {
    axios
      .get('/api/health')
      .then((r) => setHealth(r.data.status === 'ok' ? 'ok' : 'fail'))
      .catch(() => setHealth('fail'))
  }, [])

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">🧠</span>
            <span className="font-semibold text-slate-900">忆循环 MemoLoop</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-500">
              {user?.nickname}
              {user?.role === 'demo' && (
                <span className="ml-2 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] text-amber-600">
                  演示账号
                </span>
              )}
            </span>
            <button
              onClick={() => {
                logout()
                navigate('/login', { replace: true })
              }}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            >
              退出
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="text-2xl font-semibold text-slate-900">
          你好，{user?.nickname} 👋
        </h1>
        <p className="mt-2 text-slate-500">
          P1 认证已完成。接下来这里会变成你的记忆工作台。
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {[
            { icon: '📄', title: '上传资料', desc: 'PDF 自动解析成知识点卡片', tag: 'P2' },
            { icon: '🔁', title: '今日复习', desc: '按遗忘曲线调度，题型逐轮升级', tag: 'P5-P6' },
            { icon: '📊', title: '学习统计', desc: '热力图 + 错因 Top5 + 保有率曲线', tag: 'P9' },
          ].map((c) => (
            <div
              key={c.title}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-card"
            >
              <div className="text-2xl">{c.icon}</div>
              <h3 className="mt-3 font-medium text-slate-900">{c.title}</h3>
              <p className="mt-1 text-sm text-slate-500">{c.desc}</p>
              <span className="mt-3 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
                待实现 {c.tag}
              </span>
            </div>
          ))}
        </div>

        <div className="mt-8 flex items-center gap-2 text-xs text-slate-400">
          <span>服务状态</span>
          <span
            className={
              health === 'ok'
                ? 'text-emerald-600'
                : health === 'fail'
                  ? 'text-red-500'
                  : 'text-slate-400'
            }
          >
            {health === 'checking' ? '检测中…' : health === 'ok' ? '正常' : '异常'}
          </span>
          <span className="mx-2 text-slate-300">|</span>
          <span>用户 ID {user?.id}</span>
          <span className="mx-2 text-slate-300">|</span>
          <span>{user?.email}</span>
        </div>
      </main>
    </div>
  )
}
