import React from 'react'
import { useNavigate } from 'react-router-dom'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { BackIcon } from '../Icons'

export interface SideTab<K extends string = string> {
  key: K
  label: string
}

interface AppSideLayoutProps<K extends string = string> {
  tabs: SideTab<K>[]
  activeTab: K
  onChangeTab: (key: K) => void
  title: string
  children: React.ReactNode
  showBackToChat?: boolean
}

const SIDEBAR_WIDTH = 220

export function AppSideLayout<K extends string = string>({
  tabs,
  activeTab,
  onChangeTab,
  title,
  children,
  showBackToChat = true,
}: AppSideLayoutProps<K>) {
  const navigate = useNavigate()

  const menuItemStyle = (active: boolean): React.CSSProperties => ({
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '9px 14px', margin: '0 12px',
    borderRadius: radii.sm, fontSize: 14,
    fontWeight: active ? 600 : 400,
    color: active ? colors.accent : colors.textSecondary,
    background: active ? 'rgba(0,117,222,0.08)' : 'transparent',
    cursor: 'pointer', border: 'none',
    fontFamily, transition: 'all 0.15s ease',
    textAlign: 'left',
  })

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#f0efee', fontFamily }}>
      <aside
        style={{
          width: SIDEBAR_WIDTH, background: '#fff',
          borderRight: `1px solid ${colors.borderLight}`,
          display: 'flex', flexDirection: 'column', flexShrink: 0,
          height: '100vh', overflowY: 'auto',
        }}
      >
        <div
          onClick={() => navigate('/')}
          style={{
            padding: '16px 20px',
            display: 'flex', alignItems: 'center', gap: 10,
            cursor: 'pointer',
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <img
            src="/logo.png"
            alt="logo"
            style={{ width: 28, height: 28, borderRadius: radii.lg, objectFit: 'contain' }}
          />
          <span style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary }}>
            DataLens
          </span>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 8, flex: 1 }}>
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => onChangeTab(t.key)}
              style={menuItemStyle(activeTab === t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {showBackToChat && (
          <>
            <div style={{ margin: '0 14px', borderTop: `1px solid ${colors.borderLight}` }} />
            <div style={{ padding: '14px 20px' }}>
              <button
                onClick={() => navigate('/')}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  fontSize: 14, fontWeight: 500, color: colors.textSecondary,
                  textDecoration: 'none', background: 'transparent',
                  border: 'none', padding: 0, cursor: 'pointer', fontFamily,
                }}
              >
                <BackIcon width={15} height={15} color={colors.textSecondary} />
                返回
              </button>
            </div>
          </>
        )}
      </aside>

      <main style={{ flex: 1, padding: '24px', overflow: 'auto', height: '100vh' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <h1 style={{
            fontSize: 22, fontWeight: 600,
            color: colors.textPrimary, marginTop: 0, marginBottom: 20,
          }}>
            {title}
          </h1>
          {children}
        </div>
      </main>
    </div>
  )
}
