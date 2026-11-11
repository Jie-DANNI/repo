import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon'
import api, { errorMessage } from '../lib/api'
import type { ChunkItem, DocumentItem, KnowledgePointItem } from '../lib/types'
import { DOC_STATUS, fmtSize } from '../lib/types'

/** 文档状态是否处于"自动推进中"（需要轮询刷新） */
const BUSY: DocumentItem['status'][] = ['uploaded', 'parsing', 'extracting']

export default function Documents() {
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [openId, setOpenId] = useState<number | null>(null)
  const [chunks, setChunks] = useState<ChunkItem[]>([])
  const [kps, setKps] = useState<KnowledgePointItem[]>([])
  const dragRef = useRef<HTMLDivElement>(null)

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get('/documents')
      setDocs(data)
      setError('')
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // 有任务在跑（解析/建库）时轮询
  useEffect(() => {
    if (!docs.some((d) => BUSY.includes(d.status))) return
    const t = setTimeout(refresh, 2500)
    return () => clearTimeout(t)
  }, [docs, refresh])

  const upload = useCallback(
    async (file: File) => {
      if (uploading) return
      if (!/\.(pdf|md|txt)$/i.test(file.name)) { setError('请上传 PDF、Markdown 或 TXT 文件'); return }
      if (file.size > 50 * 1024 * 1024) { setError('文件大小不能超过 50MB'); return }
      setUploading(true)
      setError('')
      try {
        const form = new FormData()
        form.append('file', file)
        await api.post('/documents', form, { timeout: 120000 })
        await refresh()
      } catch (e) {
        setError(errorMessage(e))
      } finally {
        setUploading(false)
      }
    },
    [refresh, uploading],
  )

  const extract = useCallback(
    async (id: number) => {
      try {
        await api.post(`/documents/${id}/extract`, {}, { timeout: 30000 })
        await refresh()
      } catch (e) {
        setError(errorMessage(e))
      }
    },
    [refresh],
  )

  const remove = useCallback(
    async (id: number) => {
      if (!window.confirm('删除该文档及其全部知识点和复习记录？')) return
      try {
        await api.delete(`/documents/${id}`)
        if (openId === id) setOpenId(null)
        await refresh()
      } catch (e) {
        setError(errorMessage(e))
      }
    },
    [refresh, openId],
  )

  // 展开某文档：拉切块 + 知识点
  useEffect(() => {
    if (openId === null) {
      setChunks([])
      setKps([])
      return
    }
    let alive = true
    ;(async () => {
      try {
        const [c, k] = await Promise.all([
          api.get(`/documents/${openId}/chunks`, { params: { page: 1, size: 50 } }),
          api.get('/knowledge-points', { params: { document_id: openId, size: 100 } }),
        ])
        if (!alive) return
        setChunks(c.data.items)
        setKps(k.data.items)
      } catch (e) {
        if (alive) setError(errorMessage(e))
      }
    })()
    return () => {
      alive = false
    }
  }, [openId])

  const toggleOpen = (id: number) => setOpenId((cur) => (cur === id ? null : id))

  return (
    <div>
      <span className="page-kicker">MY KNOWLEDGE LIBRARY</span>
      <h1 className="text-2xl font-semibold">我的知识库</h1>
      <p className="mt-1 text-sm text-[var(--ml-text-muted)]">
        让每一份资料都有条理，让每一个知识点都值得记住。
      </p>

      {/* 上传区 */}
      <div
        ref={dragRef}
        className="ml-card document-upload mt-6 cursor-pointer border-dashed p-8 text-center transition"
        role="button"
        tabIndex={0}
        aria-label="上传学习资料"
        aria-disabled={uploading}
        onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !uploading) { e.preventDefault(); e.currentTarget.click() } }}
        onClick={() => {
          if (uploading) return
          const input = document.createElement('input')
          input.type = 'file'
          input.accept = '.pdf,.md,.txt'
          input.onchange = () => input.files?.[0] && upload(input.files[0])
          input.click()
        }}
        onDragOver={(e) => {
          e.preventDefault()
          dragRef.current?.style.setProperty('border-color', 'var(--ml-primary)')
        }}
        onDragLeave={() => dragRef.current?.style.removeProperty('border-color')}
        onDrop={(e) => {
          e.preventDefault()
          dragRef.current?.style.removeProperty('border-color')
          const f = e.dataTransfer.files?.[0]
          if (f) upload(f)
        }}
      >
        {uploading ? (
          <div className="text-sm text-[var(--ml-warn)]">⏳ 上传并解析中…（大文件可能需要几十秒）</div>
        ) : (
          <>
            <div className="upload-symbol"><Icon name="upload" size={25}/></div>
            <div className="mt-2 text-sm font-medium">点击选择文件，或把课件拖到这里</div>
            <div className="mt-1 text-xs text-[var(--ml-text-muted)]">支持 PDF / Markdown / TXT，≤ 50MB</div>
          </>
        )}
      </div>

      {error && (
        <div className="ml-badge is-danger mt-3 px-3 py-2 text-sm" role="alert">
          {error}
        </div>
      )}

      {/* 文档列表 */}
      <div className="mt-6 space-y-3">
        {docs.length === 0 && !error && (
          <div className="ml-card p-8 text-center text-sm text-[var(--ml-text-muted)]">
            还没有文档，先上传一份课件试试。
          </div>
        )}
        {docs.map((d) => {
          const st = DOC_STATUS[d.status]
          const busy = BUSY.includes(d.status)
          return (
            <div key={d.id} className="ml-card overflow-hidden">
              <button
                className="flex w-full items-center gap-3 px-5 py-4 text-left"
                onClick={() => toggleOpen(d.id)}
              >
                <span className="text-xl">{d.file_type === 'pdf' ? '📕' : '📝'}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{d.title}</span>
                  <span className="mt-0.5 block text-xs text-[var(--ml-text-muted)]">
                    {fmtSize(d.file_size)}
                    {d.page_count ? ` · ${d.page_count} 页` : ''} · {d.chunk_count} 切块 ·
                    创建于 {d.created_at.slice(0, 10)}
                  </span>
                </span>
                <span className={`ml-badge ${st.tone}`}>{st.label}</span>
                <span className="ml-btn ml-btn-ghost text-xs">{openId === d.id ? '收起 ▲' : '详情 ▼'}</span>
              </button>

              {/* 失败原因 */}
              {d.status === 'failed' && d.parse_error && (
                <div className="border-t border-[var(--ml-border)] bg-[var(--ml-danger-soft)] px-5 py-3 text-xs text-[var(--ml-danger)]">
                  {d.parse_error.slice(0, 200)}
                </div>
              )}

              {/* 操作条 */}
              <div className="flex items-center gap-2 border-t border-[var(--ml-border)] px-5 py-3">
                {(d.status === 'chunked' || d.status === 'failed') && (
                  <button className="ml-btn ml-btn-primary" onClick={() => extract(d.id)}>
                    {d.status === 'failed' ? '重试 AI 建库' : '构建知识库（AI 抽取知识点）'}
                  </button>
                )}
                {d.status === 'extracted' && <span className="ml-badge is-ok">知识点就绪，去「今日复习」开测</span>}
                {busy && <span className="ml-badge is-warn">后台处理中，页面自动刷新…</span>}
                <span className="flex-1" />
                <button className="ml-btn ml-btn-ghost text-xs text-[var(--ml-danger)]" onClick={() => remove(d.id)}>
                  删除
                </button>
              </div>

              {/* 展开详情：切块 + 知识点 */}
              {openId === d.id && (
                <div className="space-y-5 border-t border-[var(--ml-border)] px-5 py-4">
                  <section>
                    <h4 className="mb-2 text-xs font-semibold uppercase text-[var(--ml-text-muted)]">
                      语义切块（{chunks.length}）
                    </h4>
                    <div className="space-y-2">
                      {chunks.map((c) => (
                        <div key={c.id} className="ml-card p-3 text-sm">
                          <div className="flex items-center gap-2 text-xs text-[var(--ml-text-muted)]">
                            <span className="ml-chip">{c.heading_path ?? '正文'}</span>
                            <span>p{c.page_no ?? '-'}</span>
                            <span>· {c.token_count} tokens</span>
                          </div>
                          <div className="mt-1.5 line-clamp-2 leading-relaxed">{c.content}</div>
                        </div>
                      ))}
                      {chunks.length === 0 && <div className="text-sm text-[var(--ml-text-muted)]">暂无切块</div>}
                    </div>
                  </section>

                  <section>
                    <h4 className="mb-2 text-xs font-semibold uppercase text-[var(--ml-text-muted)]">
                      知识点卡片（{kps.length}）
                    </h4>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {kps.map((k) => (
                        <div key={k.id} className="ml-card p-3">
                          <div className="flex items-start justify-between gap-2">
                            <span className="font-medium">{k.title}</span>
                            <span className="ml-badge is-primary">第 {k.round} 轮</span>
                          </div>
                          {k.summary && (
                            <div className="mt-1 line-clamp-2 text-xs leading-relaxed text-[var(--ml-text-muted)]">
                              {k.summary}
                            </div>
                          )}
                          <div className="mt-2 flex flex-wrap items-center gap-1.5">
                            {k.keywords.slice(0, 4).map((w) => (
                              <span key={w} className="ml-chip">
                                {w}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                      {kps.length === 0 && (
                        <div className="text-sm text-[var(--ml-text-muted)]">
                          尚未抽取知识点{d.status === 'extracted' ? '（构建中）' : ''}
                        </div>
                      )}
                    </div>
                  </section>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
