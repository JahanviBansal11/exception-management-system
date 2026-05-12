import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const SEVERITY_STYLE = {
  success: { borderLeft: '3px solid #22c55e', background: '#f0fdf4' },
  warning: { borderLeft: '3px solid #f59e0b', background: '#fffbeb' },
  danger:  { borderLeft: '3px solid #ef4444', background: '#fef2f2' },
  info:    { borderLeft: '3px solid #3b82f6', background: '#eff6ff' },
}

export function NotificationBell({ notifications, unreadCount, markRead, markAllRead }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()

  // Close on outside click
  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function handleNotifClick(notif) {
    if (!notif.is_read) markRead(notif.id)
    if (notif.action_url) navigate(notif.action_url)
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          position: 'relative', background: 'none', border: 'none',
          cursor: 'pointer', padding: '6px', borderRadius: '6px',
          fontSize: '1.25rem', lineHeight: 1,
        }}
        title="Notifications"
      >
        🔔
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute', top: 0, right: 0,
            background: '#ef4444', color: '#fff',
            borderRadius: '999px', fontSize: '0.65rem',
            minWidth: '16px', height: '16px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '0 3px', fontWeight: 700, lineHeight: 1,
          }}>
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', right: 0, top: '110%', zIndex: 1000,
          width: '360px', maxHeight: '480px', overflowY: 'auto',
          background: '#fff', border: '1px solid #e2e8f0',
          borderRadius: '10px', boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '12px 16px', borderBottom: '1px solid #e2e8f0',
          }}>
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
              Notifications {unreadCount > 0 && <span style={{ color: '#ef4444' }}>({unreadCount})</span>}
            </span>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3b82f6', fontSize: '0.8rem' }}
              >
                Mark all read
              </button>
            )}
          </div>

          {notifications.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
              No notifications
            </div>
          ) : (
            notifications.map(notif => (
              <div
                key={notif.id}
                onClick={() => handleNotifClick(notif)}
                style={{
                  padding: '12px 16px', cursor: 'pointer',
                  borderBottom: '1px solid #f1f5f9',
                  opacity: notif.is_read ? 0.65 : 1,
                  ...(SEVERITY_STYLE[notif.severity] || SEVERITY_STYLE.info),
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                  <span style={{ fontWeight: notif.is_read ? 400 : 600, fontSize: '0.85rem' }}>
                    {notif.title}
                  </span>
                  {!notif.is_read && (
                    <span style={{
                      minWidth: '8px', height: '8px', borderRadius: '50%',
                      background: '#3b82f6', marginTop: '4px', flexShrink: 0,
                    }} />
                  )}
                </div>
                <div style={{ color: '#475569', fontSize: '0.8rem', marginTop: '2px' }}>
                  {notif.message}
                </div>
                <div style={{ color: '#94a3b8', fontSize: '0.72rem', marginTop: '4px' }}>
                  {new Date(notif.created_at).toLocaleString()}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
