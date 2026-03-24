import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { api } from './api'
import { useAuth } from './useAuth.js'

const DASHBOARD_TITLES = {
  requestor: 'Requestor Dashboard',
  approver: 'Approver Dashboard',
  'risk-owner': 'Risk Owner Dashboard',
  security: 'Security Dashboard',
}

const ACTION_CONFIG = {
  submit: { endpoint: 'submit', label: 'Submit', allowedStatuses: ['Draft'] },
  bu_approve: { endpoint: 'bu_approve', label: 'BU Approve', allowedStatuses: ['Submitted'] },
  bu_reject: { endpoint: 'bu_reject', label: 'BU Reject', allowedStatuses: ['Submitted'] },
  risk_assess: { endpoint: 'risk_assess', label: 'Risk Approve', allowedStatuses: ['AwaitingRiskOwner'] },
  risk_reject: { endpoint: 'risk_reject', label: 'Risk Reject', allowedStatuses: ['AwaitingRiskOwner'] },
  close: { endpoint: 'close', label: 'Close', allowedStatuses: ['Approved'] },
}

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'deadline_soonest', label: 'Deadline soonest' },
  { value: 'deadline_latest', label: 'Deadline latest' },
]

function statusTone(status) {
  const tones = {
    Draft: 'muted',
    Submitted: 'info',
    AwaitingRiskOwner: 'warning',
    Approved: 'success',
    Rejected: 'danger',
    Expired: 'danger',
    Closed: 'muted',
  }
  return tones[status] || 'muted'
}

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear()).slice(-2)}`
}

function formatDateTimeCompact(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear()).slice(-2)} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatDateTimeWithSeconds(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear()).slice(-2)} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function getRequestedPeriodDays(item) {
  if (!item?.created_at || !item?.exception_end_date) return null
  const created = new Date(item.created_at)
  const endDate = new Date(item.exception_end_date)
  const diffMs = endDate.getTime() - created.getTime()
  if (Number.isNaN(diffMs) || diffMs <= 0) return 0
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24))
}

function sortExceptions(items, sortKey) {
  const sorted = [...items]
  if (sortKey === 'oldest') {
    sorted.sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0))
  } else if (sortKey === 'deadline_soonest') {
    sorted.sort((a, b) => {
      const aDeadline = a.approval_deadline ? new Date(a.approval_deadline).getTime() : Number.POSITIVE_INFINITY
      const bDeadline = b.approval_deadline ? new Date(b.approval_deadline).getTime() : Number.POSITIVE_INFINITY
      return aDeadline - bDeadline
    })
  } else if (sortKey === 'deadline_latest') {
    sorted.sort((a, b) => {
      const aDeadline = a.approval_deadline ? new Date(a.approval_deadline).getTime() : Number.NEGATIVE_INFINITY
      const bDeadline = b.approval_deadline ? new Date(b.approval_deadline).getTime() : Number.NEGATIVE_INFINITY
      return bDeadline - aDeadline
    })
  } else {
    sorted.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
  }
  return sorted
}

function canAct(user, exception, actionKey) {
  const config = ACTION_CONFIG[actionKey]
  if (!config || !config.allowedStatuses.includes(exception.status)) {
    return false
  }

  const groups = user?.groups || []
  const isSecurity = groups.includes('Security')
  if (isSecurity) return true

  if (actionKey === 'submit') {
    return user?.id === exception.requested_by
  }

  if (['bu_approve', 'bu_reject', 'close'].includes(actionKey)) {
    return user?.id === exception.assigned_approver
  }

  if (['risk_assess', 'risk_reject'].includes(actionKey)) {
    return user?.id === exception.risk_owner
  }

  return false
}

function matchesView(item, view, userId) {
  if (!item || !view || !userId) return false

  const hideDraftsForView = ['approver', 'risk-owner', 'security'].includes(view)
  if (hideDraftsForView && item.status === 'Draft') return false

  if (view === 'security') return true
  if (view === 'requestor') return item.requested_by === userId
  if (view === 'approver') return item.assigned_approver === userId
  if (view === 'risk-owner') return item.risk_owner === userId

  return false
}

function DashboardPage({ view }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const exceptionIdFromQuery = Number.parseInt(new URLSearchParams(location.search).get('exception') || '', 10)
  const hasExceptionQuery = Number.isInteger(exceptionIdFromQuery)
  const successMessage = location.state?.message ?? null
  const [items, setItems] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selected, setSelected] = useState(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [loadingNotifications, setLoadingNotifications] = useState(false)
  const [actionError, setActionError] = useState('')
  const [summary, setSummary] = useState(null)
  const [notifications, setNotifications] = useState([])
  const [requesterPopup, setRequesterPopup] = useState(null)
  const [sortKey, setSortKey] = useState('newest')
  const [actionNotes, setActionNotes] = useState('')
  const [adminUsers, setAdminUsers] = useState([])
  const [adminRoles, setAdminRoles] = useState([])
  const [loadingAdminUsers, setLoadingAdminUsers] = useState(false)
  const [adminError, setAdminError] = useState('')
  const [newUserForm, setNewUserForm] = useState({
    username: '',
    password: '',
    first_name: '',
    last_name: '',
    email: '',
    is_active: true,
    role: 'Requestor',
  })

  const loadExceptions = useCallback(async () => {
    setLoadingList(true)
    try {
      const response = await api.get('/api/exceptions/')
      const results = response.data.results || []
      const filtered = results.filter((item) => matchesView(item, view, user?.id))
      setItems(filtered)
      setSelectedId((current) => {
        if (hasExceptionQuery && filtered.some((item) => item.id === exceptionIdFromQuery)) {
          return exceptionIdFromQuery
        }
        return current ?? filtered[0]?.id ?? null
      })
    } finally {
      setLoadingList(false)
    }
  }, [view, user?.id, hasExceptionQuery, exceptionIdFromQuery])

  const loadExceptionDetail = useCallback(async (id) => {
    if (!id) {
      setSelected(null)
      return
    }

    setLoadingDetail(true)
    setActionError('')
    try {
      const response = await api.get(`/api/exceptions/${id}/`)
      setSelected(response.data)
    } catch (error) {
      setActionError(error?.response?.status === 404 ? 'You do not have access to this exception.' : 'Failed to load exception details.')
      setSelected(null)
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  const loadSummary = useCallback(async () => {
    const response = await api.get('/api/worklist/summary/')
    setSummary(response.data)
  }, [])

  const loadNotifications = useCallback(async () => {
    setLoadingNotifications(true)
    try {
      const response = await api.get('/api/worklist/notifications/')
      const items = response.data.items || []
      setNotifications(items)

      if (view === 'requestor') {
        const updateItems = items.filter((item) => String(item.event_type || '').startsWith('request_'))
        if (updateItems.length > 0) {
          const latest = updateItems[0]
          const lastSeenTs = window.localStorage.getItem(`requester-popup-last-seen-${user?.id || 'anon'}`)
          const latestTs = latest.timestamp || ''
          if (!lastSeenTs || (latestTs && latestTs > lastSeenTs)) {
            setRequesterPopup(latest)
          }
        }
      }
    } finally {
      setLoadingNotifications(false)
    }
  }, [view, user?.id])

  const loadAdminUsers = useCallback(async () => {
    if (view !== 'security') return
    setLoadingAdminUsers(true)
    setAdminError('')
    try {
      const response = await api.get('/api/security/users/')
      setAdminUsers(response.data.users || [])
      setAdminRoles(response.data.roles || [])
    } catch {
      setAdminError('Failed to load users for administration.')
    } finally {
      setLoadingAdminUsers(false)
    }
  }, [view])

  useEffect(() => {
    loadExceptions()
  }, [loadExceptions])

  useEffect(() => {
    loadSummary()
  }, [loadSummary])

  useEffect(() => {
    loadNotifications()
  }, [loadNotifications])

  useEffect(() => {
    loadAdminUsers()
  }, [loadAdminUsers])

  useEffect(() => {
    setSelectedId(null)
    setSelected(null)
  }, [view])

  useEffect(() => {
    if (!hasExceptionQuery) return
    if (!items.some((item) => item.id === exceptionIdFromQuery)) return
    setSelectedId(exceptionIdFromQuery)
  }, [hasExceptionQuery, exceptionIdFromQuery, items])

  useEffect(() => {
    loadExceptionDetail(selectedId)
  }, [selectedId, loadExceptionDetail])

  const availableActions = useMemo(() => {
    if (!selected || !user) return []
    return Object.entries(ACTION_CONFIG).filter(([key]) => canAct(user, selected, key))
  }, [selected, user])

  const sortedItems = useMemo(() => sortExceptions(items, sortKey), [items, sortKey])

  async function runAction(actionKey) {
    if (!selected) return

    setActionError('')
    try {
      const config = ACTION_CONFIG[actionKey]
      const notes = actionNotes.trim()
      const requiresRejectionFeedback = actionKey === 'bu_reject' || actionKey === 'risk_reject'
      const requiresHighRiskApprovalNotes = actionKey === 'bu_approve' && ['High', 'Critical'].includes(selected.risk_rating)

      if (requiresRejectionFeedback && !notes) {
        setActionError('Feedback is mandatory for rejection.')
        return
      }

      if (requiresHighRiskApprovalNotes && !notes) {
        setActionError('Notes are mandatory when approving High/Critical exceptions.')
        return
      }

      await api.post(`/api/exceptions/${selected.id}/${config.endpoint}/`, { notes })
      await loadExceptions()
      await loadExceptionDetail(selected.id)
      await loadSummary()
      await loadNotifications()
      setActionNotes('')
    } catch (error) {
      const status = error?.response?.status
      if (status === 404) {
        setActionError('This exception is no longer visible to your account.')
      } else if (status === 400) {
        const detail = error?.response?.data?.detail
        if (typeof detail === 'string') {
          setActionError(detail)
        } else {
          setActionError('This action is not valid in the current state.')
        }
      } else if (status === 403) {
        setActionError('You do not have permission to perform this action.')
      } else {
        setActionError('Action failed. Please try again.')
      }
    }
  }

  async function createManagedUser(event) {
    event.preventDefault()
    setAdminError('')
    try {
      await api.post('/api/security/users/', {
        username: newUserForm.username,
        password: newUserForm.password,
        first_name: newUserForm.first_name,
        last_name: newUserForm.last_name,
        email: newUserForm.email,
        is_active: newUserForm.is_active,
        roles: [newUserForm.role],
      })
      setNewUserForm({
        username: '',
        password: '',
        first_name: '',
        last_name: '',
        email: '',
        is_active: true,
        role: adminRoles[0] || 'Requestor',
      })
      await loadAdminUsers()
    } catch (error) {
      const message = error?.response?.data
      if (message && typeof message === 'object') {
        const firstError = Object.values(message)[0]
        setAdminError(Array.isArray(firstError) ? firstError[0] : String(firstError))
      } else {
        setAdminError('Failed to create user.')
      }
    }
  }

  async function updateManagedUser(userItem) {
    setAdminError('')
    try {
      await api.patch(`/api/security/users/${userItem.id}/`, {
        email: userItem.email,
        first_name: userItem.first_name,
        last_name: userItem.last_name,
        is_active: userItem.is_active,
        roles: userItem.roles?.length ? userItem.roles : [],
      })
      await loadAdminUsers()
    } catch {
      setAdminError(`Failed to update user ${userItem.username}.`)
    }
  }

  function updateAdminUserLocal(userId, updates) {
    setAdminUsers((current) => current.map((entry) => (entry.id === userId ? { ...entry, ...updates } : entry)))
  }

  const title = DASHBOARD_TITLES[view] || 'Exception Management Dashboard'
  const canCreateException = view === 'requestor' || view === 'security'

  return (
    <div className="shell">
      <div className="shell-header">
        <div>
          <h2>{title}</h2>
          <div className="meta">
            Signed in as <strong>{user?.username}</strong> ({(user?.groups || []).join(', ') || 'No Group'})
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {canCreateException ? (
            <button className="btn" style={{ width: 'auto' }} onClick={() => navigate('/exceptions/new')}>
              + New Exception
            </button>
          ) : null}
          <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={logout}>
            Logout
          </button>
        </div>
      </div>

      {successMessage && (
        <div style={{ margin: '0 1.5rem', padding: '0.75rem 1rem', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '0.375rem', color: '#15803d', fontSize: '0.875rem' }}>
          {successMessage}
        </div>
      )}

      {view === 'requestor' && requesterPopup ? (
        <div className="requester-popup">
          <div className="requester-popup-title">Update on your request</div>
          <div><strong>{requesterPopup.title}</strong></div>
          <div style={{ marginTop: '4px' }}>{requesterPopup.message}</div>
          {requesterPopup.feedback ? <div style={{ marginTop: '4px' }}><strong>Feedback:</strong> {requesterPopup.feedback}</div> : null}
          <div className="meta" style={{ marginTop: '6px' }}>{formatDateTime(requesterPopup.timestamp)}</div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
            <button
              className="btn btn-secondary"
              style={{ width: 'auto' }}
              onClick={() => {
                if (requesterPopup.exception_id) {
                  setSelectedId(requesterPopup.exception_id)
                }
                const ts = requesterPopup.timestamp || ''
                if (ts) {
                  window.localStorage.setItem(`requester-popup-last-seen-${user?.id || 'anon'}`, ts)
                }
                setRequesterPopup(null)
              }}
            >
              View Details
            </button>
            <button
              className="btn"
              style={{ width: 'auto' }}
              onClick={() => {
                const ts = requesterPopup.timestamp || ''
                if (ts) {
                  window.localStorage.setItem(`requester-popup-last-seen-${user?.id || 'anon'}`, ts)
                }
                setRequesterPopup(null)
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      ) : null}

      {summary ? (
        <div className="summary-grid">
          <div className="summary-card">
            <div className="summary-label">My Queue</div>
            <div className="summary-value">{summary.my_queue_total}</div>
          </div>
          <div className="summary-card">
            <div className="summary-label">Pending Action</div>
            <div className="summary-value">{summary.pending_action}</div>
          </div>
          <div className="summary-card">
            <div className="summary-label">Overdue Approval</div>
            <div className="summary-value">{summary.overdue_approval}</div>
          </div>
          <div className="summary-card">
            <div className="summary-label">Approved</div>
            <div className="summary-value">{summary.approved}</div>
          </div>
        </div>
      ) : null}

      <section className="panel" style={{ marginBottom: '20px' }}>
        <div className="panel-header">
          <h3>Notification Center</h3>
          <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={loadNotifications}>
            Refresh
          </button>
        </div>

        {loadingNotifications ? <div className="meta">Loading notifications...</div> : null}

        {!loadingNotifications && notifications.length === 0 ? (
          <div className="meta">No notifications right now.</div>
        ) : null}

        <div className="notification-list">
          {notifications.map((item, index) => (
            <button
              key={`${item.event_type}-${item.exception_id || 'na'}-${item.timestamp || index}`}
              type="button"
              className="notification-item"
              onClick={() => {
                if (!item.exception_id) return
                setSelectedId(item.exception_id)
              }}
            >
              <div className="list-card-top">
                <strong>{item.title}</strong>
                <span className={`badge badge-${item.severity === 'danger' ? 'danger' : item.severity === 'warning' ? 'warning' : 'info'}`}>
                  {item.severity}
                </span>
              </div>
              <div>{item.message}</div>
              <div className="meta">{formatDateTime(item.timestamp)}</div>
            </button>
          ))}
        </div>
      </section>

      {view === 'security' ? (
        <section className="panel" style={{ marginBottom: '20px' }}>
          <div className="panel-header">
            <h3>User Administration</h3>
            <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={loadAdminUsers}>
              Refresh
            </button>
          </div>

          <form className="admin-form" onSubmit={createManagedUser}>
            <input placeholder="Username" value={newUserForm.username} onChange={(e) => setNewUserForm((v) => ({ ...v, username: e.target.value }))} required />
            <input placeholder="Password" type="password" value={newUserForm.password} onChange={(e) => setNewUserForm((v) => ({ ...v, password: e.target.value }))} required />
            <input placeholder="First name" value={newUserForm.first_name} onChange={(e) => setNewUserForm((v) => ({ ...v, first_name: e.target.value }))} />
            <input placeholder="Last name" value={newUserForm.last_name} onChange={(e) => setNewUserForm((v) => ({ ...v, last_name: e.target.value }))} />
            <input placeholder="Email" type="email" value={newUserForm.email} onChange={(e) => setNewUserForm((v) => ({ ...v, email: e.target.value }))} />
            <select value={newUserForm.role} onChange={(e) => setNewUserForm((v) => ({ ...v, role: e.target.value }))}>
              {(adminRoles.length ? adminRoles : ['Requestor', 'Approver', 'RiskOwner', 'Security']).map((role) => (
                <option key={role} value={role}>{role}</option>
              ))}
            </select>
            <label className="meta" style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <input type="checkbox" checked={newUserForm.is_active} onChange={(e) => setNewUserForm((v) => ({ ...v, is_active: e.target.checked }))} /> Active
            </label>
            <button className="btn" style={{ width: 'auto' }} type="submit">Create User</button>
          </form>

          {loadingAdminUsers ? <div className="meta">Loading users...</div> : null}
          {adminError ? <div className="error">{adminError}</div> : null}

          <div className="admin-users-list">
            {adminUsers.map((managedUser) => (
              <div className="admin-user-row" key={managedUser.id}>
                <div><strong>{managedUser.username}</strong></div>
                <input
                  type="email"
                  value={managedUser.email || ''}
                  onChange={(e) => updateAdminUserLocal(managedUser.id, { email: e.target.value })}
                  placeholder="Email"
                />
                <select
                  value={(managedUser.roles && managedUser.roles[0]) || ''}
                  onChange={(e) => updateAdminUserLocal(managedUser.id, { roles: e.target.value ? [e.target.value] : [] })}
                >
                  <option value="">No Role</option>
                  {(adminRoles.length ? adminRoles : ['Requestor', 'Approver', 'RiskOwner', 'Security']).map((role) => (
                    <option key={role} value={role}>{role}</option>
                  ))}
                </select>
                <label className="meta" style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={Boolean(managedUser.is_active)}
                    onChange={(e) => updateAdminUserLocal(managedUser.id, { is_active: e.target.checked })}
                  />
                  Active
                </label>
                <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={() => updateManagedUser(managedUser)}>
                  Save
                </button>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <h3>Exceptions</h3>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <select value={sortKey} onChange={(event) => setSortKey(event.target.value)}>
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
              <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={loadExceptions}>
                Refresh
              </button>
            </div>
          </div>

          {loadingList ? <div className="meta">Loading exceptions...</div> : null}

          {!loadingList && items.length === 0 ? <div className="meta">No exceptions available for your account.</div> : null}

          <div className="list-stack">
            {sortedItems.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`list-card ${selectedId === item.id ? 'list-card-active' : ''}`}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="list-card-top">
                  <strong>#{item.id}</strong>
                  <span className={`badge badge-${statusTone(item.status)}`}>{item.status}</span>
                </div>
                <div>{item.short_description}</div>
                <div className="meta">Risk: {item.risk_rating || 'Pending calculation'}</div>
                {['approver', 'risk-owner'].includes(view)
                  ? <div className="meta">Submitted On: {formatDateTime(item.submitted_at)}</div>
                  : <div className="meta">Created On: {formatDateTime(item.created_at)}</div>}
              </button>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h3>Details</h3>
          </div>

          {loadingDetail ? <div className="meta">Loading details...</div> : null}

          {!loadingDetail && !selected ? <div className="meta">Select an exception to view details.</div> : null}

          {selected ? (
            <>
              <div className="detail-grid">
                <div><strong>ID:</strong> #{selected.id}</div>
                <div><strong>Status:</strong> <span className={`badge badge-${statusTone(selected.status)}`}>{selected.status}</span></div>
                <div><strong>Risk:</strong> {selected.risk_rating || 'Pending'} ({selected.risk_score ?? '—'})</div>
                <div><strong>Business Unit:</strong> {selected.business_unit}</div>
                <div><strong>Assigned Approver:</strong> {selected.assigned_approver}</div>
                <div><strong>Risk Owner:</strong> {selected.risk_owner}</div>
              </div>

              <div className="section-block">
                <strong>Timeline</strong>
                <div className="detail-grid" style={{ marginTop: '8px' }}>
                  {['approver', 'risk-owner'].includes(view)
                    ? <div><strong>Submitted On:</strong> {formatDateTime(selected.submitted_at)}</div>
                    : <div><strong>Created On:</strong> {formatDateTime(selected.created_at)}</div>}
                  <div><strong>Last Updated On:</strong> {formatDateTime(selected.updated_at)}</div>
                  {view !== 'requestor' ? (
                    <div><strong>Approval Deadline:</strong> {formatDateTimeCompact(selected.approval_deadline)}</div>
                  ) : null}
                  <div><strong>Approved On:</strong> {formatDateTime(selected.approved_at)}</div>
                  <div><strong>Requested End Date:</strong> {formatDateTimeCompact(selected.exception_end_date)}</div>
                  <div><strong>Requested Active Period:</strong> {getRequestedPeriodDays(selected) ?? '—'} day(s)</div>
                </div>
              </div>

              {selected.status === 'Rejected' && selected.rejection_feedback ? (
                <div className="section-block">
                  <strong>Rejection Feedback</strong>
                  <p>{selected.rejection_feedback}</p>
                </div>
              ) : null}

              <div className="section-block">
                <strong>Description</strong>
                <p>{selected.short_description}</p>
              </div>

              <div className="section-block">
                <strong>Reason for exception</strong>
                <p>{selected.reason_for_exception}</p>
              </div>

              <div className="section-block">
                <strong>Available actions</strong>
                <div style={{ marginTop: '10px' }}>
                  <textarea
                    className="action-notes"
                    placeholder="Add notes/feedback (mandatory for rejection and High/Critical BU approval)"
                    value={actionNotes}
                    onChange={(event) => setActionNotes(event.target.value)}
                  />
                </div>
                <div className="action-row">
                  {availableActions.length === 0 ? <span className="meta">No actions available for your role in this state.</span> : null}
                  {availableActions.map(([key, config]) => (
                    <button key={key} className="btn" style={{ width: 'auto' }} onClick={() => runAction(key)}>
                      {config.label}
                    </button>
                  ))}
                </div>
                {actionError ? <div className="error" style={{ marginTop: '12px' }}>{actionError}</div> : null}
              </div>

              <div className="section-block">
                <strong>Checkpoints</strong>
                <div className="checkpoint-list">
                  {(selected.checkpoints || []).map((checkpoint) => (
                    <div key={checkpoint.checkpoint} className="checkpoint-item">
                      <div className="list-card-top">
                        <span>{checkpoint.checkpoint_display}</span>
                        <span className={`badge badge-${checkpoint.status === 'completed' ? 'success' : checkpoint.status === 'skipped' ? 'muted' : checkpoint.status === 'escalated' ? 'danger' : 'warning'}`}>
                          {checkpoint.status}
                        </span>
                      </div>
                      <div className="meta">{checkpoint.completed_by_name || 'System / Pending'}</div>
                      <div className="meta">Timestamp: {formatDateTimeWithSeconds(checkpoint.completed_at)}</div>
                      {checkpoint.notes ? <div className="meta">{checkpoint.notes}</div> : null}
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </section>
      </div>
    </div>
  )
}

export default DashboardPage