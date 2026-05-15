import { useState, useRef, useEffect, useCallback, type ReactNode, type ReactElement } from 'react'
import { createPortal } from 'react-dom'
import { colors, radii, fontFamily } from '../../styles/tokens'

type Placement = 'top' | 'bottom' | 'left' | 'right'

interface TooltipProps {
  content: ReactNode
  children: ReactElement
  placement?: Placement
  delay?: number
  maxWidth?: number
}

const GAP = 6

export function Tooltip({ content, children, placement = 'top', delay = 400, maxWidth }: TooltipProps) {
  const [phase, setPhase] = useState<'hidden' | 'measure' | 'visible'>('hidden')
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const [resolvedPlacement, setResolvedPlacement] = useState<Placement>(placement)
  const wrapperRef = useRef<HTMLSpanElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => setPhase('measure'), delay)
  }, [delay])

  const hide = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setPhase('hidden')
  }, [])

  useEffect(() => {
    if (phase !== 'measure') return
    const wrapper = wrapperRef.current
    const tip = tipRef.current
    if (!wrapper || !tip) return

    // display:contents wrapper has no bounding box; use first child instead
    const trigEl = (wrapper.firstElementChild as HTMLElement) ?? wrapper
    const tr = trigEl.getBoundingClientRect()
    const tipR = tip.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    let p = placement
    if (placement === 'top' && tr.top < tipR.height + GAP + 8) p = 'bottom'
    else if (placement === 'bottom' && tr.bottom + tipR.height + GAP + 8 > vh) p = 'top'
    setResolvedPlacement(p)

    let top: number, left: number
    switch (p) {
      case 'bottom':
        top = tr.bottom + GAP
        left = tr.left + tr.width / 2 - tipR.width / 2
        break
      case 'left':
        top = tr.top + tr.height / 2 - tipR.height / 2
        left = tr.left - tipR.width - GAP
        break
      case 'right':
        top = tr.top + tr.height / 2 - tipR.height / 2
        left = tr.right + GAP
        break
      default: // top
        top = tr.top - tipR.height - GAP
        left = tr.left + tr.width / 2 - tipR.width / 2
    }

    left = Math.max(8, Math.min(left, vw - tipR.width - 8))
    top = Math.max(8, Math.min(top, vh - tipR.height - 8))
    setPos({ top, left })
    setPhase('visible')
  }, [phase, placement])

  if (!content) return children

  const originMap: Record<Placement, string> = {
    top: 'bottom center',
    bottom: 'top center',
    left: 'right center',
    right: 'left center',
  }

  return (
    <>
      <span
        ref={wrapperRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        style={{ display: 'contents' }}
      >
        {children}
      </span>
      {phase !== 'hidden' &&
        createPortal(
          <div
            ref={tipRef}
            style={{
              position: 'fixed',
              top: pos.top,
              left: pos.left,
              zIndex: 9999,
              background: colors.userMsgBg,
              boxShadow: '0 1px 4px rgba(0,0,0,0.02)',
              borderRadius: radii.sm,
              padding: '4px 8px',
              fontSize: 12,
              color: colors.textPrimary,
              fontFamily,
              pointerEvents: 'none',
              whiteSpace: maxWidth ? 'normal' : 'nowrap',
              maxWidth: maxWidth,
              wordBreak: maxWidth ? 'break-word' : undefined,
              visibility: phase === 'measure' ? 'hidden' : 'visible',
              animation: phase === 'visible' ? 'tooltipIn 0.15s ease both' : 'none',
              transformOrigin: originMap[resolvedPlacement],
            }}
          >
            {content}
          </div>,
          document.body,
        )}
    </>
  )
}
