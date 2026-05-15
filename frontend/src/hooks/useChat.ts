import { useState, useCallback, useRef, useMemo, useEffect } from 'react'
import type {
  Message,
  MessageStatus,
  Session,
  QueryResult,
  MessageOut,
  TableGroup,
  QuickQuestion,
  QuickQuestionInput,
} from '../types/chat'
import { chatService } from '../services/chat'

const DEFAULT_TITLE = '新对话'

type StreamHandle = {
  runId: string
  aiMsgId: string
  es: EventSource
  isFirstTurn?: boolean
}

type StreamingState = {
  runId: string
  aiMsgId: string
}

function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

function normalizeStatus(value: unknown): MessageStatus | undefined {
  return value === 'streaming' || value === 'completed' || value === 'stopped' || value === 'failed'
    ? value
    : undefined
}

export function serverMsgToLocal(m: MessageOut): Message {
  const serverStatus = normalizeStatus(m.metadata?.status)
  const isEmptyAssistant = m.role === 'assistant' && (!m.content || !m.content.trim())
  const status = serverStatus ?? (m.role === 'assistant' ? (isEmptyAssistant ? 'streaming' : 'completed') : undefined)
  return {
    id: m.id,
    role: m.role === 'assistant' ? 'ai' : 'user',
    content: m.content,
    sql: m.metadata?.sql ?? undefined,
    explanation: m.metadata?.explanation ?? undefined,
    result: m.metadata?.result ?? undefined,
    queryResultId: m.metadata?.query_result_id ?? undefined,
    status,
    runId: m.metadata?.run_id ?? undefined,
    lastEventId: m.metadata?.last_event_id ?? undefined,
    error: m.metadata?.error ?? undefined,
    thinking: m.role === 'assistant' && status === 'streaming' && isEmptyAssistant,
    createdAt: new Date(m.created_at).getTime(),
  }
}

export function applyStreamEventToMessage(message: Message, data: any, eventId?: string): Message {
  const withEventId = eventId ? { ...message, lastEventId: eventId } : message
  if (data.type === 'answer_chunk') {
    return {
      ...withEventId,
      content: withEventId.content + (data.content || ''),
      thinking: false,
      status: 'streaming',
    }
  }
  if (data.type === 'explanation') {
    return { ...withEventId, explanation: data.content }
  }
  if (data.type === 'result') {
    return {
      ...withEventId,
      result: data.data as QueryResult,
      queryResultId: data.data?.query_result_id || withEventId.queryResultId,
    }
  }
  if (data.type === 'done') {
    const state = data.state || {}
    return {
      ...withEventId,
      sql: state.generated_sql || withEventId.sql,
      queryResultId: state.query_result_id || withEventId.queryResultId,
      thinking: false,
      status: 'completed',
    }
  }
  if (data.type === 'stopped') {
    return {
      ...withEventId,
      sql: data.state?.generated_sql || withEventId.sql,
      thinking: false,
      status: 'stopped',
    }
  }
  if (data.type === 'error') {
    const error = data.content || 'Query failed.'
    return {
      ...withEventId,
      content: withEventId.content || error,
      error,
      thinking: false,
      status: 'failed',
    }
  }
  return withEventId
}

function sortQuickQuestions(items: QuickQuestion[]) {
  return [...items].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
    if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })
}

function sortSessions(items: Session[]) {
  return [...items].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
}

