import React from 'react'

export function DashboardStats({ summary, activeKpi, setActiveKpi }) {
  if (!summary) return null

  const KPI_CONFIG = [
    { key: 'my_queue_total', label: 'My Queue' },
    { key: 'pending_action', label: 'Pending Action' },
    { key: 'overdue_approval', label: 'Overdue Approval' },
    { key: 'approved', label: 'Approved' },
  ]

  return (
    <div className="stats-grid">
      {KPI_CONFIG.map((kpi) => {
        const val = summary[kpi.key] || 0
        const isOverdue = kpi.key === 'overdue_approval' && val > 0
        const isActive = activeKpi === kpi.key
        return (
          <div
            key={kpi.key}
            className={`stat-card ${isOverdue ? 'danger' : ''} ${isActive ? 'active' : ''}`}
            onClick={() => setActiveKpi(isActive ? '' : kpi.key)}
            style={{ cursor: 'pointer' }}
          >
            <div className="stat-value">{val}</div>
            <div className="stat-label">{kpi.label}</div>
          </div>
        )
      })}
    </div>
  )
}
