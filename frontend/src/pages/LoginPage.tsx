import React, { useState } from 'react'
import { colors, radii, fontFamily, shadows } from '../styles/tokens'
import { useAuth } from '../hooks/useAuth'
import { useNavigate } from 'react-router-dom'
import { LogoIcon } from '../components/Icons'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [emailError, setEmailError] = useState(false)
  const [pwdError, setPwdError] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
    setEmailError(!emailValid)
    setPwdError(!password)
    if (!emailValid || !password) return

    setError('')
    setLoading(true)
    try {
      const user = await login(email, password)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || '登录失败，请检查邮箱和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: colors.pageBg,
        fontFamily,
      }}
    >
      <div
        style={{
          width: 380,
          background: colors.pageBg,
          borderRadius: radii.xxl,
          boxShadow: shadows.card,
          padding: '40px 32px',
          animation: 'fadeIn 0.3s ease',
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <div
            style={{
              width: 36, height: 36,
              background: colors.accent,
              borderRadius: radii.lg,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <LogoIcon width={20} height={20} color="white" />
          </div>
          <span style={{ fontSize: 18, fontWeight: 600, color: colors.textPrimary }}>
            DataLens
          </span>
        </div>

        <h1
          style={{
            fontSize: 22, fontWeight: 600,
            color: 'rgba(0,0,0,0.9)', margin: '4px 0 32px',
          }}
        >
          欢迎回来
        </h1>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 18 }}>
            <label
              style={{ display: 'block', fontSize: 13, fontWeight: 500, color: colors.textSecondary, marginBottom: 6 }}
            >
              邮箱
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setEmailError(false) }}
              placeholder="your@company.com"
              autoComplete="email"
              style={{
                width: '100%', padding: '8px 12px',
                border: `1px solid ${emailError ? colors.errorColor : colors.borderInput}`,
                borderRadius: radii.sm,
                fontSize: 14, fontFamily,
                color: colors.textPrimary,
                background: colors.inputBg,
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.15s ease',
              }}
              onFocus={(e) => (e.target.style.borderColor = colors.accent)}
              onBlur={(e) => (e.target.style.borderColor = emailError ? colors.errorColor : colors.borderInput)}
            />
            {emailError && (
              <div style={{ fontSize: 11, color: colors.errorColor, marginTop: 4 }}>
                请输入有效的邮箱地址
              </div>
            )}
          </div>

          <div style={{ marginBottom: 18 }}>
            <label
              style={{ display: 'block', fontSize: 13, fontWeight: 500, color: colors.textSecondary, marginBottom: 6 }}
            >
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setPwdError(false) }}
              placeholder="输入密码"
              autoComplete="current-password"
              style={{
                width: '100%', padding: '8px 12px',
                border: `1px solid ${pwdError ? colors.errorColor : colors.borderInput}`,
                borderRadius: radii.sm,
                fontSize: 14, fontFamily,
                color: colors.textPrimary,
                background: colors.inputBg,
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.15s ease',
              }}
              onFocus={(e) => (e.target.style.borderColor = colors.accent)}
              onBlur={(e) => (e.target.style.borderColor = pwdError ? colors.errorColor : colors.borderInput)}
            />
            {pwdError && (
              <div style={{ fontSize: 11, color: colors.errorColor, marginTop: 4 }}>
                密码不能为空
              </div>
            )}
          </div>

          {error && (
            <div
              style={{
                fontSize: 12, color: colors.errorColor,
                marginBottom: 14,
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '10px 16px',
              background: loading ? colors.textMuted : colors.accent,
              color: '#fff', border: 'none',
              borderRadius: radii.sm,
              fontSize: 14, fontWeight: 500,
              cursor: loading ? 'default' : 'pointer',
              fontFamily,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (!loading) e.currentTarget.style.background = colors.accentHover
            }}
            onMouseLeave={(e) => {
              if (!loading) e.currentTarget.style.background = colors.accent
            }}
            onMouseDown={(e) => {
              if (!loading) e.currentTarget.style.transform = 'scale(0.95)'
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = 'scale(1)'
            }}
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: colors.textMuted }}>
          没有账号？<a href="#" onClick={(e) => e.preventDefault()} style={{ fontWeight: 500 }}>联系管理员</a>
        </p>
      </div>
    </div>
  )
}
