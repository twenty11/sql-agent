import { useState, useRef, useEffect } from 'react'
import type { TableGroup } from '../../types/chat'
import { colors, radii, fontFamily } from '../../styles/tokens'

interface TableGroupSelectorProps {
  groups: TableGroup[]
  selectedGroupId: string | null
  onSelect: (groupId: string | null) => void
  loading?: boolean
}

export function TableGroupSelector({
  groups,
  selectedGroupId,
  onSelect,
  loading = false,
}: TableGroupSelectorProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selected = groups.find((g) => g.id === selectedGroupId) ?? null

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelect = (id: string | null) => {
    onSelect(id)
    setOpen(false)
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      {/* Trigger button */}
      <button
        onClick={() => !loading && setOpen((v) => !v)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 10px 4px 8px',
          border: selected
            ? `1.5px solid ${colors.accent}`
            : `1.5px solid ${colors.border}`,
          borderRadius: radii.pill,
          background: selected ? colors.pillBg : 'transparent',
          cursor: loading ? 'default' : 'pointer',
          fontFamily,
          fontSize: 13,
          fontWeight: selectedGroupId ? 600 : 500,
          color: selectedGroupId ? colors.accent : colors.textSecondary,
          transition: 'all 0.15s ease',
          whiteSpace: 'nowrap',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => {
          if (!loading) {
            const el = e.currentTarget
            el.style.background = selected ? colors.pillBg : colors.hoverBg
            el.style.borderColor = selected ? colors.accentHover : colors.borderStrong
          }
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget
          el.style.background = selected ? colors.pillBg : 'transparent'
          el.style.borderColor = selected ? colors.accent : colors.border
        }}
      >
        {/* Grid icon */}
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
          <rect x="1" y="1" width="5.5" height="5.5" rx="1.5"
            fill={selected ? colors.accent : colors.textMuted} />
          <rect x="9.5" y="1" width="5.5" height="5.5" rx="1.5"
            fill={selected ? colors.accent : colors.textMuted} />
          <rect x="1" y="9.5" width="5.5" height="5.5" rx="1.5"
            fill={selected ? colors.accent : colors.textMuted} />
          <rect x="9.5" y="9.5" width="5.5" height="5.5" rx="1.5"
            fill={selected ? colors.accent : colors.textMuted} />
        </svg>

        <span>{loading ? '加载中...' : (selected ? selected.name : '选择分组')}</span>

        {/* Chevron */}
        {!loading && (
          <svg
            width="10" height="10" viewBox="0 0 10 10"
            style={{
              transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.15s ease',
              flexShrink: 0,
            }}
          >
            <path d="M2 3.5L5 6.5L8 3.5" stroke={colors.textMuted} strokeWidth="1.5"
              strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            zIndex: 100,
            minWidth: 200,
            maxWidth: 280,
            background: '#fff',
            border: `1px solid ${colors.border}`,
            borderRadius: radii.md,
            boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
            overflow: 'hidden',
            animation: 'fadeIn 0.12s ease',
          }}
        >
          {/* Header */}
          <div style={{
            padding: '8px 12px 6px',
            borderBottom: `1px solid ${colors.borderLight}`,
            fontSize: 11,
            fontWeight: 600,
            color: colors.textMuted,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}>
            选择数据分组
          </div>

          {/* Group options */}
          {groups.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: 12, color: colors.textMuted, textAlign: 'center' }}>
              暂无可用分组
            </div>
          ) : (
            groups.map((g) => (
              <DropdownItem
                key={g.id}
                label={g.name}
                sublabel={g.description ?? undefined}
                count={g.table_count}
                isSelected={selectedGroupId === g.id}
                onClick={() => handleSelect(g.id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}


interface DropdownItemProps {
  label: string
  sublabel?: string
  count?: number
  isSelected: boolean
  showCount?: boolean
  onClick: () => void
}

function DropdownItem({ label, sublabel, count, isSelected, showCount = true, onClick }: DropdownItemProps) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '7px 12px',
        cursor: 'pointer',
        background: isSelected ? colors.pillBg : hovered ? colors.hoverBg : 'transparent',
        transition: 'background 0.1s ease',
      }}
    >
      {/* Selection indicator */}
      <div style={{
        width: 14,
        height: 14,
        borderRadius: '50%',
        border: isSelected ? `2px solid ${colors.accent}` : `2px solid ${colors.borderStrong}`,
        background: isSelected ? colors.accent : 'transparent',
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {isSelected && (
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#fff' }} />
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13,
          fontWeight: isSelected ? 600 : 400,
          color: isSelected ? colors.accent : colors.textPrimary,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {label}
        </div>
        {sublabel && (
          <div style={{
            fontSize: 11,
            color: colors.textMuted,
            marginTop: 1,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {sublabel}
          </div>
        )}
      </div>

      {showCount && count !== undefined && (
        <span style={{
          fontSize: 11,
          color: colors.textMuted,
          background: colors.hoverBg,
          borderRadius: radii.sm,
          padding: '1px 5px',
          flexShrink: 0,
        }}>
          {count} 表
        </span>
      )}
    </div>
  )
}
