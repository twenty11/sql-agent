import React, { useRef, useEffect, useState } from 'react'
import type { Message, TableGroup, QuickQuestion, QuickQuestionInput } from '../../types/chat'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { UserMessage } from '../Chat/UserMessage'
import { AIMessage } from '../Chat/AIMessage'
import { InputArea } from '../Chat/InputArea'
import { TableGroupSelector } from '../Chat/TableGroupSelector'

interface ChatAreaProps {
  title: string
  messages: Message[]
  isStreaming: boolean
  onSend: (q: string) => boolean | Promise<boolean>
  onStop: () => void
  onToggleSidebar?: () => void
  sidebarCollapsed?: boolean
  tableGroups: TableGroup[]
  selectedGroupId: string | null
  onSelectGroup: (groupId: string | null) => void
  tableGroupsLoading?: boolean
  quickQuestions: QuickQuestion[]
  inputValue: string
  onInputChange: (value: string) => void
  onApplyQuickQuestion: (item: QuickQuestion) => void
  onCreateQuickQuestion: (payload: QuickQuestionInput) => Promise<QuickQuestion>
}

function quickQuestionLabel(item: QuickQuestion) {
  const displayName = item.display_name?.trim()
  if (displayName) return displayName
  const text = item.question_text.trim()
  return text.length > 16 ? `${text.slice(0, 16)}...` : text
}

function QuickQuestionChips({
  items,
  selectedGroupId,
  onApply,
}: {
  items: QuickQuestion[]
  selectedGroupId: string | null
  onApply: (item: QuickQuestion) => void
}) {
  const pinned = selectedGroupId
    ? items.filter((item) => item.is_pinned && item.table_group_id === selectedGroupId)
    : []
  if (pinned.length === 0) return null

  return (
    <div
      className="quick-question-chip-row"
      style={{
        position: 'absolute',
        left: 10,
        right: 10,
        bottom: 'calc(100% + 8px)',
        zIndex: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        overflowX: 'auto',
        padding: '2px 0',
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
        pointerEvents: 'auto',
      }}
    >
      {pinned.map((item) => (
        <button
          key={item.id}
          type="button"
          title={item.question_text}
          onClick={() => onApply(item)}
          style={{
            maxWidth: 156,
            display: 'inline-flex',
            alignItems: 'center',
            flexShrink: 0,
            padding: '5px 12px',
            border: '1px solid rgba(0,0,0,0.06)',
            borderRadius: radii.pill,
            background: 'rgba(255,255,255,0.72)',
            color: 'rgba(0,0,0,0.46)',
            fontSize: 12,
            fontFamily,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {quickQuestionLabel(item)}
          </span>
        </button>
      ))}
    </div>
  )
}

function InputDock({
  quickQuestions,
  selectedGroupId,
  inputValue,
  onInputChange,
  onSend,
  isStreaming,
  onStop,
  onApplyQuickQuestion,
}: {
  quickQuestions: QuickQuestion[]
  selectedGroupId: string | null
  inputValue: string
  onInputChange: (value: string) => void
  onSend: (q: string) => boolean | Promise<boolean>
  isStreaming: boolean
  onStop: () => void
  onApplyQuickQuestion: (item: QuickQuestion) => void
}) {
  return (
    <div style={{ position: 'relative' }}>
      <QuickQuestionChips
        items={quickQuestions}
        selectedGroupId={selectedGroupId}
        onApply={onApplyQuickQuestion}
      />
      <InputArea
        value={inputValue}
        onChange={onInputChange}
        onSend={onSend}
        isStreaming={isStreaming}
        onStop={onStop}
      />
    </div>
  )
}

function QuickQuestionSaveDialog({
  initialQuestion,
  selectedGroupId,
  selectedGroupName,
  onCreate,
  onClose,
}: {
  initialQuestion: string
  selectedGroupId: string | null
  selectedGroupName: string | null
  onCreate: (payload: QuickQuestionInput) => Promise<QuickQuestion>
  onClose: () => void
}) {
  const [displayName, setDisplayName] = useState('')
  const [questionText, setQuestionText] = useState(initialQuestion)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '9px 11px',
    border: `1px solid ${colors.borderInput}`,
    borderRadius: radii.sm,
    background: colors.inputBg,
    color: colors.textPrimary,
    fontSize: 14,
    fontFamily,
    boxSizing: 'border-box',
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    const cleanQuestion = questionText.trim()
    if (!cleanQuestion) {
      setError('问题文本不能为空')
      return
    }
    if (!selectedGroupId) {
      setError('请先选择表分组')
      return
    }

    try {
      setSubmitting(true)
      setError('')
      await onCreate({
        display_name: displayName.trim() || null,
        question_text: cleanQuestion,
        table_group_id: selectedGroupId,
        is_pinned: true,
      })
      onClose()
    } catch {
      setError('保存失败，请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      role="presentation"
      onMouseDown={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 260,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.16)',
        padding: 20,
      }}
    >
      <form
        onSubmit={submit}
        onMouseDown={(event) => event.stopPropagation()}
        style={{
          width: 'min(460px, calc(100vw - 32px))',
          background: colors.pageBg,
          border: `1px solid ${colors.border}`,
          borderRadius: radii.xxl,
          boxShadow: '0 18px 48px rgba(0,0,0,0.16)',
          padding: 20,
          fontFamily,
        }}
      >
        <h2 style={{ margin: '0 0 16px', fontSize: 18, color: colors.textPrimary }}>
          收藏为快捷问题
        </h2>

        <label style={{ display: 'block', marginBottom: 12 }}>
          <span style={{ display: 'block', marginBottom: 6, fontSize: 13, color: colors.textSecondary }}>
            显示名称（可选）
          </span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="例如：昨日新增用户"
            maxLength={100}
            style={inputStyle}
          />
        </label>

        <label style={{ display: 'block', marginBottom: 12 }}>
          <span style={{ display: 'block', marginBottom: 6, fontSize: 13, color: colors.textSecondary }}>
            问题文本
          </span>
          <textarea
            value={questionText}
            onChange={(event) => setQuestionText(event.target.value)}
            rows={4}
            style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.5 }}
          />
        </label>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ color: colors.errorColor, fontSize: 13 }}>{error}</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 14px',
                border: `1px solid ${colors.borderStrong}`,
                borderRadius: radii.sm,
                background: 'transparent',
                color: colors.textSecondary,
                cursor: 'pointer',
                fontFamily,
              }}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: '8px 16px',
                border: 'none',
                borderRadius: radii.sm,
                background: submitting ? colors.borderStrong : colors.accent,
                color: colors.textWhite,
                cursor: submitting ? 'default' : 'pointer',
                fontFamily,
              }}
            >
              {submitting ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}

