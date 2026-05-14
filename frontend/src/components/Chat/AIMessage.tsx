import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '../../types/chat'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { ResultTable } from './ResultTable'
import { SQLBlock } from '../SQL/SQLBlock'
import { QueryExplain } from '../SQL/QueryExplain'
import { ChevronDownIcon } from '../Icons'

interface AIMessageProps {
  message: Message
}

function ThinkingDots() {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', padding: '6px 0' }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 6, height: 6,
            borderRadius: '50%',
            background: colors.textMuted,
            display: 'inline-block',
            animation: `dotBounce 1.2s ease-in-out ${i * 0.15}s infinite`,
          }}
        />
      ))}
    </span>
  )
}

function DetailsAccordion({ message }: { message: Message }) {
  const [open, setOpen] = useState(false)

  return (
    <div
      style={{
        border: `1px solid rgba(0,0,0,0.08)`,
        borderRadius: radii.lg,
        overflow: 'hidden',
        marginTop: 6,
      }}
    >
      {/* 折叠触发行 */}
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          padding: '5px 12px',
          background: open ? 'rgba(0,0,0,0.035)' : 'rgba(0,0,0,0.025)',
          border: 'none',
          cursor: 'pointer',
          transition: 'background 0.15s ease',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.045)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = open ? 'rgba(0,0,0,0.035)' : 'rgba(0,0,0,0.025)' }}
      >
        <span style={{ fontSize: 12, color: colors.textSecondary, fontFamily }}>
          查询说明
        </span>
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            flexShrink: 0,
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
          }}
        >
          <ChevronDownIcon width={14} height={14} color={colors.textMuted} />
        </span>
      </button>

      {/* 展开内容 */}
      {open && (
        <div
          style={{
            padding: '14px 16px',
            background: 'rgba(255,255,255,0.55)',
            borderTop: `1px solid rgba(0,0,0,0.06)`,
          }}
        >
          {message.explanation && (
            <>
              <QueryExplain explanation={message.explanation} />
              <div style={{ borderTop: `1px solid rgba(0,0,0,0.06)`, margin: '12px 0' }} />
            </>
          )}
          {message.sql && <SQLBlock sql={message.sql} />}
        </div>
      )}
    </div>
  )
}

export function AIMessage({ message }: AIMessageProps) {
  const hasSqlOrExplanation = !!(message.sql || message.explanation)
  const statusText =
    message.status === 'stopped'
      ? '已停止'
      : message.status === 'failed'
        ? (message.error || '生成失败')
        : ''

  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        alignItems: 'flex-start',
        animation: 'msgIn 0.2s ease',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* 消息内容 */}
        <div
          style={{
            fontSize: 14,
            color: colors.textPrimary,
            lineHeight: 1.7,
            fontFamily,
            wordBreak: 'break-word',
          }}
        >
          {message.thinking ? (
            <ThinkingDots />
          ) : (
            message.content ? (
              <>
                <div className="md-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                </div>
                {statusText && (
                  <div style={{ marginTop: 6, fontSize: 12, color: colors.textMuted }}>
                    {statusText}
                  </div>
                )}
              </>
            ) : (
              <span style={{ color: colors.textMuted }}>{statusText || '正在生成...'}</span>
            )
          )}
        </div>

        {/* 查询结果表格 */}
        {message.result && !message.thinking && (
          <div style={{ marginTop: 14 }}>
            <ResultTable result={message.result} />
          </div>
        )}

        {/* 内联查询详情折叠面板：与结果表完全同步 */}
        {message.result && !message.thinking && hasSqlOrExplanation && (
          <DetailsAccordion message={message} />
        )}
      </div>
    </div>
  )
}
