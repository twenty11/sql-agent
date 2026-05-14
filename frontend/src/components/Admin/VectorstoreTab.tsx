import React, { useEffect, useState, useCallback } from 'react'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { StatusDot } from './shared'
import { VectorstoreAPI } from '../../services/admin'
import type { VectorSyncLogEntry } from '../../types/admin'

const STATUS_LABEL: Record<string, string> = {
  pending: '待同步',
  success: '成功',
  pending_retry: '待重试',
  failed: '失败',
}

const STATUS_COLOR: Record<string, string> = {
  pending: '#f59e0b',
  success: '#22c55e',
  pending_retry: '#f97316',
  failed: '#e57575',
}

export function VectorstoreTab() {
  const [status, setStatus] = useState<{ table_count: number; ready: boolean } | null>(null)
  const [syncLog, setSyncLog] = useState<VectorSyncLogEntry[]>([])
  const [opStatus, setOpStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const pendingRetryCount = syncLog.filter(e => e.status === 'pending_retry' || e.status === 'failed').length

  const load = useCallback(async () => {
    try {
      const [s, logs] = await Promise.all([
        VectorstoreAPI.status(),
        VectorstoreAPI.syncLog(50),
      ])
      setStatus(s)
      setSyncLog(logs)
    } catch {
      // silently ignore if milvus is not available
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSync = async () => {
    if (!window.confirm('将把所有待同步（待同步/待重试）的记录推送到 Milvus，确定继续？')) return
    setLoading(true)
    setOpStatus('同步中...')
    try {
      const r = await VectorstoreAPI.sync()
      setOpStatus(r.message || '增量同步已完成')
      await load()
    } catch {
      setOpStatus('同步失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRetry = async () => {
    if (!window.confirm('将重置所有失败记录并重新同步，确定继续？')) return
    setLoading(true)
    setOpStatus('重试失败项...')
    try {
      const r = await VectorstoreAPI.retry()
      setOpStatus(r.message || '重试完成')
      await load()
    } catch {
      setOpStatus('重试失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRebuild = async () => {
    if (!window.confirm('全量重建将清空并重新构建整个向量库，可能需要数分钟，确定继续？')) return
    setLoading(true)
    setOpStatus('全量重建中...')
    try {
      const r = await VectorstoreAPI.rebuild()
      setOpStatus(r.message || '全量重建已完成')
      await load()
    } catch {
      setOpStatus('全量重建失败')
    } finally {
      setLoading(false)
    }
  }

  const isReady = status?.ready ?? false

  return (
    <div style={{ maxWidth: 720 }}>
      {/* Status card */}
      <div style={{
        background: '#fff',
        borderRadius: radii.xxl,
        border: `1px solid ${colors.border}`,
        padding: 24,
        marginBottom: 20,
      }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: 'rgba(0,0,0,0.9)', marginBottom: 18 }}>
          Milvus 向量库状态
        </div>

        <div style={{ display: 'flex', gap: 32, marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <StatusDot success={isReady} />
            <span style={{ fontSize: 14, fontWeight: 500, color: colors.textPrimary }}>
              {isReady ? '连接正常' : (status === null ? '未知' : '连接异常')}
            </span>
          </div>
          {status && (
            <>
              <StatItem label="表向量" value={status.table_count} />
              {pendingRetryCount > 0 && (
                <StatItem label="待重试" value={pendingRetryCount} color="#ef4444" />
              )}
            </>
          )}
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <ActionButton onClick={handleSync} disabled={loading} primary>
            增量同步
          </ActionButton>
          <ActionButton onClick={handleRetry} disabled={loading || pendingRetryCount === 0}>
            重试失败项
          </ActionButton>
          <ActionButton onClick={handleRebuild} disabled={loading}>
            全量重建
          </ActionButton>
        </div>

        {opStatus && (
          <div style={{ marginTop: 12, fontSize: 13, color: colors.textSecondary }}>
            {opStatus}
          </div>
        )}
      </div>

      {/* Sync log */}
      {syncLog.length > 0 && (
        <div style={{
          background: '#fff',
          borderRadius: radii.xxl,
          border: `1px solid ${colors.border}`,
          padding: 24,
        }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'rgba(0,0,0,0.85)', marginBottom: 14 }}>
            最近同步日志
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
              <colgroup>
                <col style={{ width: 80 }} />
                <col style={{ width: 55 }} />
                <col style={{ width: 75 }} />
                <col style={{ width: 80 }} />
                <col style={{ width: 140 }} />
                <col />
              </colgroup>
              <thead>
                <tr>
                  {['ID', '操作', '状态', '重试次数', '更新时间', '错误信息'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '6px 10px',
                      borderBottom: `1px solid ${colors.border}`,
                      color: colors.textSecondary, fontWeight: 500,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {syncLog.map(entry => (
                  <tr key={entry.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                    <td style={{ padding: '7px 10px', color: colors.textSecondary, fontFamily: 'monospace', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {entry.id}
                    </td>
                    <td style={{ padding: '7px 10px', color: colors.textSecondary }}>
                      {entry.op === 'upsert' ? '写入' : '删除'}
                    </td>
                    <td style={{ padding: '7px 10px' }}>
                      <span style={{
                        fontSize: 11, padding: '2px 6px', borderRadius: 4,
                        background: (STATUS_COLOR[entry.status] || '#aaa') + '20',
                        color: STATUS_COLOR[entry.status] || '#aaa',
                        fontWeight: 500,
                      }}>
                        {STATUS_LABEL[entry.status] || entry.status}
                      </span>
                    </td>
                    <td style={{ padding: '7px 10px', color: colors.textSecondary, textAlign: 'center' }}>
                      {entry.attempts}
                    </td>
                    <td style={{ padding: '7px 10px', color: colors.textSecondary, whiteSpace: 'nowrap' }}>
                      {new Date(entry.updated_at).toLocaleString('zh-CN', { hour12: false })}
                    </td>
                    <td style={{ padding: '7px 10px', color: '#e57575', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {entry.last_error || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function StatItem({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || colors.textPrimary, lineHeight: 1.2 }}>
        {value}
      </div>
      <div style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
        {label}
      </div>
    </div>
  )
}

function ActionButton({ children, onClick, disabled, primary }: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  primary?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: primary ? colors.accent : '#fff',
        color: primary ? '#fff' : colors.textPrimary,
        border: `1px solid ${primary ? colors.accent : colors.border}`,
        borderRadius: radii.sm,
        padding: '7px 18px',
        fontSize: 14,
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {children}
    </button>
  )
}
