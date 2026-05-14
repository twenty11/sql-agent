import { useState } from 'react'
import { colors, radii, fontFamily, fontMono } from '../../styles/tokens'
import { ChevronDownIcon } from '../Icons'

interface SQLBlockProps {
  sql: string | null
}

function highlightSQL(sql: string): React.ReactNode {
  const kw = /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|LIKE|GROUP BY|ORDER BY|HAVING|LIMIT|OFFSET|AS|DISTINCT|COUNT|SUM|AVG|MAX|MIN|CASE|WHEN|THEN|ELSE|END|WITH|UNION|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|NULL|IS|BETWEEN|ASC|DESC|INTERVAL|CURRENT_DATE|DATE_TRUNC|EXTRACT|QUARTER|RETURNED)\b/gi
  const strings = /'[^']*'/g
  const numbers = /\b\d+(\.\d+)?\b/g
  const functions = /\b(EXTRACT|COUNT|SUM|AVG|MAX|MIN|ROUND|DATE|DATE_TRUNC|COALESCE|LENGTH|UPPER|LOWER|TRIM|SUBSTRING|CONCAT|NOW|CURRENT_DATE|CURRENT_TIMESTAMP)\b/gi
  const tables = /\b(orders|customers|products|inventory|regions|order_items|returns|table_name)\b/gi

  const combined = new RegExp(
    `(${kw.source})|(${strings.source})|(${numbers.source})|(${functions.source})|(${tables.source})`,
    'gi',
  )

  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = combined.exec(sql)) !== null) {
    if (match.index > lastIndex) {
      parts.push(
        <span key={`text-${match.index}`}>{sql.slice(lastIndex, match.index)}</span>,
      )
    }
    const text = match[0]
    if (match[2]) {
      parts.push(
        <span key={`str-${match.index}`} style={{ color: '#6a9955' }}>{text}</span>,
      )
    } else if (match[3]) {
      parts.push(
        <span key={`num-${match.index}`} style={{ color: '#ce9178' }}>{text}</span>,
      )
    } else if (match[4]) {
      parts.push(
        <span key={`fn-${match.index}`} style={{ color: '#dcdcaa' }}>{text}</span>,
      )
    } else if (match[5]) {
      parts.push(
        <span key={`tbl-${match.index}`} style={{ color: '#4ec9b0' }}>{text}</span>,
      )
    } else {
      parts.push(
        <span key={`kw-${match.index}`} style={{ color: '#c586c0' }}>{text}</span>,
      )
    }
    lastIndex = match.index + text.length
  }

  if (lastIndex < sql.length) {
    parts.push(
      <span key={`text-end`}>{sql.slice(lastIndex)}</span>,
    )
  }

  return <>{parts}</>
}

export function SQLBlock({ sql }: SQLBlockProps) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (!sql) return
    const fallback = () => {
      const ta = document.createElement('textarea')
      ta.value = sql
      ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      try {
        document.execCommand('copy')
        setCopied(true)
      } catch (_) {}
      document.body.removeChild(ta)
    }
    if (navigator.clipboard) {
      navigator.clipboard.writeText(sql).then(() => {
        setCopied(true)
      }).catch(fallback)
    } else {
      fallback()
    }
  }

  const firstLine = sql ? sql.split('\n').find((l) => l.trim()) || '' : ''
  const collapsedText =
    firstLine.length > 60 ? firstLine.substring(0, 60) + '...' : firstLine

  if (!sql) {
    return (
      <div
        style={{
          fontSize: 11,
          color: colors.textMuted,
          textAlign: 'center',
          padding: '16px 0',
          fontFamily,
        }}
      >
        暂无生成的 SQL
      </div>
    )
  }

  return !expanded ? (
    <button
      onClick={() => setExpanded(true)}
      style={{
        width: '100%',
        background: colors.bgSqlCollapsed,
        border: `1px solid ${colors.border}`,
        borderRadius: radii.xxl,
        padding: '8px 12px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'background 0.15s ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = colors.hoverBg }}
      onMouseLeave={(e) => { e.currentTarget.style.background = colors.bgSqlCollapsed }}
    >
      <span
        style={{
          fontFamily: fontMono,
          fontSize: 12,
          color: colors.textSecondary,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          flex: 1,
        }}
      >
        {collapsedText}
      </span>
      <span
        style={{
          color: colors.textMuted,
          display: 'flex',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <ChevronDownIcon width={14} height={14} color="currentColor" />
      </span>
    </button>
  ) : (
    <div
      style={{
        background: colors.inputBg,
        border: `1px solid ${colors.border}`,
        borderRadius: radii.code,
        padding: '12px 16px',
        position: 'relative',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
        }}
      >
        <button
          onClick={handleCopy}
          style={{
            border: '1px solid transparent',
            background: 'transparent',
            borderRadius: radii.btn,
            padding: '3px 8px',
            fontSize: 12,
            fontWeight: 500,
            color: colors.textMuted,
            cursor: 'pointer',
            fontFamily,
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = colors.hoverBg }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
        >
          {copied ? '已复制' : '复制'}
        </button>
        <button
          onClick={() => { setExpanded(false); setCopied(false) }}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: colors.textMuted,
            display: 'flex',
            alignItems: 'center',
            padding: '4px',
            borderRadius: radii.sm,
            transition: 'color 0.15s ease',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = colors.textPrimary }}
          onMouseLeave={(e) => { e.currentTarget.style.color = colors.textMuted }}
        >
          <span style={{ transform: 'rotate(180deg)', display: 'flex' }}>
            <ChevronDownIcon width={14} height={14} color="currentColor" />
          </span>
        </button>
      </div>
      <pre
        style={{
          margin: 0,
          fontFamily: fontMono,
          fontSize: 13,
          lineHeight: 1.65,
          color: colors.textPrimary,
          whiteSpace: 'pre',
          overflowX: 'auto',
          paddingRight: 72,
        }}
      >
        {highlightSQL(sql)}
      </pre>
    </div>
  )
}
