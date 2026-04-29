import React from 'react'

export function NotificationFeed({ notifications, formatDateTime }) {
  if (!notifications || notifications.length === 0) return null

  return (
    <div className="notifications-feed">
      {notifications.map((item, index) => (
        <div key={item.exception_id != null ? `${item.event_type}-${item.exception_id}-${index}` : index} className={`notification-item ${!item.is_read ? 'unread' : ''}`}>
          <div><strong>{item.title}</strong></div>
          <div className="meta" style={{ marginTop: '2px' }}>{item.message}</div>
          {item.feedback ? <div className="meta" style={{ marginTop: '2px', color: '#1e293b' }}>Feedback: {item.feedback}</div> : null}
          <div className="meta" style={{ marginTop: '4px', fontSize: '0.75rem' }}>{formatDateTime(item.timestamp)}</div>
        </div>
      ))}
    </div>
  )
}
