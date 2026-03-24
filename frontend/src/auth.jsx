import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, clearTokens, getAccessToken, setTokens } from './api'
import { AuthContext } from './AuthContext'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    const response = await api.get('/api/auth/me/')
    setUser(response.data)
    return response.data
  }, [])

  const bootstrap = useCallback(async () => {
    if (!getAccessToken()) {
      setLoading(false)
      return
    }

    try {
      await fetchMe()
    } catch {
      clearTokens()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [fetchMe])

  const login = useCallback(async (username, password) => {
    const tokenResponse = await api.post('/api/auth/token/', { username, password })
    setTokens(tokenResponse.data.access, tokenResponse.data.refresh)
    return fetchMe()
  }, [fetchMe])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [])

  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshUser: fetchMe }),
    [user, loading, login, logout, fetchMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
