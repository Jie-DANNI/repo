import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import type { StatsOverview } from '../lib/types'

/** 工作台：今日复习入口 + 关键指标速览 */
export default function Home() {
  const [todayTotal, setTodayTotal] = useState<number | null>(null)
  const [stats, setStats] = useState<StatsOverview | null>(null)

  useEffect(() => {
    api
      .get('/review/today', { params: { limit: 1 } })
      .then((r) => setTodayTotal(r.data.total))
      .catch(() => setTodayTotal(null))
    api
      .get('/stats/overview')
      .then((r) => setStats(r.data))
      .catch(() => setStats(null))
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-semibold">工作台</h1>
      <p className="mt-1 text-sm text-[var(--ml-text-muted)]">
        上传课件 → AI 建卡 → 按遗忘曲线复习，答错会被定向追问。
      </p>

      {/* 主行动区 */}
      <div className="ml-card mt-6 flex flex-col items-center gap-4 px-6 py-10">
        {todayTotal === null ? (
          <div className="text-sm text-[var(--ml-text-muted)]">加载中…</div>
        ) : todayTotal > 0 ? (
          <>
            <div className="text-4xl font-semibold">{todayTotal}</div>
            <div className="text-sm text-[var(--ml-text-muted)]">张卡片等待复习</div>
            <Link to="/review" className="ml-btn ml-btn-primary px-8 py-3 text-base">
              开始今日复习 →
            </Link>
          </>
        ) : (
          <>
            <div className="text-lg">🎉 今日复习已清空</div>
            <div className="text-sm text-[var(--ml-text-muted)]">上传新课件，开始积累知识卡片</div>
            <Link to="/documents" className="ml-btn ml-btn-primary px-8 py-3 text-base">
              去知识库上传 →
            </Link>
          </>
        )}
      </div>

      {/* 指标速览 */}
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {[
          {
            icon: '📚',
            label: '知识点总数',
            value: stats ? String(stats.kp_total) : '…',
            link: '/documents',
          },
          {
            icon: '🧠',
            label: '平均记忆保有率',
            value: stats ? `${Math.round(stats.retention.avg_retrievability * 100)}%` : '…',
            link: '/stats',
          },
          {
            icon: '🔍',
            label: '头号错因',
            value:
              stats && stats.error_top.length > 0 ? stats.error_top[0].tag : '暂无',
            link: '/stats',
          },
        ].map((c) => (
          <Link key={c.label} to={c.link} className="ml-card block p-5 transition hover:-translate-y-0.5">
            <div className="text-2xl">{c.icon}</div>
            <div className="mt-3 text-2xl font-semibold">{c.value}</div>
            <div className="mt-1 text-xs text-[var(--ml-text-muted)]">{c.label}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
