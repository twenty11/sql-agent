import { api } from './api'
import type { Session, MessageOut, TableGroup, QuickQuestion, QuickQuestionInput } from '../types/chat'

export const chatService = {
  async listSessions(): Promise<Session[]> {
    const res = await api.get<Session[]>('/api/sessions')
    return res.data
  },

  async createSession(title = '新对话'): Promise<Session> {
    const res = await api.post<Session>('/api/sessions', { title })
    return res.data
  },

  async renameSession(id: string, title: string): Promise<Session> {
    const res = await api.put<Session>(`/api/sessions/${id}`, { title })
    return res.data
  },

  async deleteSession(id: string): Promise<void> {
    await api.delete(`/api/sessions/${id}`)
  },

  async listMessages(sessionId: string, limit = 100): Promise<MessageOut[]> {
    const res = await api.get<MessageOut[]>(`/api/sessions/${sessionId}/messages`, {
      params: { limit },
    })
    return res.data
  },

  async generateSessionTitle(sessionId: string): Promise<{ title: string }> {
    const res = await api.post<{ title: string }>(`/api/sessions/${sessionId}/generate-title`)
    return res.data
  },

  /**
   * 发起 SSE 流式查询，返回 EventSource
   * 调用方负责关闭 EventSource
   */
  createQueryStream(question: string, sessionId: string, groupId: string | null | undefined, runId: string): EventSource {
    const token = localStorage.getItem('access_token') || ''
    const params = new URLSearchParams({
      q: question,
      session_id: sessionId,
      run_id: runId,
    })
    params.set('token', token)
    if (groupId) params.set('group_id', groupId)
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
    return new EventSource(`${baseUrl}/api/query?${params.toString()}`)
  },

  createResumeStream(runId: string, fromEventId?: string): EventSource {
    const token = localStorage.getItem('access_token') || ''
    const params = new URLSearchParams({
      run_id: runId,
      from_event_id: fromEventId || '0-0',
    })
    params.set('token', token)
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
    return new EventSource(`${baseUrl}/api/query/resume?${params.toString()}`)
  },

  async cancelQuery(runId: string): Promise<void> {
    await api.post('/api/query/cancel', { run_id: runId })
  },

  async exportQueryResult(resultId: string): Promise<{ blob: Blob; filename: string }> {
    const res = await api.get<Blob>(`/api/query-results/${resultId}/export`, {
      responseType: 'blob',
    })
    const disposition = res.headers['content-disposition']
    const fallback = `query_result_${resultId}.xlsx`
    const filename = parseContentDispositionFilename(disposition) || fallback
    return { blob: res.data, filename }
  },

  async fetchUserTableGroups(): Promise<TableGroup[]> {
    const res = await api.get<TableGroup[]>('/profile/table-groups')
    return res.data
  },

  async listQuickQuestions(): Promise<QuickQuestion[]> {
    const res = await api.get<QuickQuestion[]>('/api/quick-questions')
    return res.data
  },

  async createQuickQuestion(payload: QuickQuestionInput): Promise<QuickQuestion> {
    const res = await api.post<QuickQuestion>('/api/quick-questions', payload)
    return res.data
  },

  async updateQuickQuestion(id: string, payload: Partial<QuickQuestionInput>): Promise<QuickQuestion> {
    const res = await api.put<QuickQuestion>(`/api/quick-questions/${id}`, payload)
    return res.data
  },

  async deleteQuickQuestion(id: string): Promise<void> {
    await api.delete(`/api/quick-questions/${id}`)
  },

  async reorderQuickQuestions(orderedIds: string[]): Promise<QuickQuestion[]> {
    const res = await api.post<QuickQuestion[]>('/api/quick-questions/reorder', {
      ordered_ids: orderedIds,
    })
    return res.data
  },

  async markQuickQuestionUsed(id: string): Promise<QuickQuestion> {
    const res = await api.post<QuickQuestion>(`/api/quick-questions/${id}/use`)
    return res.data
  },
}

function parseContentDispositionFilename(disposition?: string): string | null {
  if (!disposition) return null
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      return encoded
    }
  }
  const quoted = disposition.match(/filename="([^"]+)"/i)?.[1]
  if (quoted) return quoted
  return disposition.match(/filename=([^;]+)/i)?.[1]?.trim() || null
}
