import { api } from './api'
import type { LoginRequest, TokenResponse, User } from '../types/auth'

export const authService = {
  async login(body: LoginRequest): Promise<TokenResponse> {
    const res = await api.post<TokenResponse>('/auth/login', body)
    return res.data
  },

  async logout(): Promise<void> {
    try {
      await api.post('/auth/logout')
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  },

  async getProfile(): Promise<User> {
    const res = await api.get<User>('/profile')
    return res.data
  },
}
