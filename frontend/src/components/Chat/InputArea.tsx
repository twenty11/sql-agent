import React, { useRef, useCallback, useEffect, useState } from 'react'
import { colors, fontFamily, shadows } from '../../styles/tokens'
import { ArrowUpIcon } from '../Icons'

interface InputAreaProps {
  value: string
  onChange: (value: string) => void
  onSend: (q: string) => boolean | Promise<boolean>
  isStreaming: boolean
  onStop: () => void
}

export function InputArea({ value, onChange, onSend, isStreaming, onStop }: InputAreaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const scrollDivRef = useRef<HTMLDivElement>(null)
  const [isSending, setIsSending] = useState(false)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
    if (scrollDivRef.current) {
      scrollDivRef.current.scrollTop = scrollDivRef.current.scrollHeight
    }
  }, [value])

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    // No maxHeight on the textarea — the wrapper div caps at 204px and scrolls.
    el.style.height = el.scrollHeight + 'px'
    // Keep wrapper scrolled to bottom so the cursor is always visible while typing.
    requestAnimationFrame(() => {
      if (scrollDivRef.current) {
        scrollDivRef.current.scrollTop = scrollDivRef.current.scrollHeight
      }
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSend = useCallback(async () => {
    const q = value.trim()
    if (!q || isStreaming || isSending) return
    setIsSending(true)
    try {
      const sent = await onSend(q)
      if (sent) {
        onChange('')
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto'
        }
      }
    } finally {
      setIsSending(false)
    }
  }, [value, isStreaming, isSending, onSend, onChange])

  const hasContent = value.trim().length > 0

  return (
    <div
      style={{
        border: `1px solid ${colors.borderLight}`,
        borderRadius: '30px',
        boxShadow: shadows.input,
        background: colors.inputBg,
        display: 'flex',
        alignItems: 'flex-end',
        minHeight: 60,
      }}
    >
      {/*
       * Three-layer column: [fixed 18px top] + [scrollable area] + [fixed 18px bottom].
       * The top/bottom divs are outside the scroll container so they never scroll away,
       * giving the textarea a persistent 18px visual padding on both edges.
       */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Fixed top padding — never scrolls */}
        <div style={{ height: 18, flexShrink: 0 }} />

        {/* Scrollable content — capped at 204px (240 total − 18 top − 18 bottom) */}
        <div
          ref={scrollDivRef}
          style={{
            overflowY: 'auto',
            maxHeight: 204,
            scrollbarGutter: 'stable',
          }}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="畅所欲言"
            rows={1}
            style={{
              display: 'block',
              width: '100%',
              border: 'none',
              outline: 'none',
              resize: 'none',
              // Vertical padding lives in the fixed spacer divs above/below.
              padding: '0 20px 0 22px',
              fontSize: 14,
              fontFamily,
              color: colors.textPrimary,
              background: 'transparent',
              lineHeight: 1.5,
              overflow: 'hidden',
              boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Fixed bottom padding — never scrolls */}
        <div style={{ height: 18, flexShrink: 0 }} />
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 10px 10px 6px',
        }}
      >
        {isStreaming ? (
          <button
            onClick={onStop}
            style={{
              width: 36, height: 36,
              borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer',
              border: 'none',
              background: '#000',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.82)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = '#000' }}
          >
            <div style={{ width: 12, height: 12, background: '#fff', borderRadius: 2 }} />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!hasContent || isSending}
            style={{
              width: 36, height: 36,
              borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: hasContent && !isSending ? 'pointer' : 'default',
              border: 'none',
              background: hasContent ? '#000' : 'rgba(0,0,0,0.1)',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (hasContent) e.currentTarget.style.background = 'rgba(0,0,0,0.82)'
            }}
            onMouseLeave={(e) => {
              if (hasContent) e.currentTarget.style.background = '#000'
            }}
            onMouseDown={(e) => {
              if (hasContent) e.currentTarget.style.transform = 'scale(0.95)'
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = 'scale(1)'
            }}
          >
            <ArrowUpIcon width={16} height={16} color={hasContent ? '#fff' : 'rgba(0,0,0,0.3)'} />
          </button>
        )}
      </div>
    </div>
  )
}
