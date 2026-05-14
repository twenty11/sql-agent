import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { TablesAPI } from '../services/admin'
import type { UploadAcceptedResponse, UploadBatchStatus, UploadBatchSummary } from '../types/admin'
import { useAuth } from './AuthContext'

type LocalUploadStatus = 'submitting' | 'failed'

export interface LocalUploadSubmission {
  id: string
  fileNames: string[]
  status: LocalUploadStatus
  error: string | null
  createdAt: string
}

interface StartUploadInput {
  files: File[]
  groupId: string
  targetTableId?: string
  targetTableIds?: string[]
}

interface UploadTasksContextValue {
  batches: UploadBatchSummary[]
  localSubmissions: LocalUploadSubmission[]
  loading: boolean
  startUpload: (input: StartUploadInput) => void
  refresh: () => Promise<void>
  dismissLocalSubmission: (id: string) => void
}

const ACTIVE_BATCH_STATUSES = new Set<UploadBatchStatus>(['queued', 'processing'])
const TERMINAL_BATCH_STATUSES = new Set<UploadBatchStatus>(['success', 'partial_failed', 'failed'])

const UploadTasksContext = createContext<UploadTasksContextValue | null>(null)

export function UploadTasksProvider({ children }: { children: React.ReactNode }) {
  const { user, isLoggedIn } = useAuth()
  const isAdmin = isLoggedIn && !!user?.roles.includes('admin')
  const [batches, setBatches] = useState<UploadBatchSummary[]>([])
  const [localSubmissions, setLocalSubmissions] = useState<LocalUploadSubmission[]>([])
  const [loading, setLoading] = useState(false)
  const previousStatuses = useRef<Map<string, UploadBatchStatus>>(new Map())
  const notifiedTerminalIds = useRef<Set<string>>(new Set())
  const initialized = useRef(false)

  const refresh = useCallback(async () => {
    if (!isAdmin) {
      setBatches([])
      return
    }
    setLoading(true)
    try {
      const next = await TablesAPI.uploadBatches(50)
      const previous = previousStatuses.current
      const completed = next.some((batch) => {
        const oldStatus = previous.get(batch.id)
        return initialized.current &&
          TERMINAL_BATCH_STATUSES.has(batch.status) &&
          !notifiedTerminalIds.current.has(batch.id) &&
          (!oldStatus || ACTIVE_BATCH_STATUSES.has(oldStatus))
      })
      next.forEach((batch) => {
        if (TERMINAL_BATCH_STATUSES.has(batch.status)) notifiedTerminalIds.current.add(batch.id)
      })
      initialized.current = true
      previousStatuses.current = new Map(next.map((batch) => [batch.id, batch.status]))
      setBatches(next)
      if (completed) window.dispatchEvent(new Event('upload-batches-updated'))
    } finally {
      setLoading(false)
    }
  }, [isAdmin])

  useEffect(() => {
    refresh().catch(() => {})
  }, [refresh])

  useEffect(() => {
    if (!isAdmin) return
    const hasActive = batches.some((batch) => ACTIVE_BATCH_STATUSES.has(batch.status)) ||
      localSubmissions.some((item) => item.status === 'submitting')
    if (!hasActive) return
    const timer = window.setInterval(() => {
      refresh().catch(() => {})
    }, 3000)
    return () => window.clearInterval(timer)
  }, [batches, localSubmissions, isAdmin, refresh])

  const startUpload = useCallback((input: StartUploadInput) => {
    const localId = `local-${Date.now()}-${Math.random().toString(16).slice(2)}`
    setLocalSubmissions((prev) => [
      {
        id: localId,
        fileNames: input.files.map((file) => file.name),
        status: 'submitting',
        error: null,
        createdAt: new Date().toISOString(),
      },
      ...prev,
    ])

    TablesAPI.upload(input.files, input.groupId, input.targetTableIds ?? input.targetTableId)
      .then((_res: UploadAcceptedResponse) => {
        setLocalSubmissions((prev) => prev.filter((item) => item.id !== localId))
        return refresh()
      })
      .catch((e: any) => {
        setLocalSubmissions((prev) => prev.map((item) => (
          item.id === localId
            ? { ...item, status: 'failed', error: e?.response?.data?.detail || '上传任务提交失败' }
            : item
        )))
      })
  }, [refresh])

  const dismissLocalSubmission = useCallback((id: string) => {
    setLocalSubmissions((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const value = useMemo<UploadTasksContextValue>(() => ({
    batches,
    localSubmissions,
    loading,
    startUpload,
    refresh,
    dismissLocalSubmission,
  }), [batches, localSubmissions, loading, startUpload, refresh, dismissLocalSubmission])

  return <UploadTasksContext.Provider value={value}>{children}</UploadTasksContext.Provider>
}

export function useUploadTasks(): UploadTasksContextValue {
  const ctx = useContext(UploadTasksContext)
  if (!ctx) throw new Error('useUploadTasks must be used within UploadTasksProvider')
  return ctx
}
