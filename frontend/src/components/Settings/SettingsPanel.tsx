import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../../services/api'
import type { QuickQuestion, QuickQuestionInput, TableGroup } from '../../types/chat'
import { colors, radii, fontFamily, shadows } from '../../styles/tokens'
import { ChevronDownIcon, CloseIcon, PlusIcon, TrashIcon } from '../Icons'
import { ConfirmDialog } from '../ui/ConfirmDialog'

interface SettingsPanelProps {
  open: boolean
  onClose: () => void
  tableGroups: TableGroup[]
  quickQuestions: QuickQuestion[]
  quickQuestionsLoading: boolean
  onCreateQuickQuestion: (payload: QuickQuestionInput) => Promise<QuickQuestion>
  onUpdateQuickQuestion: (id: string, payload: Partial<QuickQuestionInput>) => Promise<QuickQuestion>
  onDeleteQuickQuestion: (id: string) => Promise<void>
  onReorderQuickQuestions: (orderedIds: string[]) => Promise<QuickQuestion[]>
}

type Status = {
  type: 'success' | 'error'
  text: string
} | null

type SettingsTab = 'password' | 'quickQuestions'

type QuickQuestionDraft = {
  display_name: string
  question_text: string
  table_group_id: string
  is_pinned: boolean
}

const navItems: Array<{ key: SettingsTab; label: string }> = [
  { key: 'password', label: '修改密码' },
  { key: 'quickQuestions', label: '快捷问题' },
]

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  border: `1px solid ${colors.borderInput}`,
  borderRadius: radii.sm,
  color: colors.textPrimary,
  background: colors.inputBg,
  fontSize: 14,
  fontFamily,
  boxSizing: 'border-box',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: 6,
  color: colors.textSecondary,
  fontSize: 13,
  fontWeight: 500,
}

const smallButtonStyle: React.CSSProperties = {
  height: 30,
  padding: '0 10px',
  border: `1px solid ${colors.borderStrong}`,
  borderRadius: radii.sm,
  background: colors.pageBg,
  color: colors.textSecondary,
  fontSize: 13,
  fontFamily,
  cursor: 'pointer',
}

function displayLabel(item: QuickQuestion) {
  const label = item.display_name?.trim() || item.question_text.trim()
  return label.length > 18 ? `${label.slice(0, 18)}...` : label
}

function normalizeDraft(draft: QuickQuestionDraft): QuickQuestionInput | null {
  const question = draft.question_text.trim()
  if (!question) return null
  if (!draft.table_group_id) return null
  return {
    display_name: draft.display_name.trim() || null,
    question_text: question,
    table_group_id: draft.table_group_id,
    is_pinned: draft.is_pinned,
  }
}

function SettingRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 0',
        borderBottom: `1px solid ${colors.borderLight}`,
      }}
    >
      <span style={{ fontSize: 14, color: colors.textPrimary }}>{label}</span>
      {children}
    </div>
  )
}

