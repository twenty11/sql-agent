import React, { useEffect, useRef, useState } from 'react'
import { colors, radii, fontFamily, shadows } from '../../styles/tokens'

export function ToggleSwitch({
  on, onClick, disabled,
}: {
  on: boolean
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <div
      onClick={() => { if (!disabled) onClick() }}
      style={{
        width: 36, height: 20,
        background: on ? colors.accent : 'rgba(0,0,0,0.15)',
        borderRadius: 10,
        position: 'relative',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
        transition: 'background 0.15s ease',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          position: 'absolute',
          width: 16, height: 16,
          background: 'white',
          borderRadius: '50%',
          top: 2, left: 2,
          transition: 'transform 0.15s ease',
          transform: on ? 'translateX(16px)' : 'translateX(0)',
        }}
      />
    </div>
  )
}

export function StatusDot({ success }: { success: boolean | null }) {
  if (success === null) return null
  return (
    <span
      style={{
        display: 'inline-block',
        width: 8, height: 8,
        borderRadius: '50%',
        background: success ? colors.successColor : colors.errorColor,
        marginRight: 6,
      }}
    />
  )
}

const ROLE_LABEL_MAP: Record<string, { bg: string; color: string; label: string }> = {
  admin: { bg: colors.adminBadgeBg, color: colors.adminBadgeText, label: '管理员' },
  analyst: { bg: colors.analystBadgeBg, color: colors.analystBadgeText, label: '分析师' },
  viewer: { bg: colors.viewerBadgeBg, color: colors.viewerBadgeText, label: '观察者' },
}

export function RoleBadge({ role }: { role: string }) {
  const s = ROLE_LABEL_MAP[role] ?? {
    bg: colors.viewerBadgeBg, color: colors.viewerBadgeText, label: role,
  }
  return (
    <span
      style={{
        background: s.bg, color: s.color,
        borderRadius: radii.pill,
        fontSize: 13, fontWeight: 600,
        padding: '3px 10px',
        letterSpacing: '0.125px',
        marginRight: 4,
      }}
    >
      {s.label}
    </span>
  )
}

export function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        background: active ? '#e8f6ef' : '#fef2f2',
        color: active ? colors.successColor : colors.errorColor,
        borderRadius: radii.pill,
        fontSize: 13, fontWeight: 600,
        padding: '3px 10px',
      }}
    >
      <span
        style={{
          width: 6, height: 6, borderRadius: '50%',
          background: active ? colors.successColor : colors.errorColor,
        }}
      />
      {active ? '已启用' : '已禁用'}
    </span>
  )
}

export const inputStyle: React.CSSProperties = {
  padding: '9px 14px',
  border: `1px solid ${colors.borderInput}`,
  borderRadius: radii.sm,
  fontSize: 14, fontFamily,
  color: colors.textPrimary,
  background: colors.inputBg,
  width: '100%',
  boxSizing: 'border-box',
}

export const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 13, fontWeight: 500,
  color: colors.textSecondary, marginBottom: 6,
}

export const primaryBtnStyle: React.CSSProperties = {
  background: colors.accent, color: '#fff',
  border: 'none', borderRadius: radii.sm,
  padding: '7px 16px', fontSize: 14,
  cursor: 'pointer', fontFamily, fontWeight: 500,
  transition: 'background 0.15s ease',
}

export const secondaryBtnStyle: React.CSSProperties = {
  background: 'transparent', color: colors.textSecondary,
  border: `1px solid ${colors.border}`, borderRadius: radii.sm,
  padding: '7px 16px', fontSize: 14,
  cursor: 'pointer', fontFamily,
}

export const dangerBtnStyle: React.CSSProperties = {
  background: colors.errorColor, color: '#fff',
  border: 'none', borderRadius: radii.sm,
  padding: '7px 16px', fontSize: 14,
  cursor: 'pointer', fontFamily, fontWeight: 500,
}

// ─── CustomSelect ──────────────────────────────────────────────────
// 替代原生 select，下拉列表最多显示 10 条，超出滚动

export interface SelectOption {
  value: string
  label: string
}

const ITEM_H = 36
const MAX_VISIBLE = 10

export function CustomSelect({
  value,
  onChange,
  options,
  placeholder,
  style,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  options: SelectOption[]
  placeholder?: string
  style?: React.CSSProperties
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selected = options.find((o) => o.value === value)
  const listHeight = Math.min(options.length, MAX_VISIBLE) * ITEM_H

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      <div
        onClick={() => { if (!disabled) setOpen((p) => !p) }}
        style={{
          ...inputStyle,
          height: 36,
          padding: '0 10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: disabled ? 'not-allowed' : 'pointer',
          userSelect: 'none',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        <span style={{ color: selected ? colors.textPrimary : colors.textSecondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {selected?.label ?? placeholder ?? '请选择'}
        </span>
        <span style={{ color: colors.textSecondary, fontSize: 10, flexShrink: 0, marginLeft: 6 }}>▼</span>
      </div>
      {open && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          background: '#fff',
          border: `1px solid ${colors.border}`,
          borderRadius: radii.sm,
          boxShadow: shadows.card,
          zIndex: 9999,
          maxHeight: listHeight,
          overflowY: options.length > MAX_VISIBLE ? 'auto' : 'hidden',
          marginTop: 2,
        }}>
          {options.map((o) => (
            <div
              key={o.value}
              onMouseDown={(e) => {
                e.preventDefault()
                onChange(o.value)
                setOpen(false)
              }}
              style={{
                height: ITEM_H,
                padding: '0 10px',
                display: 'flex',
                alignItems: 'center',
                cursor: 'pointer',
                fontSize: 14,
                color: o.value === value ? colors.accent : colors.textPrimary,
                background: o.value === value ? colors.accent + '10' : 'transparent',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
              onMouseEnter={(e) => { if (o.value !== value) e.currentTarget.style.background = colors.hoverBg }}
              onMouseLeave={(e) => { e.currentTarget.style.background = o.value === value ? colors.accent + '10' : 'transparent' }}
            >
              {o.label}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function Modal({
  title, onClose, children, maxWidth = 400, closeOnBackdropClick = true,
}: {
  title: string
  onClose: () => void
  children: React.ReactNode
  maxWidth?: number
  closeOnBackdropClick?: boolean
}) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.35)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (closeOnBackdropClick && e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        background: '#fff', borderRadius: radii.xxl,
        padding: 24, width: '100%', maxWidth,
        boxShadow: shadows.card,
        maxHeight: '85vh', overflow: 'auto',
      }}>
        <div style={{ fontSize: 17, fontWeight: 600, marginBottom: 18, color: colors.textPrimary }}>
          {title}
        </div>
        {children}
      </div>
    </div>
  )
}
