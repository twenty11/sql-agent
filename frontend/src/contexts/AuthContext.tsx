import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { User } from '../types/auth'
import { authService } from '../services/auth'

interface AuthState {
  user: User | null
  loading: boolean
  isLoggedIn: boolean
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  refreshProfile: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    isLoggedIn: false,
  })

  const fetchProfile = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setState({ user: null, loading: false, isLoggedIn: false })
      return
    }
    try {
      const user = await authService.getProfile()
      setState({ user, loading: false, isLoggedIn: true })
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      setState({ user: null, loading: false, isLoggedIn: false })
    }
  }, [])

  useEffect(() => {
    fetchProfile()
  }, [fetchProfile])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authService.login({ email, password })
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    const user = await authService.getProfile()
    setState({ user, loading: false, isLoggedIn: true })
    return user
  }, [])

  const logout = useCallback(async () => {
    await authService.logout()
    setState({ user: null, loading: false, isLoggedIn: false })
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout, refreshProfile: fetchProfile }),
    [state, login, logout, fetchProfile],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