function PasswordSettings() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [status, setStatus] = useState<Status>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setStatus(null)

    if (!oldPassword || !newPassword || !confirmPassword) {
      setStatus({ type: 'error', text: '请完整填写密码' })
      return
    }

    if (newPassword !== confirmPassword) {
      setStatus({ type: 'error', text: '两次输入的新密码不一致' })
      return
    }

    try {
      setSubmitting(true)
      await api.post('/profile/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setStatus({ type: 'success', text: '密码修改成功' })
    } catch {
      setStatus({ type: 'error', text: '密码修改失败，请检查旧密码' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <h2 style={{ margin: '0 0 4px', color: colors.textPrimary, fontSize: 18, fontWeight: 600 }}>
        修改密码
      </h2>
      <p style={{ margin: '0 0 20px', color: colors.textMuted, fontSize: 13 }}>
        更新账户的登录密码。
      </p>

      <form onSubmit={handleSubmit}>
        <div style={{ borderTop: `1px solid ${colors.borderLight}` }}>
          <SettingRow label="旧密码">
            <input
              id="old-password"
              type="password"
              value={oldPassword}
              onChange={(event) => setOldPassword(event.target.value)}
              style={{ ...inputStyle, width: 220 }}
              autoComplete="current-password"
            />
          </SettingRow>
          <SettingRow label="新密码">
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              style={{ ...inputStyle, width: 220 }}
              autoComplete="new-password"
            />
          </SettingRow>
          <SettingRow label="确认新密码">
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              style={{ ...inputStyle, width: 220 }}
              autoComplete="new-password"
            />
          </SettingRow>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 20 }}>
          <button
            type="submit"
            disabled={submitting}
            style={{
              padding: '9px 22px',
              borderRadius: radii.sm,
              border: 'none',
              background: submitting ? colors.borderStrong : colors.accent,
              color: colors.textWhite,
              fontSize: 14,
              fontWeight: 500,
              fontFamily,
              cursor: submitting ? 'default' : 'pointer',
            }}
            onMouseEnter={(event) => {
              if (!submitting) event.currentTarget.style.background = colors.accentHover
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.background = submitting ? colors.borderStrong : colors.accent
            }}
          >
            {submitting ? '更新中...' : '更新密码'}
          </button>

          {status && (
            <span
              style={{
                color: status.type === 'success' ? colors.successColor : colors.errorColor,
                fontSize: 13,
              }}
            >
              {status.text}
            </span>
          )}
        </div>
      </form>
    </>
  )
}

function QuickQuestionForm({
  draft,
  tableGroups,
  submitText,
  submitting,
  error,
  onChange,
  onSubmit,
  onCancel,
}: {
  draft: QuickQuestionDraft
  tableGroups: TableGroup[]
  submitText: string
  submitting: boolean
  error: string
  onChange: (draft: QuickQuestionDraft) => void
  onSubmit: () => void
  onCancel: () => void
}) {
  return (
    <div
      style={{
        border: `1px solid ${colors.borderLight}`,
        borderRadius: radii.lg,
        padding: 14,
        background: '#fbfaf9',
      }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 160px', gap: 12, marginBottom: 12 }}>
        <label>
          <span style={labelStyle}>显示名称（可选）</span>
          <input
            value={draft.display_name}
            onChange={(event) => onChange({ ...draft, display_name: event.target.value })}
            maxLength={100}
            style={inputStyle}
            placeholder="例如：昨日新增用户"
          />
        </label>
        <label>
          <span style={labelStyle}>表分组</span>
          <select
            value={draft.table_group_id}
            onChange={(event) => onChange({ ...draft, table_group_id: event.target.value })}
            style={inputStyle}
          >
            <option value="" disabled>请选择表分组</option>
            {tableGroups.map((group) => (
              <option key={group.id} value={group.id}>{group.name}</option>
            ))}
          </select>
        </label>
      </div>

      <label>
        <span style={labelStyle}>问题文本</span>
        <textarea
          value={draft.question_text}
          onChange={(event) => onChange({ ...draft, question_text: event.target.value })}
          rows={3}
          style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.5 }}
          placeholder="输入要反复使用的自然语言问题"
        />
      </label>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, gap: 12 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: colors.textSecondary, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={draft.is_pinned}
            onChange={(event) => onChange({ ...draft, is_pinned: event.target.checked })}
          />
          显示在输入框上方
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: colors.errorColor, fontSize: 13 }}>{error}</span>
          <button type="button" onClick={onCancel} style={smallButtonStyle}>取消</button>
          <button
            type="button"
            disabled={submitting}
            onClick={onSubmit}
            style={{
              ...smallButtonStyle,
              border: 'none',
              background: submitting ? colors.borderStrong : colors.accent,
              color: colors.textWhite,
              cursor: submitting ? 'default' : 'pointer',
            }}
          >
            {submitting ? '保存中...' : submitText}
          </button>
        </div>
      </div>
    </div>
  )
}

