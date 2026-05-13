import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/apiClient'

const WS_BASE = 'ws://127.0.0.1:8000'
const MAX_BACKOFF_MS = 30_000

export function useNotifications(user) {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const wsRef = useRef(null)
  const retryTimer = useRef(null)
  const retryCount = useRef(0)
  const destroyed = useRef(false)

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get('/api/notifications/')
      setNotifications(res.data)
      setUnreadCount(res.data.filter(n => !n.is_read).length)
    } catch {
      // silently ignore — user may not be logged in yet
    }
  }, [])

  // WebSocket connection with exponential-backoff reconnect.
  // Uses short-lived tickets (POST /api/ws-ticket/) instead of putting the
  // long-lived JWT in the query string, which would expose it in server logs.
  useEffect(() => {
    if (!user) return

    destroyed.current = false

    async function connect() {
      if (destroyed.current) return

      // Step 1: obtain a one-time ticket from the REST API
      let ticket
      try {
        const res = await api.post('/api/ws-ticket/')
        ticket = res.data.ticket
      } catch {
        // Ticket fetch failed (e.g. token expired) — back off and retry
        if (destroyed.current) return
        const delay = Math.min(1000 * 2 ** retryCount.current, MAX_BACKOFF_MS)
        retryCount.current += 1
        retryTimer.current = setTimeout(connect, delay)
        return
      }

      if (destroyed.current) return  // component unmounted while awaiting ticket

      // Step 2: open the WebSocket with the ticket (30-second TTL, single-use)
      const ws = new WebSocket(`${WS_BASE}/ws/notifications/?ticket=${ticket}`)
      wsRef.current = ws

      ws.onmessage = (e) => {
        const notif = JSON.parse(e.data)
        setNotifications(prev => [notif, ...prev])
        setUnreadCount(prev => prev + 1)
      }

      ws.onopen = () => {
        retryCount.current = 0
        // Re-sync any notifications that arrived while we were disconnected
        fetchNotifications()
      }

      ws.onclose = () => {
        if (destroyed.current) return
        // Exponential backoff: 1s, 2s, 4s … capped at 30s
        const delay = Math.min(1000 * 2 ** retryCount.current, MAX_BACKOFF_MS)
        retryCount.current += 1
        retryTimer.current = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      destroyed.current = true
      clearTimeout(retryTimer.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [user, fetchNotifications])

  // Initial fetch on mount (before the WS connection is established)
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
