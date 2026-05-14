import React, { useState, useCallback, useEffect, useRef } from 'react'
import type { Message } from '../../types/chat'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { SQLBlock } from '../SQL/SQLBlock'
import { QueryExplain } from '../SQL/QueryExplain'
import { CloseIcon } from '../Icons'

interface RightPanelProps {
  open: boolean
  onToggle: () => void
  activeMessage: Message | null
  width?: number
  onWidthChange?: (w: number) => void
}

export function RightPanel({ open, onToggle, activeMessage, width: controlledWidth, onWidthChange }: RightPanelProps) {
  const [internalWidth, setInternalWidth] = useState(320)
  const width = controlledWidth ?? internalWidth
  const setWidth = onWidthChange ?? setInternalWidth
  const isDragging = useRef(false)
  const startX = useRef(0)
  const startWidth = useRef(0)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDragging.current = true
    startX.current = e.clientX
    startWidth.current = width
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [width])

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging.current) return
    const delta = startX.current - e.clientX
    const newWidth = Math.max(256, Math.min(600, startWidth.current + delta))
    setWidth(newWidth)
  }, [])

  const handleMouseUp = useCallback(() => {
    isDragging.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [])

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [handleMouseMove, handleMouseUp])

  return (
    <aside
      style={{
        width: open ? width : 0,
        minWidth: open ? width : 0,
        overflow: 'hidden',
        background: colors.sidebarBg,
        borderLeft: open ? `1px solid ${colors.border}` : 'none',
        display: 'flex',
        flexDirection: 'column',
        transition: open ? 'none' : 'width 0.2s ease, min-width 0.2s ease',
        height: '100vh',
        fontFamily,
        flexShrink: 0,
        position: 'relative',
      }}
    >
      {/* 拖动手柄 */}
      {open && (
        <div
          onMouseDown={handleMouseDown}
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: 6,
            cursor: 'col-resize',
            zIndex: 10,
          }}
        />
      )}

      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 12px 10px', flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 600, color: colors.textPrimary }}>
          查询详情
        </span>
        <button
          onClick={onToggle}
          style={{
            border: 'none', background: 'transparent',
            cursor: 'pointer', color: colors.textMuted,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '2px 6px', borderRadius: radii.listItem,
          }}
        >
          <CloseIcon width={14} height={14} color={colors.textMuted} />
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
        {/* 查询说明 */}
        <QueryExplain explanation={activeMessage?.explanation || null} />

        {/* 分隔线 */}
        <div
          style={{
            borderTop: `1px solid rgba(0,0,0,0.06)`,
            margin: '12px 0',
          }}
        />

        {/* SQL 代码块 */}
        <SQLBlock sql={activeMessage?.sql || null} />
      </div>
    </aside>
  )
}
