import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Session } from '../../types/chat'
import type { User } from '../../types/auth'
import { colors, radii, fontFamily, shadows, getAvatarColor } from '../../styles/tokens'
import {
  ChevronsLeftIcon,
  ChevronsRightIcon,
  PencilIcon,
  MoreIcon,
  SettingsIcon,
  ShieldIcon,
  LogOutIcon,
  RenameIcon,
  TrashIcon,
} from '../Icons'
import { ConfirmDialog } from '../ui/ConfirmDialog'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  sessions: Session[]
  activeSessionId: string | null
  onSelectSession: (id: string) => void
  onNewSession: () => void
  onRenameSession: (id: string, title: string) => void
  onDeleteSession: (id: string) => void
  onBatchDeleteSessions: (ids: string[]) => void
  user: User | null
  onLogout: () => void
  onOpenSettings: () => void
  isTemporarySession: boolean
}

function groupSessions(sessions: Session[]) {
  const now = new Date()
  const today: Session[] = []
  const yesterday: Session[] = []
  const older: Session[] = []

  for (const s of sessions) {
    const d = new Date(s.updated_at)
    const diff = Math.floor((now.getTime() - d.getTime()) / 86400000)
    if (diff === 0) today.push(s)
    else if (diff === 1) yesterday.push(s)
    else older.push(s)
  }
  return { today, yesterday, older }
}

const PAGE_SIZE = 50

const iconBtnStyle: React.CSSProperties = {
  border: 'none', background: 'transparent', cursor: 'pointer',
  padding: '6px', borderRadius: radii.md,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  transition: 'background 0.15s ease',
}

const menuItemBase: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8,
  width: '100%', padding: '8px 12px',
  border: 'none', background: 'transparent',
  cursor: 'pointer', fontSize: 14,
  fontFamily, textAlign: 'left',
  borderRadius: radii.md,
  transition: 'background 0.15s ease',
}

