import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../lib/api'
import { streamSSE } from '../lib/sse'
import type { ConversationMessage } from '../lib/types'

interface Props {
  conversationId: number
  kpTitle: string
  onClose: () => void
}

/** 苏格拉底追问抽屉：多轮对话，导师回复流式渲染。 */
export default function SocraticDrawer({ conversationId, kpTitle, onClose }: Props) {
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [liveText, setLiveText] = useState('') // 正在流式生成的回复缓冲
  const [streaming, setStreaming] = useState(false)
  const [closed, setClosed] = useState(false)
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  // 载入历史 + 状态
  useEffect(() => {
    let alive = true
    api
      .get(`/conversations/${conversationId}`)
      .then((r) => {
        if (!alive) return
        setMessages(r.data.messages)
        setClosed(r.data.status === 'closed')
      })
      .catch(() => alive && setError('会话加载失败'))
    return () => {
      alive = false
    }
  }, [conversationId])

  // 新消息时滚到底
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, liveText])

  const send = useCallback(async () => {
    const content = input.trim()
    if (!content || streaming || closed) return
    setInput('')
    setError('')
    setMessages((m) => [...m, { role: 'user', content }])
    setLiveText('')
    setStreaming(true)
    try {
      await streamSSE(`/api/conversations/${conversationId}/messages`, { content }, (ev) => {
        if (ev.type === 'chunk') setLiveText((t) => t + String(ev.text ?? ''))
        else if (ev.type === 'done' && ev.closed) setClosed(true)
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : '发送失败')
    } finally {
      // 流结束：缓冲内容固化为一条完整消息
      setLiveText((t) => {
        if (t) setMessages((m) => [...m, { role: 'assistant', content: t }])
        return ''
      })
      setStreaming(false)
    }
  }, [input, streaming, closed, conversationId])

  return (
    <>
      <div className="ml-drawer-mask" onClick={onClose} />
      <aside className="ml-drawer">
        <header className="flex items-center gap-2 border-b border-[var(--ml-border)] px-4 py-3">
          <span className="text-lg">🎓</span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold">苏格拉底导师 · 定向追问</div>
            <div className="truncate text-xs text-[var(--ml-text-muted)]">{kpTitle}</div>
          </div>
          {closed && <span className="ml-badge is-ok">已收束</span>}
          <button className="ml-btn ml-btn-ghost" onClick={onClose}>
            ✕
          </button>
        </header>

        <div ref={listRef} className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
          {messages.length === 0 && !liveText && (
            <div className="text-center text-xs text-[var(--ml-text-muted)]">
              导师会针对你刚才答错的点提问，不直接给答案。
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`ml-bubble ${m.role === 'user' ? 'ml-bubble-user' : 'ml-bubble-ai'}`}
            >
              {m.content}
            </div>
          ))}
          {liveText && (
            <div className="ml-bubble ml-bubble-ai stream-cursor">{liveText}</div>
          )}
          {error && <div className="ml-badge is-danger px-3 py-2 text-xs">{error}</div>}
        </div>

        <footer className="border-t border-[var(--ml-border)] p-3">
          {closed ? (
            <div className="px-2 py-2 text-center text-xs text-[var(--ml-text-muted)]">
              本次补弱已收束，回到复习页继续下一张卡。
            </div>
          ) : (
            <div className="flex gap-2">
              <input
                className="ml-input"
                placeholder="说说你的想法…（导师只会反问，不会直接给答案）"
                value={input}
                disabled={streaming}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
              />
              <button className="ml-btn ml-btn-primary" disabled={streaming || !input.trim()} onClick={send}>
                {streaming ? '…' : '发送'}
              </button>
            </div>
          )}
        </footer>
      </aside>
    </>
  )
}
