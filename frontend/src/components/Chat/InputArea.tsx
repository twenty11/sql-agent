import React, { useRef, useCallback, useEffect, useState } from 'react'
import { colors, fontFamily, shadows } from '../../styles/tokens'
import { ArrowUpIcon } from '../Icons'

const CYCLE_TEXTS = [
  "想看哪个业务的数据？",
  "输入您的查询需求",
  "有什么想查的数据吗？",
  "告诉我您想了解什么业务情况？",
  "想查询哪些数据呢？",
  "请输入自然语言查询",
  "有什么业务数据需要我帮您查？",
  "来，问我点业务上的问题试试",
  "您今天想看什么数据？",
]
const STATIC_PLACEHOLDER = "畅所欲言"

type SlotPhase = 'idle' | 'exiting' | 'entering'

function PlaceholderSlot({ dynamic }: { dynamic: boolean }) {
  const [curIdx, setCurIdx] = useState(0)
  const [nxtIdx, setNxtIdx] = useState(1)
  const [phase, setPhase] = useState<SlotPhase>('idle')

  useEffect(() => {
    if (!dynamic || phase !== 'idle') return
    const id = setTimeout(() => setPhase('exiting'), 7000)
    return () => clearTimeout(id)
  }, [dynamic, phase])

  if (!dynamic) return <>{STATIC_PLACEHOLDER}</>

  const onExitDone = () => setPhase('entering')
  const onEnterDone = () => {
    setCurIdx(nxtIdx)
    setNxtIdx(n => (n + 1) % CYCLE_TEXTS.length)
    setPhase('idle')
  }

  return (
    <>
      <div
        style={{
          position: 'absolute', inset: 0,
          animation: phase === 'exiting' ? 'ph-exit 0.32s ease forwards' : 'none',
          transform: phase === 'entering' ? 'translateY(-100%)' : undefined,
          opacity: phase === 'entering' ? 0 : undefined,
        }}
        onAnimationEnd={phase === 'exiting' ? onExitDone : undefined}
      >
        {CYCLE_TEXTS[curIdx]}
      </div>
      {phase !== 'idle' && (
        <div
          style={{
            position: 'absolute', inset: 0,
            transform: phase === 'exiting' ? 'translateY(100%)' : undefined,
            animation: phase === 'entering' ? 'ph-enter 0.32s ease forwards' : 'none',
          }}
          onAnimationEnd={phase === 'entering' ? onEnterDone : undefined}
        >
          {CYCLE_TEXTS[nxtIdx]}
        </div>
      )}
    </>
  )
}

interface InputAreaProps {
  value: string
  onChange: (value: string) => void
  onSend: (q: string) => boolean | Promise<boolean>
  isStreaming: boolean
  onStop: () => void
  dynamicPlaceholder?: boolean
}

export function InputArea({ value, onChange, onSend, isStreaming, onStop, dynamicPlaceholder }: InputAreaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const scrollDivRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [isSending, setIsSending] = useState(false)
  const singleLineHeightRef = useRef(0)

  const updateBorderRadius = (scrollHeight: number) => {
    if (!containerRef.current) return
    const isMulti = singleLineHeightRef.current > 0 && scrollHeight > singleLineHeightRef.current
    containerRef.current.style.borderRadius = isMulti ? '28px' : '9999px'
  }

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const sh = el.scrollHeight
    el.style.height = `${sh}px`
    if (singleLineHeightRef.current === 0) singleLineHeightRef.current = sh
    updateBorderRadius(sh)
    if (scrollDivRef.current) {
      scrollDivRef.current.scrollTop = scrollDivRef.current.scrollHeight
    }
  }, [value])

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    const sh = el.scrollHeight
    el.style.height = sh + 'px'
    updateBorderRadius(sh)
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
      ref={containerRef}
      style={{
        border: `1px solid ${colors.borderLight}`,
        borderRadius: '9999px',
        boxShadow: '0 1px 4px rgba(0,0,0,0.02)',
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
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        {/* Fixed top padding — never scrolls */}
        <div style={{ height: 16, flexShrink: 0 }} />

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
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus={!!dynamicPlaceholder}
            rows={1}
            style={{
              display: 'block',
              width: '100%',
              border: 'none',
              outline: 'none',
              resize: 'none',
              padding: '0 20px 0 22px',
              fontSize: 16,
              fontFamily,
              color: colors.textPrimary,
              background: 'transparent',
              lineHeight: 1.75,
              overflow: 'hidden',
              boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Fixed bottom padding — never scrolls */}
        <div style={{ height: 16, flexShrink: 0 }} />

        {/* Animated placeholder overlay — only visible when textarea is empty */}
        {!value && (
          <div
            style={{
              position: 'absolute',
              top: 16,
              left: 22,
              right: 20,
              height: '1.75em',
              overflow: 'hidden',
              pointerEvents: 'none',
              color: 'rgba(0,0,0,0.35)',
              fontSize: 16,
              lineHeight: 1.75,
              fontFamily,
              whiteSpace: 'nowrap',
            }}
          >
            <PlaceholderSlot dynamic={!!dynamicPlaceholder} />
          </div>
        )}
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
              width: 40, height: 40,
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
              width: 40, height: 40,
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