export function Sidebar({
  collapsed,
  onToggle,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onRenameSession,
  onDeleteSession,
  onBatchDeleteSessions,
  user,
  onLogout,
  onOpenSettings,
}: SidebarProps) {
  const { today, yesterday, older } = groupSessions(sessions)
  const allSessionIds = [...today, ...yesterday, ...older].map((s) => s.id)

  const [menuOpen, setMenuOpen] = useState(false)
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null)
  const [rowHoverId, setRowHoverId] = useState<string | null>(null)
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<Session | null>(null)

  // Batch mode
  const [isBatchMode, setIsBatchMode] = useState(false)
  const [selectedSessionIds, setSelectedSessionIds] = useState<Set<string>>(new Set())
  const [batchDeleteConfirmOpen, setBatchDeleteConfirmOpen] = useState(false)

  const navigate = useNavigate()
  const isAdmin = user?.roles.includes('admin')
  const menuRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setHoveredSessionId(null)
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => { setMenuOpen(false) }, [collapsed])

  useEffect(() => {
    const sentinel = sentinelRef.current
    const total = today.length + yesterday.length + older.length
    if (!sentinel || visibleCount >= total) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisibleCount((c) => Math.min(c + PAGE_SIZE, total))
      },
      { threshold: 0, rootMargin: '80px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [visibleCount, today.length, yesterday.length, older.length])

  const handleEnterBatchMode = () => {
    setIsBatchMode(true)
    setSelectedSessionIds(new Set())
    setHoveredSessionId(null)
  }

  const handleExitBatchMode = () => {
    setIsBatchMode(false)
    setSelectedSessionIds(new Set())
  }

  const handleToggleSession = (id: string) => {
    setSelectedSessionIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleSelectAll = () => {
    if (selectedSessionIds.size === allSessionIds.length) {
      setSelectedSessionIds(new Set())
    } else {
      setSelectedSessionIds(new Set(allSessionIds))
    }
  }

  const allSelected = allSessionIds.length > 0 && selectedSessionIds.size === allSessionIds.length

  const totalCount = today.length + yesterday.length + older.length
  let _rem = visibleCount
  const visibleToday = today.slice(0, _rem); _rem = Math.max(0, _rem - today.length)
  const visibleYesterday = yesterday.slice(0, _rem); _rem = Math.max(0, _rem - yesterday.length)
  const visibleOlder = older.slice(0, _rem)
  const hasMore = visibleCount < totalCount

  return (
    <aside
      ref={menuRef}
      onClick={() => setHoveredSessionId(null)}
      style={{
        width: collapsed ? 56 : 256,
        minWidth: collapsed ? 56 : 256,
        overflow: 'hidden',
        background: colors.sidebarBg,
        borderRight: `1px solid ${colors.borderLight}`,
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.25s ease, min-width 0.25s ease',
        height: '100vh',
        fontFamily,
        flexShrink: 0,
        position: 'relative',
      }}
    >
      <style>{`
        @keyframes batchPanelIn {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '14px 0 10px 14px', flexShrink: 0 }}>
        <div
          onClick={onNewSession}
          style={{ cursor: 'pointer', padding: '4px', borderRadius: radii.md, transition: 'background 0.15s ease', flexShrink: 0 }}
          onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <img src="/logo.png" alt="logo" style={{ width: 28, height: 28, borderRadius: radii.lg, objectFit: 'contain', display: 'block' }} />
        </div>
        <div style={{ flex: 1 }} />
        <button
          onClick={onToggle}
          style={{ ...iconBtnStyle, marginRight: 10, display: collapsed ? 'none' : 'flex' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <ChevronsLeftIcon width={16} height={16} color={colors.textSecondary} />
        </button>
      </div>

      {/* ── New session button ── */}
      <div style={{ padding: '0 8px 4px 8px', flexShrink: 0 }}>
        <button
          onClick={onNewSession}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            width: collapsed ? 'auto' : '100%',
            padding: '8px 8px', marginLeft: 0,
            border: 'none', borderRadius: radii.md,
            background: 'transparent', cursor: 'pointer',
            fontSize: 14, fontWeight: 700,
            color: colors.textPrimary, fontFamily,
            textAlign: 'left', transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.08)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <PencilIcon width={15} height={15} color="#000000" />
          <span style={{ opacity: collapsed ? 0 : 1, maxWidth: collapsed ? 0 : 200, overflow: 'hidden', transition: 'opacity 0.15s ease, max-width 0.25s ease', whiteSpace: 'nowrap' }}>
            新会话
          </span>
        </button>
      </div>

      {/* ── Session list ── */}
      <div
        style={{
          flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '0 8px',
          opacity: collapsed ? 0 : 1,
          transition: 'opacity 0.15s ease',
          pointerEvents: collapsed ? 'none' : 'auto',
          paddingBottom: isBatchMode ? 96 : 0,
        }}
      >
        {[
          { label: '今天', items: visibleToday },
          { label: '昨天', items: visibleYesterday },
          { label: '更早', items: visibleOlder },
        ].map(({ label, items }) =>
          items.length > 0 ? (
            <div key={label}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 8px 6px' }}>
                <span style={{ fontSize: 11, fontWeight: 300, color: colors.textMuted, flexShrink: 0 }}>{label}</span>
                <div style={{ flex: 1, height: 1, background: colors.borderLight }} />
              </div>

              {items.map((s) => {
                const isSelected = selectedSessionIds.has(s.id)
                const isHovered = rowHoverId === s.id

                return (
                  <div
                    key={s.id}
                    onMouseEnter={() => setRowHoverId(s.id)}
                    onMouseLeave={() => setRowHoverId(null)}
                    onClick={isBatchMode ? (e) => { e.stopPropagation(); handleToggleSession(s.id) } : undefined}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      width: '100%',
                      borderRadius: '10px',
                      marginBottom: 2,
                      background: isBatchMode
                        ? (isHovered ? colors.hoverBg : 'transparent')
                        : (s.id === activeSessionId ? colors.activeBg : (isHovered ? colors.hoverBg : 'transparent')),
                      transition: 'background 0.15s ease',
                      position: 'relative',
                      cursor: isBatchMode ? 'pointer' : 'default',
                    }}
                  >
                    {/* Checkbox — always rendered, width animates in/out for smooth shift */}
                    <div
                      style={{
                        width: isBatchMode ? 12 : 0,
                        marginLeft: isBatchMode ? 8 : 0,
                        opacity: isBatchMode ? 1 : 0,
                        overflow: 'hidden',
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'width 0.2s ease, margin-left 0.2s ease, opacity 0.18s ease',
                      }}
                    >
                      <div
                        style={{
                          width: 12,
                          height: 12,
                          borderRadius: 3,
                          border: isSelected
                            ? `1.5px solid ${colors.accent}`
                            : `1.5px solid ${colors.borderStrong}`,
                          background: isSelected ? colors.accent : 'transparent',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          transition: 'background 0.12s ease, border-color 0.12s ease',
                          flexShrink: 0,
                        }}
                      >
                        {isSelected && (
                          <svg width="7" height="7" viewBox="0 0 7 7" fill="none">
                            <path d="M1 3.5L2.8 5.2L6 1.5" stroke="#fff" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                      </div>
                    </div>

                    {/* Normal mode: session select button — hidden during rename */}
                    {!isBatchMode && (
                      <button
                        onClick={() => onSelectSession(s.id)}
                        style={{
                          display: renamingSessionId === s.id ? 'none' : 'flex',
                          alignItems: 'center',
                          flex: 1,
                          padding: '7px 8px',
                          border: 'none',
                          borderRadius: '10px',
                          background: 'transparent',
                          cursor: 'pointer',
                          fontSize: 14,
                          fontWeight: s.id === activeSessionId ? 500 : 400,
                          color: colors.textPrimary,
                          fontFamily,
                          textAlign: 'left',
                          textOverflow: 'ellipsis',
                          overflow: 'hidden',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {s.title || '未命名对话'}
                        </span>
                      </button>
                    )}

                    {/* Batch mode: plain title text */}
                    {isBatchMode && (
                      <span
                        style={{
                          flex: 1,
                          padding: '8px 10px',
                          fontSize: 14,
                          color: colors.textPrimary,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {s.title || '未命名对话'}
                      </span>
                    )}

                    {/* "..." more button — shown on hover in normal mode only */}
                    {!isBatchMode && renamingSessionId !== s.id && (isHovered || hoveredSessionId === s.id) && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setHoveredSessionId(hoveredSessionId === s.id ? null : s.id)
                        }}
                        style={{
                          border: 'none', background: 'transparent', cursor: 'pointer',
                          color: colors.textMuted, display: 'flex', alignItems: 'center',
                          justifyContent: 'center', padding: '4px 6px',
                          borderRadius: radii.sm, flexShrink: 0,
                        }}
                      >
                        <MoreIcon width={15} height={15} color={colors.textMuted} />
                      </button>
                    )}

                    {/* Context menu dropdown */}
                    {!isBatchMode && hoveredSessionId === s.id && renamingSessionId !== s.id && (
                      <div
                        style={{
                          position: 'absolute', right: 4, top: '100%', zIndex: 200,
                          background: colors.pageBg, border: `1px solid ${colors.border}`,
                          borderRadius: radii.md, boxShadow: shadows.card,
                          padding: '4px', minWidth: 100,
                        }}
                      >
                        {/* Rename */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setRenamingSessionId(s.id)
                            setRenameValue(s.title || '')
                            setHoveredSessionId(null)
                          }}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            width: '100%', padding: '7px 10px',
                            border: 'none', background: 'transparent',
                            cursor: 'pointer', fontSize: 13, color: colors.textPrimary,
                            fontFamily, borderRadius: radii.sm, transition: 'background 0.1s',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          <RenameIcon width={13} height={13} color={colors.textSecondary} />
                          重命名
                        </button>

                        {/* Batch */}
                        <button
                          onClick={(e) => { e.stopPropagation(); handleEnterBatchMode() }}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            width: '100%', padding: '7px 10px',
                            border: 'none', background: 'transparent',
                            cursor: 'pointer', fontSize: 13, color: colors.textPrimary,
                            fontFamily, borderRadius: radii.sm, transition: 'background 0.1s',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          <svg
                            width="14" height="14" viewBox="0 0 16 16" fill="none"
                            stroke={colors.textSecondary} strokeLinecap="round"
                            strokeOpacity=".95" strokeWidth="1.5"
                            style={{ flexShrink: 0 }}
                          >
                            <path d="M7.576 2.423h7M7.576 7.523h7M7.576 12.723h7" />
                            <path strokeLinejoin="round" d="M1.6 2.75 2.733 3.9 5 1.6M1.6 6.95 2.733 8.1 5 5.8M1.6 12.25l1.133 1.15L5 11.1" />
                          </svg>
                          批量
                        </button>

                        {/* Delete — no confirm dialog */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setDeleteTarget(s)
                            setHoveredSessionId(null)
                          }}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            width: '100%', padding: '7px 10px',
                            border: 'none', background: 'transparent',
                            cursor: 'pointer', fontSize: 13, color: colors.errorColor,
                            fontFamily, borderRadius: radii.sm, transition: 'background 0.1s',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          <TrashIcon width={13} height={13} color={colors.errorColor} />
                          删除
                        </button>
                      </div>
                    )}

                    {/* Rename input */}
                    {!isBatchMode && renamingSessionId === s.id && (
                      <input
                        type="text"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            if (renameValue.trim()) onRenameSession(s.id, renameValue.trim())
                            setRenamingSessionId(null)
                          } else if (e.key === 'Escape') {
                            setRenamingSessionId(null)
                          }
                        }}
                        onBlur={() => {
                          if (renameValue.trim()) onRenameSession(s.id, renameValue.trim())
                          setRenamingSessionId(null)
                        }}
                        onClick={(e) => e.stopPropagation()}
                        autoFocus
                        style={{
                          flex: 1, padding: '7px 10px',
                          border: `1px solid ${colors.accent}`,
                          borderRadius: radii.sm, background: colors.pageBg,
                          fontSize: 14, fontFamily, color: colors.textPrimary,
                          outline: 'none', marginRight: 8,
                        }}
                      />
                    )}
                  </div>
                )
              })}
            </div>
          ) : null
        )}
        {hasMore && <div ref={sentinelRef} style={{ height: 8 }} />}
      </div>

      {/* ── Bottom section ── */}
      <button
        onClick={onToggle}
        style={{ ...iconBtnStyle, alignSelf: 'center', marginBottom: 8, flexShrink: 0, display: collapsed ? 'flex' : 'none' }}
        onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <ChevronsRightIcon width={16} height={16} color={colors.textSecondary} />
      </button>

      {user && (
        <>
          <div style={{ margin: '0 12px', borderTop: `1px solid ${colors.borderLight}`, flexShrink: 0, opacity: collapsed ? 0 : 1, transition: 'opacity 0.15s ease' }} />

          <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10, position: 'relative', flexShrink: 0 }}>
            <div
              onClick={() => setMenuOpen(!menuOpen)}
              style={{
                width: 32, height: 32, borderRadius: '50%',
                background: getAvatarColor(user.full_name || user.email),
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#fff', fontSize: 13, fontWeight: 600,
                flexShrink: 0, cursor: 'pointer', transition: 'box-shadow 0.15s ease',
              }}
              onMouseEnter={(e) => { const bg = getAvatarColor(user.full_name || user.email); e.currentTarget.style.boxShadow = `0 0 0 3px ${bg}55` }}
              onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
            >
              {(user.full_name || user.email)[0].toUpperCase()}
            </div>

            <div style={{ flex: 1, minWidth: 0, overflow: 'hidden', opacity: collapsed ? 0 : 1, transition: 'opacity 0.15s ease', pointerEvents: collapsed ? 'none' : 'auto' }}>
              <div style={{ fontSize: 14, fontWeight: 500, color: colors.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.full_name || user.email}
              </div>
              <div style={{ fontSize: 12, color: colors.textMuted }}>{user.roles.join(', ')}</div>
            </div>

            {menuOpen && (
              <div
                style={{
                  position: collapsed ? 'fixed' : 'absolute',
                  left: collapsed ? 64 : 14, bottom: collapsed ? 16 : 56,
                  width: 200, background: colors.pageBg,
                  border: `1px solid ${colors.border}`, borderRadius: radii.xxl,
                  boxShadow: shadows.card, padding: '6px', zIndex: 200,
                }}
              >
                <button
                  onClick={() => { setMenuOpen(false); onOpenSettings() }}
                  style={{ ...menuItemBase, color: colors.textPrimary }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <SettingsIcon width={15} height={15} color={colors.textSecondary} />
                  设置
                </button>
                {isAdmin && (
                  <button
                    onClick={() => { setMenuOpen(false); navigate('/admin') }}
                    style={{ ...menuItemBase, color: colors.textPrimary }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <ShieldIcon width={15} height={15} color={colors.textSecondary} />
                    管理后台
                  </button>
                )}
                <div style={{ height: 0, borderTop: `1px solid ${colors.borderLight}`, margin: '4px 0' }} />
                <button
                  onClick={() => { setMenuOpen(false); onLogout(); navigate('/login') }}
                  style={{ ...menuItemBase, color: colors.errorColor }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <LogOutIcon width={15} height={15} color={colors.errorColor} />
                  退出登录
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Batch mode panel — slides up from bottom ── */}
      {isBatchMode && !collapsed && (
        <div
          style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: colors.sidebarBg,
            borderTop: `1px solid ${colors.borderLight}`,
            padding: '12px 14px 16px',
            zIndex: 50,
            animation: 'batchPanelIn 0.18s ease',
          }}
        >
          {/* Row 1: 全选 + count */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <button
              onClick={handleSelectAll}
              style={{
                border: 'none', background: 'transparent', cursor: 'pointer',
                fontSize: 13, fontWeight: 500,
                color: allSelected ? colors.accent : colors.textSecondary,
                fontFamily, padding: '2px 0', transition: 'color 0.15s ease',
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              <div
                style={{
                  width: 12, height: 12, borderRadius: 3, flexShrink: 0,
                  border: allSelected ? `1.5px solid ${colors.accent}` : `1.5px solid ${colors.borderStrong}`,
                  background: allSelected ? colors.accent : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'background 0.12s ease, border-color 0.12s ease',
                }}
              >
                {allSelected && (
                  <svg width="7" height="7" viewBox="0 0 7 7" fill="none">
                    <path d="M1 3.5L2.8 5.2L6 1.5" stroke="#fff" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
              {allSelected ? '取消全选' : '全选'}
            </button>
            <span style={{ fontSize: 13, color: colors.textSecondary, fontWeight: 500 }}>
              已选 {selectedSessionIds.size} 条
            </span>
          </div>

          {/* Row 2: 取消 + 删除 */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={handleExitBatchMode}
              style={{
                flex: 1, padding: '7px 0',
                border: `1px solid ${colors.borderStrong}`,
                borderRadius: radii.md, background: 'transparent',
                cursor: 'pointer', fontSize: 13, fontWeight: 500,
                color: colors.textSecondary, fontFamily,
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              取消
            </button>
            <button
              onClick={() => selectedSessionIds.size > 0 && setBatchDeleteConfirmOpen(true)}
              style={{
                flex: 1, padding: '7px 0', border: 'none',
                borderRadius: radii.md,
                background: selectedSessionIds.size > 0 ? colors.errorColor : colors.borderLight,
                cursor: selectedSessionIds.size > 0 ? 'pointer' : 'default',
                fontSize: 13, fontWeight: 500,
                color: selectedSessionIds.size > 0 ? '#fff' : colors.textMuted,
                fontFamily, transition: 'opacity 0.15s ease',
              }}
              onMouseEnter={(e) => { if (selectedSessionIds.size > 0) e.currentTarget.style.opacity = '0.82' }}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
            >
              删除
            </button>
          </div>
        </div>
      )}

      {/* Batch delete confirm */}
      <ConfirmDialog
        open={batchDeleteConfirmOpen}
        title="批量删除对话"
        message={`确认删除选中的 ${selectedSessionIds.size} 条对话历史吗？删除后无法恢复`}
        confirmText="确认删除"
        cancelText="取消"
        onConfirm={() => {
          onBatchDeleteSessions(Array.from(selectedSessionIds))
          setBatchDeleteConfirmOpen(false)
          handleExitBatchMode()
        }}
        onCancel={() => setBatchDeleteConfirmOpen(false)}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        title="删除对话"
        message={`确认删除“${deleteTarget?.title || '未命名对话'}”吗？删除后无法恢复`}
        confirmText="确认删除"
        cancelText="取消"
        onConfirm={() => {
          if (deleteTarget) onDeleteSession(deleteTarget.id)
          setDeleteTarget(null)
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </aside>
  )
}
