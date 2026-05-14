import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { colors, fontFamily } from '../../styles/tokens'
import { BulbIcon } from '../Icons'

interface QueryExplainProps {
  explanation: string | null
}

export function QueryExplain({ explanation }: QueryExplainProps) {
  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 10,
        }}
      >
        <BulbIcon width={15} height={15} color={colors.textSecondary} />
        <span style={{ fontSize: 13, fontWeight: 600, color: 'rgba(0,0,0,0.9)', fontFamily }}>
          查询说明
        </span>
      </div>
      {explanation ? (
        <div
          style={{
            fontSize: 14,
            fontWeight: 400,
            color: 'rgba(0,0,0,0.85)',
            lineHeight: 1.7,
            fontFamily,
            wordBreak: 'break-word',
            overflowWrap: 'break-word',
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              ul: ({ children }) => (
                <ul style={{ paddingLeft: 16, margin: '4px 0', listStyleType: 'disc' }}>{children}</ul>
              ),
              li: ({ children }) => (
                <li style={{ margin: '2px 0', lineHeight: 1.7 }}>{children}</li>
              ),
              p: ({ children }) => (
                <p style={{ margin: '4px 0' }}>{children}</p>
              ),
            }}
          >
            {explanation}
          </ReactMarkdown>
        </div>
      ) : (
        <div
          style={{
            fontSize: 11,
            color: colors.textMuted,
            textAlign: 'center',
            padding: '16px 0',
            fontFamily,
          }}
        >
          发送问题后，这里会显示查询意图说明
        </div>
      )}
    </div>
  )
}
