import React, { useState } from 'react'
import type { Message } from '../../types/chat'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { BookmarkIcon } from '../Icons'

interface UserMessageProps {
  message: Message
  onSaveQuickQuestion?: (questionText: string) => void
}

export function UserMessage({ message, onSaveQuickQuestion }: UserMessageProps) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        justifyContent: 'flex-end',
        marginBottom: 16,
        animation: 'fadeInUp 0.2s ease',
      }}
    >
      <div style={{ maxWidth: '68%', position: 'relative' }}>
        <div
          style={{
            background: colors.userMsgBg,
            border: `1px solid ${colors.border}`,
            borderRadius: '22px 22px 8px 22px',
            padding: '12px 16px',
            fontSize: 14,
            color: colors.textPrimary,
            lineHeight: 1.6,
            fontFamily,
            wordBreak: 'break-word',
            whiteSpace: 'pre-wrap',
          }}
        >
          {message.content}
        </div>
        {onSaveQuickQuestion && (
          <button
            type="button"
            title="收藏为快捷问题"
            onClick={() => onSaveQuickQuestion(message.content)}
            style={{
              position: 'absolute',
              left: -36,
              top: 4,
              width: 28,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: `1px solid ${colors.borderLight}`,
              borderRadius: radii.md,
              background: hovered ? colors.pageBg : 'transparent',
              color: colors.textMuted,
              cursor: 'pointer',
              opacity: hovered ? 1 : 0,
              transition: 'opacity 0.15s ease, background 0.15s ease',
            }}
            onMouseEnter={(event) => {
              event.currentTarget.style.background = colors.hoverBg
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.background = hovered ? colors.pageBg : 'transparent'
            }}
          >
            <BookmarkIcon width={14} height={14} color={colors.textSecondary} />
          </button>
        )}
      </div>
    </div>
  )
}
