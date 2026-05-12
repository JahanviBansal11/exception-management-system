import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/apiClient'

const WS_BASE = 'ws://127.0.0.1:8000'

export function useNotifications(user) {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const wsRef = useRef(null)

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get('/api/notifications/')
      setNotifications(res.data)
      setUnreadCount(res.data.filter(n => !n.is_read).length)
    } catch {
      // silently ignore — user may not be logged in yet
    }
  }, [])

  // WebSocket connection
  useEffect(() => {
    if (!user) return

    const token = localStorage.getItem('access_token')
    const ws = new WebSocket(`${WS_BASE}/ws/notifications/?token=${token}`)
    wsRef.current = ws

    ws.onmessage = (e) => {
      const notif = JSON.parse(e.data)
      setNotifications(prev => [notif, ...prev])
      setUnreadCount(prev => prev + 1)
    }

    ws.onclose = () => {
      // Reconnect after 5s if closed unexpectedly
      setTimeout(() => {
        if (wsRef.current === ws) wsRef.current = null
      }, 5000)
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [user])

  // Initial fetch on mount
  useEffect(() => {
    if (user) fetchNotifications()
  }, [user, fetchNotifications])

  const markRead = useCallback(async (id) => {
    try {
      const res = await api.patch(`/api/notifications/${id}/read/`)
      setNotifications(prev => prev.map(n => n.id === id ? res.data : n))
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch { /* ignore */ }
  }, [])

  const markAllRead = useCallback(async () => {
    try {
      await api.post('/api/notifications/mark-all-read/')
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch { /* ignore */ }
  }, [])

  return { notifications, unreadCount, markRead, markAllRead, refresh: fetchNotifications }
}
