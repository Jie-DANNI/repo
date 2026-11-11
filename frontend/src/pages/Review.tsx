import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { errorMessage } from '../lib/api'
import { streamSSE } from '../lib/sse'
import type { AnswerResult, QuizOption, TodayItem } from '../lib/types'
import { QUIZ_TYPE_LABEL } from '../lib/types'
import SocraticDrawer from '../components/SocraticDrawer'

type Phase = 'loading' | 'streaming' | 'ready' | 'grading' | 'graded'

export default function Review() {
  const [queue, setQueue] = useState<TodayItem[]>([])
  const [idx, setIdx] = useState(0)
  const [phase, setPhase] = useState<Phase>('loading')
  const [error, setError] = useState('')

  // 当前题目
  const [question, setQuestion] = useState('')
  const [options, setOptions] = useState<QuizOption[] | null>(null)
  const [itemId, setItemId] = useState<number | null>(null)
  const [picked, setPicked] = useState<string>('')
  const [answerText, setAnswerText] = useState('')

  // 评分结果
  const [result, setResult] = useState<AnswerResult | null>(null)

  // 追问抽屉
  const [convId, setConvId] = useState<number | null>(null)

  const current = queue[idx] ?? null

  // 1) 载入今日队列
  useEffect(() => {
    api
      .get('/review/today', { params: { limit: 20 } })
      .then((r) => setQueue(r.data.items))
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setPhase((p) => (p === 'loading' && true ? 'loading' : p)))
  }, [])

  // 2) 为当前卡流出题（SSE 打字机）
  const startQuiz = useCallback(async (kpId: number) => {
    setPhase('streaming')
    setQuestion('')
    setOptions(null)
    setItemId(null)
    setPicked('')
    setAnswerText('')
    setResult(null)
    setError('')
    try {
      await streamSSE(`/api/review/${kpId}/quiz`, null, (ev) => {
        const t = ev.type as string
        if (t === 'meta') setQuestion('') // meta 到达即代表开始
        else if (t === 'chunk') setQuestion((q) => q + String(ev.text ?? ''))
        else if (t === 'done') {
          setItemId(ev.quiz_item_id as number)
          const opts = ev.options as QuizOption[] | null
          setOptions(opts && opts.length > 0 ? opts : null)
          setPhase('ready')
        }
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : '出题失败，请稍后重试')
      setPhase('ready')
    }
  }, [])

  // 切卡时自动出题
  useEffect(() => {
    if (current) startQuiz(current.kp_id)
  }, [current?.kp_id]) // eslint-disable-line react-hooks/exhaustive-deps

  // 3) 提交作答
  const submit = useCallback(async () => {
    if (itemId === null) return
    const payload: { answer_text?: string; selected_option?: string } = {}
    if (options && picked) payload.selected_option = picked
    else if (answerText.trim()) payload.answer_text = answerText.trim()
    else return

    setPhase('grading')
    setError('')
    try {
      const { data } = await api.post(`/quiz/${itemId}/answer`, payload, { timeout: 180000 })
      setResult(data)
      setPhase('graded')
    } catch (e) {
      setError(errorMessage(e))
      setPhase('ready')
    }
  }, [itemId, options, picked, answerText])

  const next = () => {
    setConvId(null)
    setIdx((i) => i + 1)
  }

  /* ---------- 渲染 ---------- */

  if (phase === 'loading' && queue.length === 0) {
    return <div className="ml-card p-10 text-center text-sm text-[var(--ml-text-muted)]">加载今日队列…</div>
  }

  if (queue.length === 0) {
    return (
      <div className="ml-card flex flex-col items-center gap-4 p-12 text-center">
        <div className="text-3xl">🎉</div>
        <div className="text-lg font-semibold">今日复习已清空</div>
        <div className="text-sm text-[var(--ml-text-muted)]">上传新课件继续积累，或明天再来巩固记忆。</div>
        <Link to="/documents" className="ml-btn ml-btn-primary">
          去知识库
        </Link>
      </div>
    )
  }

  if (idx >= queue.length) {
    return (
      <div className="ml-card flex flex-col items-center gap-4 p-12 text-center">
        <div className="text-3xl">✅</div>
        <div className="text-lg font-semibold">本轮复习完成</div>
        <div className="text-sm text-[var(--ml-text-muted)]">
          共复习 {queue.length} 张卡片。FSRS 已按你的表现重排每张卡的下一次到期时间。
        </div>
        <div className="flex gap-2">
          <Link to="/stats" className="ml-btn">
            查看学习画像
          </Link>
          <Link to="/" className="ml-btn ml-btn-primary">
            回工作台
          </Link>
        </div>
      </div>
    )
  }

  const scorePct = result ? Math.round(result.score * 100) : 0

  return (
    <div className="mx-auto max-w-3xl">
      {/* 进度 */}
      <div className="mb-4 flex items-center justify-between text-sm text-[var(--ml-text-muted)]">
        <span>
          {idx + 1} / {queue.length} · 剩余 {queue.length - idx - 1} 张
        </span>
        <span className="ml-bar-track w-40">
          <span
            className="ml-bar-fill block"
            style={{ width: `${((idx + (phase === 'graded' ? 1 : 0)) / queue.length) * 100}%` }}
          />
        </span>
      </div>

      {/* 知识点卡头 */}
      {current && (
        <div className="ml-card mb-4 flex flex-wrap items-center gap-2 px-5 py-4">
          <span className="text-xl">🃏</span>
          <span className="flex-1 font-semibold">{current.title}</span>
          <span className="ml-badge is-primary">
            第 {current.round} 轮 · {QUIZ_TYPE_LABEL[current.quiz_type]}题
          </span>
          <span className="ml-badge">记忆保有 {Math.round(current.retrievability * 100)}%</span>
          {current.is_new && <span className="ml-badge is-warn">新卡</span>}
        </div>
      )}

      {/* 出题卡 */}
      <div className="ml-card p-6">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--ml-text-muted)]">
          {QUIZ_TYPE_LABEL[current?.quiz_type ?? 'recognition']}题 · AI 出题
        </div>

        {phase === 'streaming' && question === '' && (
          <div className="text-sm text-[var(--ml-text-muted)]">导师正在出题…</div>
        )}
        <div className={`text-lg leading-relaxed ${phase === 'streaming' ? 'stream-cursor' : ''}`}>
          {question || '\u00a0'}
        </div>

        {/* 选项区（选择题 / 判断题） */}
        {options && phase !== 'graded' && (
          <div className="mt-5 space-y-2">
            {options.map((o) => (
              <button
                key={o.id}
                className={`ml-option ${picked === o.id ? 'is-picked' : ''}`}
                disabled={phase === 'grading'}
                onClick={() => setPicked(o.id)}
              >
                <span className="font-semibold">{o.id}.</span>
                <span className="flex-1">{o.text}</span>
              </button>
            ))}
          </div>
        )}

        {/* 判断题：对/错快捷按钮（走 answer_text） */}
        {!options && current?.quiz_type === 'recognition' && phase !== 'graded' && (
          <div className="mt-5 flex gap-3">
            {['正确', '错误'].map((v) => (
              <button
                key={v}
                className={`ml-option justify-center ${answerText === v ? 'is-picked' : ''}`}
                disabled={phase === 'grading'}
                onClick={() => setAnswerText((t) => (t === v ? '' : v))}
              >
                <span className="font-semibold">{v === '正确' ? '✔' : '✘'}</span>
                <span>{v}</span>
              </button>
            ))}
          </div>
        )}

        {/* 主观题（情景 / 费曼）作答框 */}
        {!options && current && current.quiz_type !== 'recognition' && phase !== 'graded' && (
          <div className="mt-5">
            <textarea
              className="ml-textarea"
              placeholder={
                current.quiz_type === 'feynman'
                  ? '用自己的话把这个概念讲给一个完全不懂的人听…'
                  : '结合情景写下你的分析…'
              }
              value={answerText}
              disabled={phase === 'grading'}
              onChange={(e) => setAnswerText(e.target.value)}
            />
          </div>
        )}

        {/* 提交 */}
        {phase !== 'graded' && (
          <div className="mt-5 flex items-center gap-3">
            <button
              className="ml-btn ml-btn-primary px-8"
              disabled={phase !== 'ready' || (options ? !picked : !answerText.trim())}
              onClick={submit}
            >
              {phase === 'grading' ? 'AI 评分中…' : '提交作答'}
            </button>
            <span className="text-xs text-[var(--ml-text-muted)]">
              {options ? '选择一个选项后提交' : current?.quiz_type === 'recognition' ? '判断对错后提交' : '写下答案后提交'}
            </span>
          </div>
        )}

        {/* 评分结果 */}
        {result && (
          <div className="mt-6 space-y-5 border-t border-[var(--ml-border)] pt-5">
            {/* 分数 */}
            <div className="flex items-center gap-4">
              <div
                className={`text-3xl font-semibold ${
                  scorePct >= 80 ? 'text-[var(--ml-success)]' : scorePct >= 50 ? 'text-[var(--ml-warn)]' : 'text-[var(--ml-danger)]'
                }`}
              >
                {scorePct}
              </div>
              <div className="flex-1">
                <div className="ml-bar-track">
                  <div
                    className={`ml-bar-fill ${scorePct >= 80 ? 'is-success' : scorePct >= 50 ? 'is-warn' : 'is-danger'}`}
                    style={{ width: `${scorePct}%` }}
                  />
                </div>
                <div className="mt-1.5 text-xs text-[var(--ml-text-muted)]">
                  FSRS 评级 {['重来', '困难', '良好', '简单'][result.rating - 1]} · 下次复习{' '}
                  {result.fsrs.due_at.slice(0, 16).replace('T', ' ')} · 记忆稳定度{' '}
                  {result.fsrs.stability?.toFixed?.(1) ?? result.fsrs.stability}
                </div>
              </div>
            </div>

            {/* 量规逐点 */}
            {result.per_point?.length > 0 && (
              <div>
                <div className="mb-2 text-xs font-semibold uppercase text-[var(--ml-text-muted)]">评分要点</div>
                <div className="space-y-1.5">
                  {result.per_point.map((p, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      <span className={p.hit ? 'text-[var(--ml-success)]' : 'text-[var(--ml-danger)]'}>
                        {p.hit ? '✔' : '✘'}
                      </span>
                      <span className={p.hit ? '' : 'text-[var(--ml-danger)]'}>{p.point}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 错因标签 */}
            {result.error_tags?.length > 0 && (
              <div>
                <div className="mb-2 text-xs font-semibold uppercase text-[var(--ml-text-muted)]">错因诊断</div>
                <div className="flex flex-wrap gap-2">
                  {result.error_tags.map((t) => (
                    <span key={t} className="ml-chip is-danger">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* AI 反馈 */}
            {result.feedback && (
              <div className="ml-card bg-[var(--ml-primary-soft)] p-4 text-sm leading-relaxed">
                {result.feedback}
              </div>
            )}

            {/* 弱分补充：参考答案 + 追问入口 */}
            {scorePct < 80 && (
              <div className="space-y-3">
                {result.answer && (
                  <div className="ml-card p-4 text-sm leading-relaxed">
                    <span className="mr-2 font-semibold">参考要点：</span>
                    {result.answer}
                  </div>
                )}
                {result.conversation_id && (
                  <button
                    className="ml-btn ml-btn-primary"
                    onClick={() => setConvId(result.conversation_id)}
                  >
                    🎓 和苏格拉底导师聊聊这个错因（推荐）
                  </button>
                )}
              </div>
            )}

            {/* 下一张 */}
            <div className="flex items-center gap-3">
              <button className="ml-btn ml-btn-primary px-8" onClick={next}>
                {idx + 1 >= queue.length ? '完成本轮' : '下一张 →'}
              </button>
              {scorePct >= 80 && <span className="ml-badge is-ok">掌握良好，稳定度已延长</span>}
            </div>
          </div>
        )}

        {error && (
          <div className="ml-badge is-danger mt-4 px-3 py-2 text-sm" role="alert">
            {error}
          </div>
        )}
      </div>

      {/* 追问抽屉 */}
      {convId !== null && current && (
        <SocraticDrawer conversationId={convId} kpTitle={current.title} onClose={() => setConvId(null)} />
      )}
    </div>
  )
}
