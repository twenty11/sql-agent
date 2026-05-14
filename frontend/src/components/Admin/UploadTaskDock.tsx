import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { TablesAPI } from '../../services/admin'
import { colors, radii, shadows } from '../../styles/tokens'
import type { UploadBatchDetail, UploadBatchItem, UploadBatchStatus } from '../../types/admin'
import { useAuth } from '../../contexts/AuthContext'
import { useUploadTasks } from '../../contexts/UploadTasksContext'

const ACTIVE_STATUSES = new Set<UploadBatchStatus>(['queued', 'processing'])

const batchStatusLabel: Record<UploadBatchStatus, string> = {
  queued: '排队中',
  processing: '处理中',
  success: '已完成',
  partial_failed: '部分失败',
  failed: '失败',
}

const itemStatusLabel: Record<string, string> = {
  queued: '排队中',
  processing: '处理中',
  applied: '已应用',
  failed: '失败',
}

function formatTime(value: string | null) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function statusColor(status: string) {
  if (status === 'success' || status === 'applied') return colors.successColor
  if (status === 'failed' || status === 'partial_failed') return colors.errorColor
  return colors.accent
}

export function UploadTaskDock() {
  const { user, isLoggedIn } = useAuth()
  const isAdmin = isLoggedIn && !!user?.roles.includes('admin')
  const { batches, localSubmissions, refresh, dismissLocalSubmission } = useUploadTasks()
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [details, setDetails] = useState<Record<string, UploadBatchDetail>>({})

  const badgeCount = useMemo(() => {
    const batchFileCount = batches
      .filter((batch) => ACTIVE_STATUSES.has(batch.status))
      .reduce((sum, batch) => sum + batch.total_count, 0)
    const localFileCount = localSubmissions
      .filter((item) => item.status === 'submitting')
      .reduce((sum, item) => sum + item.fileNames.length, 0)
    return batchFileCount + localFileCount
  }, [batches, localSubmissions])

  const loadDetail = async (batchId: string) => {
    const detail = await TablesAPI.uploadBatchDetail(batchId)
    setDetails((prev) => ({ ...prev, [batchId]: detail }))
  }

  const toggleBatch = (batchId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(batchId)) {
        next.delete(batchId)
      } else {
        next.add(batchId)
        loadDetail(batchId).catch(() => {})
      }
      return next
    })
  }

  useEffect(() => {
    if (!open) return
    refresh().catch(() => {})
  }, [open, refresh])

  useEffect(() => {
    if (!open || expanded.size === 0) return
    const timer = window.setInterval(() => {
      refresh().catch(() => {})
      expanded.forEach((id) => loadDetail(id).catch(() => {}))
    }, 3000)
    return () => window.clearInterval(timer)
  }, [open, expanded, refresh])

  if (!isAdmin) return null

  return (
    <div style={{ position: 'fixed', right: 24, bottom: 24, zIndex: 1200 }}>
      {open && (
        <div style={{
          position: 'absolute',
          bottom: '100%',
          right: 0,
          marginBottom: 10,
          width: 430,
          maxWidth: 'calc(100vw - 48px)',
          maxHeight: '70vh',
          overflow: 'hidden',
          background: '#fff',
          border: `1px solid ${colors.border}`,
          borderRadius: radii.md,
          boxShadow: shadows.card,
        }}>
          <div style={{
            padding: '12px 14px',
            borderBottom: `1px solid ${colors.borderLight}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div style={{ fontWeight: 600, color: colors.textPrimary }}>上传任务</div>
          </div>

          <div style={{ maxHeight: 'calc(70vh - 49px)', overflowY: 'auto', padding: 10 }}>
            {localSubmissions.map((item) => (
              <div key={item.id} style={batchRowStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={batchTitleStyle}>{item.fileNames.length > 1 ? `${item.fileNames.length} 个文件` : item.fileNames[0]}</div>
                    <div style={batchMetaStyle}>{formatTime(item.createdAt)}</div>
                  </div>
                  <span style={{ ...statusPillStyle, color: statusColor(item.status === 'failed' ? 'failed' : 'processing') }}>
                    {item.status === 'submitting' ? '提交中' : '提交失败'}
                  </span>
                </div>
                {item.error && (
                  <div style={errorStyle}>
                    {item.error}
                    <button onClick={() => dismissLocalSubmission(item.id)} style={{ marginLeft: 8, color: colors.errorColor, fontSize: 12 }}>
                      移除
                    </button>
                  </div>
                )}
              </div>
            ))}

            {batches.length === 0 && localSubmissions.length === 0 && (
              <div style={{ padding: 28, textAlign: 'center', color: colors.textSecondary, fontSize: 13 }}>
                暂无上传任务
              </div>
            )}

            {batches.map((batch) => {
              const detail = details[batch.id]
              const items = detail?.items || []
              return (
                <div key={batch.id} style={batchRowStyle}>
                  <button onClick={() => toggleBatch(batch.id)} style={{ width: '100%', textAlign: 'left' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={batchTitleStyle}>
                          {batch.mode === 'new' ? '新建表' : '更新已有表'} · {batch.total_count} 个文件
                        </div>
                        <div style={batchMetaStyle}>
                          {batch.group_name || '未命名分组'} · {formatTime(batch.created_at)}
                        </div>
                      </div>
                      <span style={{ ...statusPillStyle, color: statusColor(batch.status) }}>
                        {batchStatusLabel[batch.status]}
                      </span>
                    </div>
                    <div style={{ marginTop: 8, height: 6, borderRadius: radii.pill, background: colors.sidebarBg, overflow: 'hidden' }}>
                      <div style={{
                        width: `${batch.total_count ? ((batch.success_count + batch.failed_count) / batch.total_count) * 100 : 0}%`,
                        height: '100%',
                        background: batch.failed_count > 0 ? colors.errorColor : colors.successColor,
                      }} />
                    </div>
                  </button>

                  {expanded.has(batch.id) && (
                    <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {items.length === 0 && (
                        <div style={{ fontSize: 12, color: colors.textSecondary }}>正在加载文件状态...</div>
                      )}
                      {items.map((item) => <UploadItemRow key={item.id} item={item} />)}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((prev) => !prev)}
        style={{
          position: 'relative',
          minWidth: 104,
          height: 38,
          padding: '0 14px',
          borderRadius: radii.sm,
          background: colors.textPrimary,
          color: '#fff',
          boxShadow: shadows.card,
          fontWeight: 600,
        }}
      >
        上传任务
        {badgeCount > 0 && (
          <span style={{
            position: 'absolute',
            top: -7,
            right: -7,
            minWidth: 20,
            height: 20,
            borderRadius: 10,
            padding: '0 6px',
            background: colors.errorColor,
            color: '#fff',
            fontSize: 12,
            lineHeight: '20px',
          }}>
            {badgeCount}
          </span>
        )}
      </button>
    </div>
  )
}

function UploadItemRow({ item }: { item: UploadBatchItem }) {
  return (
    <div style={{
      border: `1px solid ${colors.borderLight}`,
      borderRadius: radii.sm,
      padding: '7px 9px',
      background: colors.sidebarBg,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <div title={item.file_name} style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
          {item.file_name}
        </div>
        <span style={{ ...statusPillStyle, color: statusColor(item.status), flex: '0 0 auto' }}>
          {itemStatusLabel[item.status] || item.status}
        </span>
      </div>
      {item.table_id && (
        <div style={batchMetaStyle}>table_id: {item.table_id}</div>
      )}
      {item.error_message && (
        <div style={errorStyle}>{item.error_message}</div>
      )}
    </div>
  )
}

const batchRowStyle: CSSProperties = {
  border: `1px solid ${colors.borderLight}`,
  borderRadius: radii.sm,
  padding: 10,
  marginBottom: 8,
  background: '#fff',
}

const batchTitleStyle: CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: colors.textPrimary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const batchMetaStyle: CSSProperties = {
  marginTop: 2,
  fontSize: 12,
  color: colors.textSecondary,
}

const statusPillStyle: CSSProperties = {
  height: 22,
  padding: '0 8px',
  borderRadius: radii.pill,
  background: colors.sidebarBg,
  fontSize: 12,
  lineHeight: '22px',
  fontWeight: 600,
  whiteSpace: 'nowrap',
}

const errorStyle: CSSProperties = {
  marginTop: 6,
  fontSize: 12,
  color: colors.errorColor,
  lineHeight: 1.5,
  wordBreak: 'break-word',
}
