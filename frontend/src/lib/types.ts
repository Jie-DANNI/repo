/** 与后端 schema 一一对应的类型定义（改字段时两边同步改） */

export interface DocumentItem {
  id: number
  title: string
  file_name: string
  file_type: string
  file_size: number
  page_count: number | null
  status: 'uploaded' | 'parsing' | 'chunked' | 'extracting' | 'extracted' | 'failed'
  parse_error: string | null
  created_at: string
  chunk_count: number
}

export interface ChunkItem {
  id: number
  heading_path: string | null
  page_no: number | null
  token_count: number
  content: string
}

export interface KnowledgePointItem {
  id: number
  title: string
  summary: string | null
  difficulty: number
  importance: number
  keywords: string[]
  round: number
  state: string
  due_at: string | null
  retrievability: number
}

export interface TodayItem {
  kp_id: number
  title: string
  summary: string | null
  difficulty: number
  importance: number
  round: number
  quiz_type: 'recognition' | 'choice' | 'scenario' | 'feynman'
  retrievability: number
  state: string
  due_at: string | null
  is_new: boolean
}

export interface QuizOption {
  id: string
  text: string
}

export interface AnswerResult {
  score: number
  rating: number
  per_point: { point: string; hit: boolean }[]
  error_tags: string[]
  feedback: string
  fsrs: {
    state: string
    stability: number
    difficulty: number
    due_at: string
    retrievability?: number
    rating?: number
  }
  conversation_id: number | null
  answer: string | null
  explanation?: string | null
}

export interface ConversationMessage {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

export interface Conversation {
  id: number
  status: 'open' | 'closed'
  trigger_tags: string[] | null
  title: string
  messages: ConversationMessage[]
}

export interface StatsOverview {
  heat: { date: string; count: number; avg_score: number }[]
  error_top: { tag: string; count: number }[]
  retention: { avg_retrievability: number; cards: number }
  kp_total: number
}

/** 题型中文名与文案 */
export const QUIZ_TYPE_LABEL: Record<TodayItem['quiz_type'], string> = {
  recognition: '判断',
  choice: '选择',
  scenario: '情景',
  feynman: '费曼讲解',
}

/** 文档状态 → 徽章样式与中文 */
export const DOC_STATUS: Record<DocumentItem['status'], { label: string; tone: string }> = {
  uploaded: { label: '待解析', tone: '' },
  parsing: { label: '解析中', tone: 'is-warn' },
  chunked: { label: '已切块', tone: 'is-primary' },
  extracting: { label: 'AI 建库中', tone: 'is-warn' },
  extracted: { label: '已建库', tone: 'is-ok' },
  failed: { label: '失败', tone: 'is-danger' },
}

export function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return iso.slice(0, 10)
}
