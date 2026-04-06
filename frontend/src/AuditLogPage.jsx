import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { api } from './api'
import { useAuth } from './useAuth.js'

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear())} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatDateTimeWithSeconds(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear())} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

const ACTION_LABELS = {
  SUBMIT: 'Submitted',
  APPROVE: 'Approved',
  REJECT: 'Rejected',
  CLOSE: 'Closed',
  EXPIRE: 'Expired',
  REMIND: 'Reminder Sent',
  ESCALATE: 'Escalated',
  UPDATE: 'Updated',
}

function getAuditActionLabel(actionType) {
  return ACTION_LABELS[actionType] || actionType || 'Updated'
}

function getAuditSummary(log) {
  const details = log?.details || {}
  const summary = []

  if (details.message) {
    summary.push(details.message)
  }

  if (details.feedback) {
    summary.push(`Feedback: ${details.feedback}`)
  }

  if (details.notes) {
    summary.push(`Notes: ${details.notes}`)
  }

  if (details.decision) {
    summary.push(`Decision: ${String(details.decision)}`)
  }

  if (details.risk_rating) {
    summary.push(`Risk Rating: ${String(details.risk_rating)}`)
  }

  if (Array.isArray(details.changed_fields) && details.changed_fields.length > 0) {
    summary.push(`Updated Fields: ${details.changed_fields.join(', ')}`)
  }

  if (details.end_date_change) {
    const fromValue = details.previous_end_date ? formatDateTime(details.previous_end_date) : '—'
    const toValue = details.new_end_date ? formatDateTime(details.new_end_date) : '—'
    summary.push(`End Date: ${fromValue} → ${toValue}`)
  }

  return summary.slice(0, 3)
}