export function useChat() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messagesBySession, setMessagesBySession] = useState<Record<string, Message[]>>({})
  const [temporaryMessages, setTemporaryMessages] = useState<Message[]>([])
  const [streamingBySession, setStreamingBySession] = useState<Record<string, StreamingState>>({})
  const [isTemporarySession, setIsTemporarySession] = useState(false)
  const [tableGroups, setTableGroups] = useState<TableGroup[]>([])
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
  const [tableGroupsLoading, setTableGroupsLoading] = useState(false)
  const [quickQuestions, setQuickQuestions] = useState<QuickQuestion[]>([])
  const [quickQuestionsLoading, setQuickQuestionsLoading] = useState(false)
  const [inputValue, setInputValue] = useState('')

  const streamsRef = useRef<Record<string, StreamHandle>>({})
  const activeSessionIdRef = useRef<string | null>(null)
  const selectSeqRef = useRef(0)
  const sessionsRef = useRef<Session[]>([])
  const reloadSessionRef = useRef<(sessionId: string) => void>(() => {})

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId
  }, [activeSessionId])

  useEffect(() => {
    sessionsRef.current = sessions
  }, [sessions])

  useEffect(() => {
    return () => {
      Object.values(streamsRef.current).forEach((stream) => stream.es.close())
      streamsRef.current = {}
    }
  }, [])

  const messages = useMemo(
    () => (activeSessionId ? messagesBySession[activeSessionId] ?? [] : temporaryMessages),
    [activeSessionId, messagesBySession, temporaryMessages]
  )
  const isStreaming = activeSessionId ? !!streamingBySession[activeSessionId] : false

  const setActiveSession = useCallback((id: string | null) => {
    activeSessionIdRef.current = id
    setActiveSessionId(id)
    if (id) localStorage.setItem('activeSessionId', id)
    else localStorage.removeItem('activeSessionId')
  }, [])

  const setSessionMessages = useCallback((
    sessionId: string,
    updater: Message[] | ((prev: Message[]) => Message[])
  ) => {
    setMessagesBySession((prev) => {
      const current = prev[sessionId] ?? []
      const next = typeof updater === 'function' ? updater(current) : updater
      return { ...prev, [sessionId]: next }
    })
  }, [])

  const updateSessionMessage = useCallback((
    sessionId: string,
    messageId: string,
    updater: (message: Message) => Message
  ) => {
    setSessionMessages(sessionId, (prev) =>
      prev.map((message) => (message.id === messageId ? updater(message) : message))
    )
  }, [setSessionMessages])

  const touchSession = useCallback((sessionId: string, patch?: Partial<Session>) => {
    setSessions((prev) =>
      sortSessions(prev.map((s) =>
        s.id === sessionId
          ? { ...s, ...patch, updated_at: patch?.updated_at ?? new Date().toISOString() }
          : s
      ))
    )
  }, [])

  const cleanupStream = useCallback((sessionId: string, runId: string, closeStream = true) => {
    const current = streamsRef.current[sessionId]
    if (!current || current.runId !== runId) return
    if (closeStream) current.es.close()
    delete streamsRef.current[sessionId]
    setStreamingBySession((prev) => {
      if (prev[sessionId]?.runId !== runId) return prev
      const next = { ...prev }
      delete next[sessionId]
      return next
    })
  }, [])

  const maybeGenerateTitle = useCallback((sessionId: string, localMsgs: Message[]) => {
    const session = sessionsRef.current.find((s) => s.id === sessionId)
    if (session?.title !== DEFAULT_TITLE) return
    const hasUser = localMsgs.some((m) => m.role === 'user')
    const hasCompletedAi = localMsgs.some((m) => m.role === 'ai' && m.status !== 'streaming')
    if (!hasUser || !hasCompletedAi) return
    chatService.generateSessionTitle(sessionId).then((res) => {
      touchSession(sessionId, { title: res.title })
    }).catch(() => {})
  }, [touchSession])

  const attachStream = useCallback((
    sessionId: string,
    aiMsgId: string,
    runId: string,
    es: EventSource,
    isFirstTurn = false
  ) => {
    const existing = streamsRef.current[sessionId]
    if (existing && existing.runId !== runId) existing.es.close()
    streamsRef.current[sessionId] = { runId, aiMsgId, es, isFirstTurn }
    setStreamingBySession((prev) => ({ ...prev, [sessionId]: { runId, aiMsgId } }))

    const updateAi = (updater: (m: Message) => Message) => {
      updateSessionMessage(sessionId, aiMsgId, updater)
    }

    es.onmessage = (event) => {
      const activeStream = streamsRef.current[sessionId]
      if (!activeStream || activeStream.runId !== runId) return
      try {
        const data = JSON.parse(event.data)
        updateAi((m) => applyStreamEventToMessage(m, data, event.lastEventId || undefined))
        if (data.type === 'done' || data.type === 'stopped' || data.type === 'error') {
          cleanupStream(sessionId, runId)
          touchSession(sessionId)
          if (data.type === 'done' && activeStream.isFirstTurn) {
            chatService.generateSessionTitle(sessionId).then((res) => {
              touchSession(sessionId, { title: res.title })
            }).catch(() => {})
          }
        }
      } catch {
        // ignore malformed SSE payloads
      }
    }

    es.onerror = () => {
      const activeStream = streamsRef.current[sessionId]
      if (!activeStream || activeStream.runId !== runId) return
      cleanupStream(sessionId, runId)
      setTimeout(() => reloadSessionRef.current(sessionId), 1000)
    }
  }, [cleanupStream, touchSession, updateSessionMessage])

  const resumePendingStream = useCallback((sessionId: string, localMsgs: Message[]) => {
    const last = localMsgs[localMsgs.length - 1]
    if (!last || last.role !== 'ai' || last.status !== 'streaming' || !last.runId) return
    if (streamsRef.current[sessionId]?.runId === last.runId) return
    const es = chatService.createResumeStream(last.runId, last.lastEventId)
    attachStream(sessionId, last.id, last.runId, es)
  }, [attachStream])

  const loadSessionMessages = useCallback(async (sessionId: string) => {
    const remoteMsgs = await chatService.listMessages(sessionId)
    const localMsgs = remoteMsgs.map(serverMsgToLocal)
    if (!streamsRef.current[sessionId]) {
      setSessionMessages(sessionId, localMsgs)
    }
    resumePendingStream(sessionId, localMsgs)
    maybeGenerateTitle(sessionId, localMsgs)
    return localMsgs
  }, [maybeGenerateTitle, resumePendingStream, setSessionMessages])

  useEffect(() => {
    reloadSessionRef.current = (sessionId: string) => {
      loadSessionMessages(sessionId).catch(() => {
        setSessionMessages(sessionId, (prev) =>
          prev.map((message, index) =>
            index === prev.length - 1 && message.role === 'ai' && message.status === 'streaming'
              ? { ...message, thinking: false, status: 'failed', error: 'Stream reconnect failed.', content: message.content || 'Stream reconnect failed.' }
              : message
          )
        )
      })
    }
  }, [loadSessionMessages, setSessionMessages])

  const loadTableGroups = useCallback(async () => {
    setTableGroupsLoading(true)
    try {
      const groups = await chatService.fetchUserTableGroups()
      setTableGroups(groups)
      if (groups.length > 0) {
        const savedId = localStorage.getItem('selectedGroupId')
        const validSaved = savedId && groups.some((g) => g.id === savedId)
        if (validSaved) {
          setSelectedGroupId(savedId!)
        } else {
          if (savedId) localStorage.removeItem('selectedGroupId')
          setSelectedGroupId(groups[0].id)
        }
      } else {
        localStorage.removeItem('selectedGroupId')
        setSelectedGroupId(null)
      }
    } catch {
      setTableGroups([])
      setSelectedGroupId(null)
    } finally {
      setTableGroupsLoading(false)
    }
  }, [])

  const loadQuickQuestions = useCallback(async () => {
    setQuickQuestionsLoading(true)
    try {
      const items = await chatService.listQuickQuestions()
      setQuickQuestions(items)
      return items
    } catch {
      setQuickQuestions([])
      return []
    } finally {
      setQuickQuestionsLoading(false)
    }
  }, [])

  const loadSessions = useCallback(async () => {
    loadTableGroups()
    loadQuickQuestions()
    const list = await chatService.listSessions()
    const sorted = sortSessions(list)
    setSessions(sorted)
    sessionsRef.current = sorted

    const savedId = localStorage.getItem('activeSessionId')
    if (savedId && sorted.some((s) => s.id === savedId)) {
      setActiveSession(savedId)
      try {
        await loadSessionMessages(savedId)
      } catch {
        setSessionMessages(savedId, [])
      }
    } else if (savedId) {
      localStorage.removeItem('activeSessionId')
    }

    return sorted
  }, [loadSessionMessages, loadTableGroups, loadQuickQuestions, setActiveSession, setSessionMessages])

  const createSession = useCallback(async () => {
    setIsTemporarySession(true)
    setTemporaryMessages([])
    setActiveSession(null)
    return null
  }, [setActiveSession])

  const selectSession = useCallback(async (id: string) => {
    const seq = ++selectSeqRef.current
    setIsTemporarySession(false)
    setActiveSession(id)
    if (streamsRef.current[id]) return

    try {
      const localMsgs = await loadSessionMessages(id)
      if (seq !== selectSeqRef.current || activeSessionIdRef.current !== id) return
      setSessionMessages(id, localMsgs)
    } catch {
      if (seq === selectSeqRef.current && activeSessionIdRef.current === id && !streamsRef.current[id]) {
        setSessionMessages(id, [])
      }
    }
  }, [loadSessionMessages, setActiveSession, setSessionMessages])

  const sendMessage = useCallback(
    async (rawQuestion: string): Promise<boolean> => {
      const question = rawQuestion.trim()
      if (!question) return false

      let sessionId = activeSessionIdRef.current
      const isFirstTurn = !sessionId
      if (sessionId && streamsRef.current[sessionId]) return false

      try {
        if (!sessionId) {
          const s = await chatService.createSession(DEFAULT_TITLE)
          setSessions((prev) => sortSessions([s, ...prev]))
          sessionsRef.current = sortSessions([s, ...sessionsRef.current])
          setIsTemporarySession(false)
          setActiveSession(s.id)
          sessionId = s.id
        }

        if (streamsRef.current[sessionId]) return false

        const runId = generateId()
        const aiMsgId = generateId()
        const userMsg: Message = {
          id: generateId(),
          role: 'user',
          content: question,
          createdAt: Date.now(),
        }
        const aiMsg: Message = {
          id: aiMsgId,
          role: 'ai',
          content: '',
          thinking: true,
          status: 'streaming',
          runId,
          lastEventId: '0-0',
          createdAt: Date.now() + 1,
        }

        const es = chatService.createQueryStream(question, sessionId, selectedGroupId, runId)
        attachStream(sessionId, aiMsgId, runId, es, isFirstTurn)
        setSessionMessages(sessionId, (prev) => [...prev, userMsg, aiMsg])
        touchSession(sessionId)
        return true
      } catch {
        return false
      }
    },
    [attachStream, selectedGroupId, setActiveSession, setSessionMessages, touchSession]
  )

  const stopStreaming = useCallback(() => {
    const sessionId = activeSessionIdRef.current
    if (!sessionId) return
    const stream = streamsRef.current[sessionId]
    if (!stream) return
    chatService.cancelQuery(stream.runId).catch(() => {})
    updateSessionMessage(sessionId, stream.aiMsgId, (m) => ({
      ...m,
      thinking: false,
      status: 'stopped',
    }))
    cleanupStream(sessionId, stream.runId)
  }, [cleanupStream, updateSessionMessage])

  const renameSession = useCallback(async (id: string, title: string) => {
    await chatService.renameSession(id, title)
    touchSession(id, { title })
  }, [touchSession])

  const cancelStreamForSession = useCallback((id: string) => {
    const stream = streamsRef.current[id]
    if (!stream) return
    chatService.cancelQuery(stream.runId).catch(() => {})
    cleanupStream(id, stream.runId)
  }, [cleanupStream])

  const deleteSession = useCallback(async (id: string) => {
    cancelStreamForSession(id)
    await chatService.deleteSession(id)
    setSessions((prev) => prev.filter((s) => s.id !== id))
    setMessagesBySession((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    if (activeSessionIdRef.current === id) {
      setActiveSession(null)
      setTemporaryMessages([])
    }
  }, [cancelStreamForSession, setActiveSession])

  const deleteSessions = useCallback(async (ids: string[]) => {
    ids.forEach(cancelStreamForSession)
    await Promise.all(ids.map((id) => chatService.deleteSession(id)))
    setSessions((prev) => prev.filter((s) => !ids.includes(s.id)))
    setMessagesBySession((prev) => {
      const next = { ...prev }
      ids.forEach((id) => delete next[id])
      return next
    })
    if (activeSessionIdRef.current && ids.includes(activeSessionIdRef.current)) {
      setActiveSession(null)
      setTemporaryMessages([])
    }
  }, [cancelStreamForSession, setActiveSession])

  const selectGroup = useCallback((groupId: string | null) => {
    setSelectedGroupId(groupId)
    if (groupId) {
      localStorage.setItem('selectedGroupId', groupId)
    } else {
      localStorage.removeItem('selectedGroupId')
    }
  }, [])

  const createQuickQuestion = useCallback(async (payload: QuickQuestionInput) => {
    const created = await chatService.createQuickQuestion(payload)
    setQuickQuestions((prev) => sortQuickQuestions([created, ...prev]))
    return created
  }, [])

  const updateQuickQuestion = useCallback(
    async (id: string, payload: Partial<QuickQuestionInput>) => {
      const updated = await chatService.updateQuickQuestion(id, payload)
      setQuickQuestions((prev) =>
        sortQuickQuestions(prev.map((item) => (item.id === id ? updated : item)))
      )
      return updated
    },
    []
  )

  const deleteQuickQuestion = useCallback(async (id: string) => {
    await chatService.deleteQuickQuestion(id)
    setQuickQuestions((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const reorderQuickQuestions = useCallback(async (orderedIds: string[]) => {
    const items = await chatService.reorderQuickQuestions(orderedIds)
    setQuickQuestions(items)
    return items
  }, [])

  const applyQuickQuestion = useCallback(
    (item: QuickQuestion) => {
      if (item.table_group_id && tableGroups.some((group) => group.id === item.table_group_id)) {
        selectGroup(item.table_group_id)
      }
      setInputValue(item.question_text)
      chatService.markQuickQuestionUsed(item.id)
        .then((updated) => {
          setQuickQuestions((prev) =>
            sortQuickQuestions(prev.map((q) => (q.id === item.id ? updated : q)))
          )
        })
        .catch(() => {})
    },
    [tableGroups, selectGroup]
  )

  return {
    sessions,
    activeSessionId,
    messages,
    isStreaming,
    isTemporarySession,
    tableGroups,
    selectedGroupId,
    setSelectedGroupId,
    tableGroupsLoading,
    quickQuestions,
    quickQuestionsLoading,
    inputValue,
    setInputValue,
    loadSessions,
    loadQuickQuestions,
    createSession,
    selectSession,
    sendMessage,
    stopStreaming,
    renameSession,
    deleteSession,
    deleteSessions,
    selectGroup,
    createQuickQuestion,
    updateQuickQuestion,
    deleteQuickQuestion,
    reorderQuickQuestions,
    applyQuickQuestion,
  }
}