function QuickQuestionSettings({
  tableGroups,
  quickQuestions,
  quickQuestionsLoading,
  onCreateQuickQuestion,
  onUpdateQuickQuestion,
  onDeleteQuickQuestion,
  onReorderQuickQuestions,
}: Omit<SettingsPanelProps, 'open' | 'onClose'>) {
  const groupById = useMemo(() => new Map(tableGroups.map((group) => [group.id, group])), [tableGroups])
  const defaultGroupId = tableGroups[0]?.id ?? ''
  const [selectedGroupId, setSelectedGroupId] = useState<string>('all')
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<QuickQuestionDraft>({
    display_name: '',
    question_text: '',
    table_group_id: defaultGroupId,
    is_pinned: true,
  })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<QuickQuestion | null>(null)

  const filteredQuestions = useMemo(
    () =>
      selectedGroupId === 'all'
        ? quickQuestions
        : quickQuestions.filter((q) => q.table_group_id === selectedGroupId),
    [quickQuestions, selectedGroupId],
  )

  const resetDraft = () => {
    setDraft({ display_name: '', question_text: '', table_group_id: defaultGroupId, is_pinned: true })
    setError('')
    setSubmitting(false)
  }

  const beginEdit = (item: QuickQuestion) => {
    setAdding(false)
    setEditingId(item.id)
    setDraft({
      display_name: item.display_name ?? '',
      question_text: item.question_text,
      table_group_id: item.table_group_id,
      is_pinned: item.is_pinned,
    })
    setError('')
  }

  const cancelForm = () => {
    setAdding(false)
    setEditingId(null)
    resetDraft()
  }

  const submitCreate = async () => {
    const payload = normalizeDraft(draft)
    if (!draft.question_text.trim()) {
      setError('问题文本不能为空')
      return
    }
    if (!draft.table_group_id) {
      setError('请选择表分组')
      return
    }
    if (!payload) return
    try {
      setSubmitting(true)
      await onCreateQuickQuestion(payload)
      cancelForm()
    } catch {
      setError('保存失败')
      setSubmitting(false)
    }
  }

  const submitUpdate = async () => {
    if (!editingId) return
    const payload = normalizeDraft(draft)
    if (!draft.question_text.trim()) {
      setError('问题文本不能为空')
      return
    }
    if (!draft.table_group_id) {
      setError('请选择表分组')
      return
    }
    if (!payload) return
    try {
      setSubmitting(true)
      await onUpdateQuickQuestion(editingId, payload)
      cancelForm()
    } catch {
      setError('保存失败')
      setSubmitting(false)
    }
  }

  const togglePinned = async (item: QuickQuestion) => {
    await onUpdateQuickQuestion(item.id, { is_pinned: !item.is_pinned })
  }

  const moveItem = async (item: QuickQuestion, direction: -1 | 1) => {
    const index = quickQuestions.findIndex((q) => q.id === item.id)
    if (index === -1) return
    const target = index + direction
    if (target < 0 || target >= quickQuestions.length) return
    const ids = quickQuestions.map((q) => q.id)
    const current = ids[index]
    ids[index] = ids[target]
    ids[target] = current
    await onReorderQuickQuestions(ids)
  }

  const thStyle: React.CSSProperties = {
    padding: '9px 12px',
    textAlign: 'left',
    fontSize: 12,
    fontWeight: 600,
    color: colors.textSecondary,
    letterSpacing: '0.03em',
    borderBottom: `1px solid ${colors.borderLight}`,
    userSelect: 'none',
    fontFamily,
    whiteSpace: 'nowrap',
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: 0, color: colors.textPrimary, fontSize: 18, fontWeight: 600 }}>
            快捷问题
          </h2>
          <p style={{ margin: '4px 0 0', color: colors.textMuted, fontSize: 13 }}>
            管理常用自然语言查询，可绑定表分组并显示在输入框上方。
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setAdding(true)
            setEditingId(null)
            resetDraft()
          }}
          style={{
            ...smallButtonStyle,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            border: 'none',
            background: colors.accent,
            color: colors.textWhite,
            flexShrink: 0,
          }}
        >
          <PlusIcon width={14} height={14} color={colors.textWhite} />
          新增
        </button>
      </div>

      {/* Group filter tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        {(['all', ...tableGroups.map((g) => g.id)] as const).map((gid) => {
          const active = selectedGroupId === gid
          const isAll = gid === 'all'
          const label = isAll
            ? `全部 (${quickQuestions.length})`
            : tableGroups.find((g) => g.id === gid)?.name ?? gid
          return (
            <button
              key={gid}
              type="button"
              onClick={() => setSelectedGroupId(gid)}
              style={{
                height: 28,
                padding: '0 14px',
                borderRadius: radii.pill,
                border: active ? 'none' : `1px solid ${colors.borderStrong}`,
                background: active ? colors.accent : 'transparent',
                color: active ? colors.textWhite : colors.textSecondary,
                fontSize: 13,
                fontFamily,
                cursor: 'pointer',
                fontWeight: active ? 600 : 400,
              }}
            >
              {label}
            </button>
          )
        })}
      </div>

      {adding && (
        <div style={{ marginBottom: 14 }}>
          <QuickQuestionForm
            draft={draft}
            tableGroups={tableGroups}
            submitText="新增"
            submitting={submitting}
            error={error}
            onChange={setDraft}
            onSubmit={submitCreate}
            onCancel={cancelForm}
          />
        </div>
      )}

      {quickQuestionsLoading && (
        <div style={{ color: colors.textMuted, fontSize: 13, padding: '18px 0' }}>加载中...</div>
      )}

      {!quickQuestionsLoading && filteredQuestions.length === 0 && !adding && (
        <div
          style={{
            border: `1px dashed ${colors.borderStrong}`,
            borderRadius: radii.lg,
            padding: 22,
            color: colors.textMuted,
            fontSize: 14,
            textAlign: 'center',
          }}
        >
          {selectedGroupId === 'all' ? '暂无快捷问题' : '该分组暂无快捷问题'}
        </div>
      )}

      {!quickQuestionsLoading && filteredQuestions.length > 0 && (
        <div
          style={{
            border: `1px solid ${colors.borderLight}`,
            borderRadius: radii.lg,
            overflow: 'hidden',
            maxHeight: 400,
            overflowY: 'auto',
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
            <colgroup>
              <col style={{ width: 130 }} />
              <col />
              <col style={{ width: 48 }} />
              <col style={{ width: 204 }} />
            </colgroup>
            <thead>
              <tr style={{ background: colors.tableHeadBg, position: 'sticky', top: 0, zIndex: 1 }}>
                <th style={thStyle}>显示名称</th>
                <th style={thStyle}>问题文本</th>
                <th style={{ ...thStyle, textAlign: 'center' }}>置顶</th>
                <th style={thStyle}>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredQuestions.map((item) => {
                const isEditing = editingId === item.id
                const globalIndex = quickQuestions.findIndex((q) => q.id === item.id)

                if (isEditing) {
                  return (
                    <tr key={item.id} style={{ background: '#fbfaf9' }}>
                      <td
                        colSpan={4}
                        style={{ padding: 12, borderTop: `1px solid ${colors.borderLight}` }}
                      >
                        <QuickQuestionForm
                          draft={draft}
                          tableGroups={tableGroups}
                          submitText="保存"
                          submitting={submitting}
                          error={error}
                          onChange={setDraft}
                          onSubmit={submitUpdate}
                          onCancel={cancelForm}
                        />
                      </td>
                    </tr>
                  )
                }

                return (
                  <TableRow
                    key={item.id}
                    item={item}
                    globalIndex={globalIndex}
                    totalCount={quickQuestions.length}
                    onMoveUp={() => moveItem(item, -1)}
                    onMoveDown={() => moveItem(item, 1)}
                    onTogglePinned={() => togglePinned(item)}
                    onEdit={() => beginEdit(item)}
                    onDelete={() => setDeleteTarget(item)}
                  />
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="删除快捷问题"
        message={`确认删除"${deleteTarget ? displayLabel(deleteTarget) : ''}"吗？`}
        confirmText="确认删除"
        cancelText="取消"
        onConfirm={async () => {
          if (!deleteTarget) return
          await onDeleteQuickQuestion(deleteTarget.id)
          setDeleteTarget(null)
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  )
}

function TableRow({
  item,
  globalIndex,
  totalCount,
  onMoveUp,
  onMoveDown,
  onTogglePinned,
  onEdit,
  onDelete,
}: {
  item: QuickQuestion
  globalIndex: number
  totalCount: number
  onMoveUp: () => void
  onMoveDown: () => void
  onTogglePinned: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const [hovered, setHovered] = useState(false)

  const actionBtnStyle: React.CSSProperties = {
    height: 26,
    padding: '0 8px',
    border: `1px solid ${colors.borderStrong}`,
    borderRadius: radii.sm,
    background: colors.pageBg,
    color: colors.textSecondary,
    fontSize: 12,
    fontFamily,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    flexShrink: 0,
  }

  const iconBtnStyle: React.CSSProperties = {
    ...actionBtnStyle,
    width: 26,
    padding: 0,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  }

  return (
    <tr
      style={{
        borderTop: `1px solid ${colors.borderLight}`,
        background: hovered ? colors.hoverBg : 'transparent',
        transition: 'background 0.1s',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <td
        style={{
          padding: '10px 12px',
          fontSize: 14,
          color: colors.textPrimary,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={item.display_name || item.question_text}
      >
        {displayLabel(item)}
      </td>
      <td style={{ padding: '10px 12px', fontSize: 13, color: colors.textSecondary }}>
        <div
          title={item.question_text}
          style={{
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            lineHeight: 1.45,
          }}
        >
          {item.question_text}
        </div>
      </td>
      <td style={{ padding: '10px 12px', textAlign: 'center' }}>
        {item.is_pinned && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 18,
              height: 18,
              borderRadius: '50%',
              background: colors.pillBg,
              color: colors.accent,
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            ✓
          </span>
        )}
      </td>
      <td style={{ padding: '8px 12px' }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <button
            type="button"
            title="上移"
            disabled={globalIndex === 0}
            onClick={onMoveUp}
            style={{ ...iconBtnStyle, opacity: globalIndex === 0 ? 0.35 : 1 }}
          >
            <span style={{ display: 'inline-flex', transform: 'rotate(180deg)' }}>
              <ChevronDownIcon width={12} height={12} color={colors.textSecondary} />
            </span>
          </button>
          <button
            type="button"
            title="下移"
            disabled={globalIndex === totalCount - 1}
            onClick={onMoveDown}
            style={{ ...iconBtnStyle, opacity: globalIndex === totalCount - 1 ? 0.35 : 1 }}
          >
            <ChevronDownIcon width={12} height={12} color={colors.textSecondary} />
          </button>
          <button type="button" onClick={onTogglePinned} style={actionBtnStyle}>
            {item.is_pinned ? '取消' : '置顶'}
          </button>
          <button type="button" onClick={onEdit} style={actionBtnStyle}>
            编辑
          </button>
          <button
            type="button"
            title="删除"
            onClick={onDelete}
            style={{ ...iconBtnStyle, color: colors.errorColor, borderColor: 'transparent' }}
          >
            <TrashIcon width={13} height={13} color={colors.errorColor} />
          </button>
        </div>
      </td>
    </tr>
  )
}

export function SettingsPanel({
  open,
  onClose,
  tableGroups,
  quickQuestions,
  quickQuestionsLoading,
  onCreateQuickQuestion,
  onUpdateQuickQuestion,
  onDeleteQuickQuestion,
  onReorderQuickQuestions,
}: SettingsPanelProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>('password')

  useEffect(() => {
    if (!open) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  useEffect(() => {
    if (!open) setActiveTab('password')
  }, [open])

  if (!open) return null

  return (
    <div
      role="presentation"
      onMouseDown={onClose}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 300,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        background: 'rgba(0,0,0,0.18)',
        fontFamily,
      }}
    >
      <style>{`
        @keyframes settingsPanelIn {
          from { opacity: 0; transform: translateY(12px) scale(0.985); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>

      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-panel-title"
        onMouseDown={(event) => event.stopPropagation()}
        style={{
          width: 'min(900px, calc(100vw - 32px))',
          minHeight: 500,
          maxHeight: 'calc(100vh - 48px)',
          background: colors.pageBg,
          border: `1px solid ${colors.border}`,
          borderRadius: radii.xxl,
          boxShadow: shadows.card,
          overflow: 'hidden',
          animation: 'settingsPanelIn 0.16s ease',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 18px 0 20px',
            borderBottom: `1px solid ${colors.borderLight}`,
            flexShrink: 0,
          }}
        >
          <h1
            id="settings-panel-title"
            style={{ margin: 0, color: colors.textPrimary, fontSize: 18, fontWeight: 600 }}
          >
            设置
          </h1>
          <button
            type="button"
            onClick={onClose}
            title="关闭"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 30,
              height: 30,
              borderRadius: radii.md,
              border: 'none',
              background: 'transparent',
              color: colors.textMuted,
              cursor: 'pointer',
            }}
            onMouseEnter={(event) => (event.currentTarget.style.background = colors.hoverBg)}
            onMouseLeave={(event) => (event.currentTarget.style.background = 'transparent')}
          >
            <CloseIcon width={15} height={15} color={colors.textMuted} />
          </button>
        </div>

        {/* Body */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          <nav
            aria-label="设置导航"
            style={{
              width: 168,
              flexShrink: 0,
              padding: '10px 8px',
              borderRight: `1px solid ${colors.borderLight}`,
              background: colors.sidebarBg,
              overflowY: 'auto',
            }}
          >
            {navItems.map((item) => {
              const active = activeTab === item.key
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setActiveTab(item.key)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '9px 12px',
                    borderRadius: radii.sm,
                    border: 'none',
                    background: active ? 'rgba(0,117,222,0.08)' : 'transparent',
                    color: active ? colors.accent : colors.textSecondary,
                    fontSize: 14,
                    fontWeight: active ? 600 : 500,
                    fontFamily,
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(event) => {
                    if (!active) event.currentTarget.style.background = colors.hoverBg
                  }}
                  onMouseLeave={(event) => {
                    if (!active) event.currentTarget.style.background = 'transparent'
                  }}
                >
                  {item.label}
                </button>
              )
            })}
          </nav>

          <main
            style={{
              flex: 1,
              padding: '28px 32px',
              minWidth: 0,
              overflowY: 'auto',
            }}
          >
            {activeTab === 'password' ? (
              <PasswordSettings />
            ) : (
              <QuickQuestionSettings
                tableGroups={tableGroups}
                quickQuestions={quickQuestions}
                quickQuestionsLoading={quickQuestionsLoading}
                onCreateQuickQuestion={onCreateQuickQuestion}
                onUpdateQuickQuestion={onUpdateQuickQuestion}
                onDeleteQuickQuestion={onDeleteQuickQuestion}
                onReorderQuickQuestions={onReorderQuickQuestions}
              />
            )}
          </main>
        </div>
      </section>
    </div>
  )
}