export default function AuditLogPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [view, setView] = useState('list') // 'list' or 'detail'
  const [selectedExceptionId, setSelectedExceptionId] = useState(null)

  // List view state
  const [exceptions, setExceptions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sortBy, setSortBy] = useState('latest')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [totalCount, setTotalCount] = useState(0)

  // Detail view state
  const [detailLogs, setDetailLogs] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [selectedExceptionDetail, setSelectedExceptionDetail] = useState(null)

  const loadExceptionsList = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
        limit: pageSize,
        offset: page * pageSize,
      })

      const response = await api.get(`/api/security/audit-list/?${params.toString()}`)
      setExceptions(response.data.results || [])
      setTotalCount(response.data.count || 0)
    } catch (err) {
      const status = err?.response?.status
      if (status === 403) {
        setError('You do not have permission to view audit logs.')
      } else {
        setError('Failed to load exceptions list.')
      }
      setExceptions([])
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, sortBy])

  const loadExceptionDetail = useCallback(async (exceptionId) => {
    setDetailLoading(true)
    setDetailError('')
    try {
      const response = await api.get(`/api/exceptions/${exceptionId}/`)
      setSelectedExceptionDetail(response.data)

      const auditResponse = await api.get(`/api/exceptions/${exceptionId}/audit_logs/?limit=100`)
      setDetailLogs(auditResponse.data.results || [])
    } catch (err) {
      setDetailError('Failed to load exception details.')
      setSelectedExceptionDetail(null)
      setDetailLogs([])
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    loadExceptionsList()
  }, [loadExceptionsList])

  useEffect(() => {
    setPage(0)
  }, [sortBy, pageSize])

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  const handleViewDetail = (exceptionId) => {
    setSelectedExceptionId(exceptionId)
    loadExceptionDetail(exceptionId)
    setView('detail')
    // Push to browser history so back button works
    window.history.pushState({ view: 'detail', exceptionId }, '', window.location.href)
  }

  const handleBack = () => {
    setView('list')
    setSelectedExceptionId(null)
    setSelectedExceptionDetail(null)
    setDetailLogs([])
    // Use browser back if available, otherwise stay on list
    if (window.history.length > 1) {
      window.history.back()
    }
  }

  // LIST VIEW
  if (view === 'list') {
    return (
      <div className="shell">
        <div className="shell-header">
          <div>
            <h2>Audit Log</h2>
            <div className="meta">
              Security Team - Master Audit Trail
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={() => navigate('/dashboard')}>
              ← Back to Dashboard
            </button>
            <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={logout}>
              Logout
            </button>
          </div>
        </div>

        <div className="panel" style={{ marginBottom: '20px' }}>
          <div className="panel-header">
            <h3>Sort & Display Options</h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
            <div>
              <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Sort By</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                style={{ width: '100%' }}
              >
                <option value="latest">Latest to Oldest (ID)</option>
                <option value="oldest">Oldest to Latest (ID)</option>
                <option value="id_desc">ID: High to Low</option>
                <option value="id_asc">ID: Low to High</option>
                <option value="status_asc">Status: A-Z</option>
                <option value="status_desc">Status: Z-A</option>
                <option value="risk_desc">Risk Rating: High to Low</option>
                <option value="risk_asc">Risk Rating: Low to High</option>
              </select>
            </div>

            <div>
              <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Page Size</label>
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                style={{ width: '100%' }}
              >
                <option value={10}>10 per page</option>
                <option value={25}>25 per page</option>
                <option value={50}>50 per page</option>
                <option value={100}>100 per page</option>
              </select>
            </div>

            <div>
              <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Total</label>
              <div className="meta">
                {totalCount} exception{totalCount !== 1 ? 's' : ''} | Page {Math.min(page + 1, totalPages)} of {totalPages}
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div style={{ margin: '0 1.5rem', padding: '0.75rem 1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.375rem', color: '#991b1b', fontSize: '0.875rem' }}>
            {error}
          </div>
        )}

        <div className="panel">
          {loading ? (
            <div className="meta" style={{ padding: '1rem' }}>Loading exceptions...</div>
          ) : exceptions.length === 0 ? (
            <div className="meta" style={{ padding: '1rem' }}>No exceptions found.</div>
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>ID</th>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>Description</th>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>Risk</th>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>Status</th>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>Last Action</th>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>Performed By</th>
                      <th style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold' }}>View</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exceptions.map((exc) => (
                      <tr key={exc.id} style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: '#fff' }}>
                        <td style={{ padding: '10px', fontWeight: 'bold' }}>#{exc.id}</td>
                        <td style={{ padding: '10px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {exc.short_description || '—'}
                        </td>
                        <td style={{ padding: '10px' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '3px',
                            fontSize: '0.75rem',
                            fontWeight: 'bold',
                            backgroundColor: exc.risk_rating === 'High' ? '#fee2e2' : exc.risk_rating === 'Medium' ? '#fef3c7' : '#dbeafe',
                            color: exc.risk_rating === 'High' ? '#991b1b' : exc.risk_rating === 'Medium' ? '#92400e' : '#1e40af',
                          }}>
                            {exc.risk_rating || '—'}
                          </span>
                        </td>
                        <td style={{ padding: '10px' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '3px',
                            fontSize: '0.75rem',
                            backgroundColor: '#e0e7ff',
                            color: '#3730a3',
                          }}>
                            {exc.status || '—'}
                          </span>
                        </td>
                        <td style={{ padding: '10px', fontSize: '0.85rem' }}>
                          {exc.last_action ? getAuditActionLabel(exc.last_action) : '—'}
                        </td>
                        <td style={{ padding: '10px', fontSize: '0.85rem' }}>
                          {exc.performed_by || '—'}
                        </td>
                        <td style={{ padding: '10px', textAlign: 'center' }}>
                          <button
                            className="btn btn-secondary"
                            style={{ width: 'auto', fontSize: '0.85rem' }}
                            onClick={() => handleViewDetail(exc.id)}
                          >
                            → View Timeline
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', padding: '0 1rem' }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  style={{ width: 'auto' }}
                >
                  ← Previous
                </button>
                <span className="meta">
                  Page {Math.min(page + 1, totalPages)} of {totalPages}
                </span>
                <button
                  className="btn btn-secondary"
                  onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                  disabled={page >= totalPages - 1}
                  style={{ width: 'auto' }}
                >
                  Next →
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  // DETAIL VIEW
  return (
    <div className="shell">
      <div className="shell-header">
        <div>
          <h2>Audit Timeline - Exception #{selectedExceptionId}</h2>
          <div className="meta">
            Detailed audit trail for this exception
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={handleBack}>
            ← Back to Exceptions List
          </button>
          <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={logout}>
            Logout
          </button>
        </div>
      </div>

      {detailError && (
        <div style={{ margin: '0 1.5rem', padding: '0.75rem 1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.375rem', color: '#991b1b', fontSize: '0.875rem' }}>
          {detailError}
        </div>
      )}

      {selectedExceptionDetail && (
        <div className="panel" style={{ marginBottom: '20px' }}>
          <div className="panel-header">
            <h3>Exception Details</h3>
          </div>

          <div className="detail-grid" style={{ padding: '1rem' }}>
            <div><strong>Exception ID:</strong> #{selectedExceptionDetail.id}</div>
            <div><strong>Short Description:</strong> {selectedExceptionDetail.short_description}</div>
            <div><strong>Current Status:</strong> {selectedExceptionDetail.status}</div>
            <div><strong>Risk Rating:</strong> {selectedExceptionDetail.risk_rating}</div>
            <div><strong>Created At:</strong> {formatDateTime(selectedExceptionDetail.created_at)}</div>
            {selectedExceptionDetail.approved_at && (
              <div><strong>Approved At:</strong> {formatDateTime(selectedExceptionDetail.approved_at)}</div>
            )}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <h3>Audit Timeline</h3>
          <span className="meta">{detailLogs.length} action{detailLogs.length !== 1 ? 's' : ''}</span>
        </div>

        {detailLoading ? (
          <div className="meta" style={{ padding: '1rem' }}>Loading audit trail...</div>
        ) : detailLogs.length === 0 ? (
          <div className="meta" style={{ padding: '1rem' }}>No audit logs recorded for this exception.</div>
        ) : (
          <div className="checkpoint-list" style={{ padding: '1rem' }}>
            {detailLogs.map((log) => (
              <div key={log.id} className="checkpoint-item">
                <div className="list-card-top">
                  <span><strong>{getAuditActionLabel(log.action_type)}</strong></span>
                  <span className="badge badge-info">audit</span>
                </div>
                <div className="meta">Performed By: {log.performed_by_name || log.performed_by || 'System'}</div>
                <div className="meta">Status Change: {log.previous_status || '—'} → {log.new_status || '—'}</div>
                <div className="meta">Timestamp: {formatDateTimeWithSeconds(log.timestamp)}</div>
                {getAuditSummary(log).map((line, index) => (
                  <div key={`${log.id}-summary-${index}`} className="meta">{line}</div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
