import { useEffect, useState } from 'react'
import api from '../lib/api'
import type { StatsOverview } from '../lib/types'

/** 学习画像：复习热力图 + 错因 Top5 + 保有率 */
export default function Stats() {
  const [stats, setStats] = useState<StatsOverview | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/stats/overview')
      .then((r) => setStats(r.data))
      .catch(() => setError('统计加载失败'))
  }, [])

  if (error) return <div className="ml-badge is-danger px-3 py-2">{error}</div>
  if (!stats) return <div className="text-sm text-[var(--ml-text-muted)]">加载中…</div>

  const maxErr = Math.max(1, ...stats.error_top.map((e) => e.count))

  return (
    <div>
      <span className="page-kicker">YOUR LEARNING INSIGHTS</span>
      <h1 className="text-2xl font-semibold">学习画像</h1>
      <p className="mt-1 text-sm text-[var(--ml-text-muted)]">
        看见知识的积累，找到理解的薄弱处，安排下一步学习。
      </p>

      {/* 三个总览数 */}
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <div className="ml-card p-5">
          <div className="text-xs text-[var(--ml-text-muted)]">知识点总数</div>
          <div className="mt-2 text-3xl font-semibold">{stats.kp_total}</div>
        </div>
        <div className="ml-card p-5">
          <div className="text-xs text-[var(--ml-text-muted)]">平均记忆保有率</div>
          <div className="mt-2 text-3xl font-semibold">
            {Math.round(stats.retention.avg_retrievability * 100)}%
          </div>
          <div className="mt-2 ml-bar-track">
            <div
              className="ml-bar-fill is-success"
              style={{ width: `${Math.round(stats.retention.avg_retrievability * 100)}%` }}
            />
          </div>
        </div>
        <div className="ml-card p-5">
          <div className="text-xs text-[var(--ml-text-muted)]">在册卡片</div>
          <div className="mt-2 text-3xl font-semibold">{stats.retention.cards}</div>
        </div>
      </div>

      {/* 近 90 天热力条 */}
      <div className="ml-card mt-6 p-5">
        <div className="text-sm font-semibold">近 90 天复习热力</div>
        {stats.heat.length === 0 ? (
          <div className="mt-3 text-sm text-[var(--ml-text-muted)]">
            暂无复习记录——去「今日复习」答几题，这里就会亮起来。
          </div>
        ) : (
          <div className="mt-3 flex flex-wrap items-end gap-1.5">
            {stats.heat.map((h) => (
              <div key={h.date} className="group relative">
                <div
                  title={`${h.date}：${h.count} 次 · 均分 ${(h.avg_score * 100).toFixed(0)}%`}
                  style={{
                    width: 14,
                    height: 14 + Math.min(h.count, 10) * 4,
                    background: 'var(--ml-primary)',
                    opacity: 0.35 + Math.min(h.avg_score, 1) * 0.65,
                    borderRadius: 4,
                  }}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 错因 Top5 */}
      <div className="ml-card mt-6 p-5">
        <div className="text-sm font-semibold">错因 Top5</div>
        {stats.error_top.length === 0 ? (
          <div className="mt-3 text-sm text-[var(--ml-text-muted)]">暂无错因记录，继续保持。</div>
        ) : (
          <div className="mt-3 space-y-2.5">
            {stats.error_top.map((e, i) => (
              <div key={e.tag} className="flex items-center gap-3 text-sm">
                <span className="w-6 text-xs text-[var(--ml-text-muted)]">#{i + 1}</span>
                <span className="ml-chip is-danger">{e.tag}</span>
                <span className="ml-bar-track flex-1">
                  <span
                    className="ml-bar-fill is-danger block"
                    style={{ width: `${(e.count / maxErr) * 100}%` }}
                  />
                </span>
                <span className="text-xs text-[var(--ml-text-muted)]">×{e.count}</span>
              </div>
            ))}
          </div>
        )}
        {stats.error_top.length > 0 && (
          <div className="mt-4 text-xs text-[var(--ml-text-muted)]">
            这些错因会注入到相关知识点的后续出题与追问中。
          </div>
        )}
      </div>
    </div>
  )
}
