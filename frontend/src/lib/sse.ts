import { getToken } from './api'

export type SSEHandler = (ev: Record<string, unknown>) => void

/**
 * 消费后端 SSE（POST + Authorization 头）。
 * 逐帧解析 `data: {...}` 事件，通过 onEvent 回调流出。
 * 后端事件类型：meta / chunk / done / error。
 */
export async function streamSSE(
  path: string,
  body: unknown | null,
  onEvent: SSEHandler,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let payload: BodyInit | undefined
  if (body !== null && body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const resp = await fetch(path, { method: 'POST', headers, body: payload, signal })
  if (!resp.ok || !resp.body) {
    let detail = ''
    try {
      detail = await resp.text()
    } catch {
      /* ignore */
    }
    throw new Error(detail || `请求失败（HTTP ${resp.status}）`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })

    let sep: number
    while ((sep = buf.indexOf('\n\n')) !== -1) {
      const frame = buf.slice(0, sep)
      buf = buf.slice(sep + 2)
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data:')) continue
        const raw = line.slice(5).trim()
        if (!raw) continue
        try {
          onEvent(JSON.parse(raw))
        } catch {
          /* 忽略坏帧 */
        }
      }
    }
  }
}
