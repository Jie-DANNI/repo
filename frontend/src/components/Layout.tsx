import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

const NAV = [
  { to: '/', label: '工作台', icon: '🏠', end: true },
  { to: '/documents', label: '知识库', icon: '📚' },
  { to: '/review', label: '今日复习', icon: '🔁' },
  { to: '/stats', label: '学习画像', icon: '📊' },
]

/** 应用外壳：顶栏 + 导航 + 内容区。视觉全部来自 theme.css 的令牌。 */
export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-[var(--ml-border)] bg-[var(--ml-surface)]/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">🧠</span>
            <span className="text-base font-semibold">忆循环 MemoLoop</span>
          </div>
          <nav className="flex items-center gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) => `ml-nav-link ${isActive ? 'is-active' : ''}`}
              >
                <span>{n.icon}</span>
                <span className="hidden sm:inline">{n.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2 text-sm">
            <span className="hidden text-[var(--ml-text-muted)] md:inline">{user?.nickname}</span>
            {user?.role === 'demo' && <span className="ml-badge is-warn">演示账号</span>}
            <button
              className="ml-btn-ghost ml-btn"
              onClick={() => {
                logout()
                navigate('/login', { replace: true })
              }}
            >
              退出
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-8">
        <Outlet />
      </main>

      <footer className="mx-auto max-w-5xl px-5 pb-6 text-xs text-[var(--ml-text-muted)]">
        MemoLoop · FSRS-4.5 记忆调度 × RAG 混合检索 × 三 Agent 协作
      </footer>
    </div>
  )
}