export function ChatArea({
  title,
  messages,
  isStreaming,
  onSend,
  onStop,
  tableGroups,
  selectedGroupId,
  onSelectGroup,
  tableGroupsLoading = false,
  quickQuestions,
  inputValue,
  onInputChange,
  onApplyQuickQuestion,
  onCreateQuickQuestion,
}: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const isEmpty = messages.length === 0
  const [saveQuestionText, setSaveQuestionText] = useState<string | null>(null)
  const selectedGroup = tableGroups.find((group) => group.id === selectedGroupId) ?? null

  useEffect(() => {
    if (!isEmpty) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isEmpty])

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
        background: '#f0efee',
        fontFamily,
      }}
    >
      <style>{`
        .quick-question-chip-row::-webkit-scrollbar {
          display: none;
        }
        .md-content ul, .md-content ol {
          padding-left: 1.5em;
          margin: 4px 0 8px;
        }
        .md-content li {
          margin-bottom: 2px;
        }
        .md-content p {
          margin: 0 0 6px;
        }
        .md-content p:last-child {
          margin-bottom: 0;
        }
        .md-content h1, .md-content h2, .md-content h3 {
          margin: 10px 0 4px;
        }
      `}</style>

      {/* 顶部导航栏 */}
      <div
        style={{
          height: 52,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
          <TableGroupSelector
            groups={tableGroups}
            selectedGroupId={selectedGroupId}
            onSelect={onSelectGroup}
            loading={tableGroupsLoading}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }} />
      </div>

      {isEmpty ? (
        /* ── 空状态：Logo + 输入框居中偏上 ── */
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            paddingTop: 'calc(16vh)',
            paddingBottom: '8vh',
            boxSizing: 'border-box',
            overflowY: 'auto',
          }}
        >
          {/* Logo + DataLens */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              marginBottom: 80,
              animation: 'fadeIn 0.4s ease',
            }}
          >
            <img
              src="/logo.png"
              alt="logo"
              style={{ width: 40, height: 40, borderRadius: radii.lg, objectFit: 'contain' }}
            />
            <span style={{ fontSize: 22, fontWeight: 700, color: colors.textPrimary }}>
              DataLens
            </span>
          </div>

          {/* 输入框 */}
          <div style={{ width: '100%', maxWidth: 800, padding: '0 24px', boxSizing: 'border-box' }}>
            <InputDock
              quickQuestions={quickQuestions}
              selectedGroupId={selectedGroupId}
              inputValue={inputValue}
              onInputChange={onInputChange}
              onSend={onSend}
              isStreaming={isStreaming}
              onStop={onStop}
              onApplyQuickQuestion={onApplyQuickQuestion}
            />
          </div>
        </div>
      ) : (
        /* ── 有消息：正常布局 ── */
        <>
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '24px',
            }}
          >
            <div style={{ maxWidth: 760, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
              {messages.map((msg) =>
                msg.role === 'user' ? (
                  <UserMessage
                    key={msg.id}
                    message={msg}
                    onSaveQuickQuestion={setSaveQuestionText}
                  />
                ) : (
                  <AIMessage key={msg.id} message={msg} />
                )
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          <div
            style={{
              padding: '0 24px 16px',
              flexShrink: 0,
            }}
          >
            <div style={{ maxWidth: 800, margin: '0 auto' }}>
              <InputDock
                quickQuestions={quickQuestions}
                selectedGroupId={selectedGroupId}
                inputValue={inputValue}
                onInputChange={onInputChange}
                onSend={onSend}
                isStreaming={isStreaming}
                onStop={onStop}
                onApplyQuickQuestion={onApplyQuickQuestion}
              />
            </div>
          </div>
        </>
      )}

      {saveQuestionText !== null && (
        <QuickQuestionSaveDialog
          initialQuestion={saveQuestionText}
          selectedGroupId={selectedGroupId}
          selectedGroupName={selectedGroup?.name ?? null}
          onCreate={onCreateQuickQuestion}
          onClose={() => setSaveQuestionText(null)}
        />
      )}
    </div>
  )
}
