export interface Session {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface TableGroup {
  id: string
  name: string
  description?: string | null
  table_count: number
  is_default?: boolean
}

export interface QuickQuestion {
  id: string
  display_name?: string | null
  question_text: string
  table_group_id: string
  is_pinned: boolean
  sort_order: number
  usage_count: number
  last_used_at?: string | null
  created_at: string
  updated_at: string
}

export interface QuickQuestionInput {
  display_name?: string | null
  question_text: string
  table_group_id: string
  is_pinned?: boolean
}

export interface QueryResult {
  columns: string[]
  rows: (string | number | null)[][]
  row_count: number
}

export type MessageRole = 'user' | 'ai'
export type MessageStatus = 'streaming' | 'completed' | 'stopped' | 'failed'

export interface Message {
  id: string
  role: MessageRole
  content: string
  result?: QueryResult
  sql?: string
  explanation?: string
  thinking?: boolean
  status?: MessageStatus
  runId?: string
  lastEventId?: string
  error?: string
  createdAt: number
}

/** 服务端返回的消息格式（GET /api/sessions/{id}/messages） */
export interface MessageOut {
  id: string
  role: 'user' | 'assistant'
  content: string
  metadata?: {
    sql?: string
    explanation?: string
    result?: QueryResult
    status?: MessageStatus
    run_id?: string
    started_at?: string
    finished_at?: string
    last_event_id?: string
    last_heartbeat?: string
    error?: string
    stopped_at?: string
  } | null
  created_at: string
}
