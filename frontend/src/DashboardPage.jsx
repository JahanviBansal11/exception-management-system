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

const KPI_CONFIG = [
  { key: 'my_queue_total', label: 'My Queue' },
  { key: 'pending_action', label: 'Pending Action' },
  { key: 'overdue_approval', label: 'Overdue Approval' },
  { key: 'approved', label: 'Approved' },
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

function toDateTimeLocalValue(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const timezoneOffset = date.getTimezoneOffset() * 60000
  const localDate = new Date(date.getTime() - timezoneOffset)
  return localDate.toISOString().slice(0, 16)
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

function matchesKpi(item, kpiKey) {
  if (!kpiKey) return true
  if (kpiKey === 'my_queue_total') return true
  if (kpiKey === 'pending_action') return ['Submitted', 'AwaitingRiskOwner'].includes(item.status)
  if (kpiKey === 'overdue_approval') {
    if (!['Submitted', 'AwaitingRiskOwner'].includes(item.status)) return false
    if (!item.approval_deadline) return false
    const deadline = new Date(item.approval_deadline)
    if (Number.isNaN(deadline.getTime())) return false
    return deadline.getTime() < Date.now()
  }
  if (kpiKey === 'approved') return item.status === 'Approved'
  return true
}

function reachedRiskOwnerStage(item) {
  if (!item) return false
  const checkpoints = item.checkpoints || []
  const riskNotifiedCheckpoint = checkpoints.find((checkpoint) => checkpoint.checkpoint === 'risk_assessment_notified')
  return ['pending', 'completed', 'escalated'].includes(riskNotifiedCheckpoint?.status)
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
  if (view === 'risk-owner') {
    if (item.risk_owner !== userId) return false
    if (item.status === 'AwaitingRiskOwner') return true
    if (['Approved', 'Rejected', 'Expired', 'Closed'].includes(item.status)) {
      return reachedRiskOwnerStage(item)
    }
    return false
  }

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
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [actionError, setActionError] = useState('')
  const [summary, setSummary] = useState(null)
  const [notifications, setNotifications] = useState([])
  const [requesterPopup, setRequesterPopup] = useState(null)
  const [sortKey, setSortKey] = useState('newest')
  const [selectedStatusFilters, setSelectedStatusFilters] = useState([])
  const [selectedRiskFilters, setSelectedRiskFilters] = useState([])
  const [sortMenuOpen, setSortMenuOpen] = useState(false)
  const [filterMenuOpen, setFilterMenuOpen] = useState(false)
  const [statusFilterEnabled, setStatusFilterEnabled] = useState(false)
  const [riskFilterEnabled, setRiskFilterEnabled] = useState(false)
  const [activeKpi, setActiveKpi] = useState('')
  const [actionNotes, setActionNotes] = useState('')
  const [endDateInput, setEndDateInput] = useState('')
  const [endDateNotes, setEndDateNotes] = useState('')
  const [endDateUpdateError, setEndDateUpdateError] = useState('')
  const [updatingEndDate, setUpdatingEndDate] = useState(false)
  const [adminUsers, setAdminUsers] = useState([])
  const [adminRoles, setAdminRoles] = useState([])
  const [loadingAdminUsers, setLoadingAdminUsers] = useState(false)
  const [adminError, setAdminError] = useState('')
  const [adminSearch, setAdminSearch] = useState('')
  const [adminRoleFilter, setAdminRoleFilter] = useState('all')
  const [adminStatusFilter, setAdminStatusFilter] = useState('all')
  const [adminSortKey, setAdminSortKey] = useState('username_asc')
  const [activeAdminSection, setActiveAdminSection] = useState('')
  const [adminPageSize, setAdminPageSize] = useState(25)
  const [adminPage, setAdminPage] = useState(1)
  const [newUserForm, setNewUserForm] = useState({
    username: '',
    password: '',
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

  useEffect(() => {
    if (!selected) {
      setEndDateInput('')
      setEndDateNotes('')
      setEndDateUpdateError('')
      return
    }
    setEndDateInput(toDateTimeLocalValue(selected.exception_end_date))
    setEndDateNotes('')
    setEndDateUpdateError('')
  }, [selected])

  const availableActions = useMemo(() => {
    if (!selected || !user) return []
    return Object.entries(ACTION_CONFIG).filter(([key]) => canAct(user, selected, key))
  }, [selected, user])

  const sortedItems = useMemo(() => sortExceptions(items, sortKey), [items, sortKey])

  const statusOptions = useMemo(() => {
    const statuses = Array.from(new Set(items.map((item) => item.status).filter(Boolean)))
    return statuses.sort((a, b) => a.localeCompare(b))
  }, [items])

  const riskOptions = useMemo(() => {
    const ratings = Array.from(new Set(items.map((item) => item.risk_rating).filter(Boolean)))
    return ratings.sort((a, b) => a.localeCompare(b))
  }, [items])

  const canUseRiskFilter = ['approver', 'security'].includes(view)
  const effectiveStatusFilters = statusFilterEnabled ? selectedStatusFilters : []
  const effectiveRiskFilters = riskFilterEnabled && canUseRiskFilter ? selectedRiskFilters : []

  const listItems = useMemo(() => {
    return sortedItems.filter((item) => {
      if (effectiveStatusFilters.length > 0 && !effectiveStatusFilters.includes(item.status)) return false
      if (effectiveRiskFilters.length > 0 && !effectiveRiskFilters.includes(item.risk_rating)) return false
      if (!matchesKpi(item, activeKpi)) return false
      return true
    })
  }, [sortedItems, effectiveStatusFilters, effectiveRiskFilters, activeKpi])

  function toggleStatusFilter(value) {
    setSelectedStatusFilters((current) => (
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    ))
  }

  function toggleRiskFilter(value) {
    setSelectedRiskFilters((current) => (
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    ))
  }

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

  async function updateExceptionEndDate() {
    if (!selected) return
    setEndDateUpdateError('')

    if (!endDateInput) {
      setEndDateUpdateError('Please select a new end date.')
      return
    }
    if (!endDateNotes.trim()) {
      setEndDateUpdateError('Please provide notes for this end date update.')
      return
    }

    setUpdatingEndDate(true)
    try {
      const isoEndDate = new Date(endDateInput).toISOString()
      await api.post(`/api/exceptions/${selected.id}/update_end_date/`, {
        exception_end_date: isoEndDate,
        notes: endDateNotes.trim(),
      })

      await loadExceptions()
      await loadExceptionDetail(selected.id)
      await loadSummary()
      await loadNotifications()
      setEndDateNotes('')
    } catch (error) {
      const detail = error?.response?.data
      if (typeof detail?.detail === 'string') {
        setEndDateUpdateError(detail.detail)
      } else if (detail && typeof detail === 'object') {
        const first = Object.values(detail)[0]
        setEndDateUpdateError(Array.isArray(first) ? String(first[0]) : String(first))
      } else {
        setEndDateUpdateError('Failed to update end date.')
      }
    } finally {
      setUpdatingEndDate(false)
    }
  }

  async function createManagedUser(event) {
    event.preventDefault()
    setAdminError('')
    try {
      await api.post('/api/security/users/', {
        username: newUserForm.username,
        password: newUserForm.password,
        email: newUserForm.email,
        is_active: newUserForm.is_active,
        roles: [newUserForm.role],
      })
      setNewUserForm({
        username: '',
        password: '',
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

  const filteredAdminUsers = useMemo(() => {
    let list = [...adminUsers]

    if (adminSearch.trim()) {
      const keyword = adminSearch.trim().toLowerCase()
      list = list.filter((entry) => {
        const roleText = (entry.roles || []).join(' ').toLowerCase()
        return (
          String(entry.username || '').toLowerCase().includes(keyword) ||
          String(entry.email || '').toLowerCase().includes(keyword) ||
          roleText.includes(keyword)
        )
      })
    }

    if (adminRoleFilter !== 'all') {
      list = list.filter((entry) => (entry.roles || []).includes(adminRoleFilter))
    }

    if (adminStatusFilter !== 'all') {
      const onlyActive = adminStatusFilter === 'active'
      list = list.filter((entry) => Boolean(entry.is_active) === onlyActive)
    }

    if (adminSortKey === 'username_desc') {
      list.sort((a, b) => String(b.username || '').localeCompare(String(a.username || '')))
    } else if (adminSortKey === 'role_asc') {
      list.sort((a, b) => String((a.roles && a.roles[0]) || '').localeCompare(String((b.roles && b.roles[0]) || '')))
    } else if (adminSortKey === 'active_first') {
      list.sort((a, b) => Number(Boolean(b.is_active)) - Number(Boolean(a.is_active)))
    } else if (adminSortKey === 'inactive_first') {
      list.sort((a, b) => Number(Boolean(a.is_active)) - Number(Boolean(b.is_active)))
    } else {
      list.sort((a, b) => String(a.username || '').localeCompare(String(b.username || '')))
    }

    return list
  }, [adminUsers, adminSearch, adminRoleFilter, adminStatusFilter, adminSortKey])

  const totalAdminPages = Math.max(1, Math.ceil(filteredAdminUsers.length / adminPageSize))

  useEffect(() => {
    setAdminPage(1)
  }, [adminSearch, adminRoleFilter, adminStatusFilter, adminSortKey, adminPageSize])

  useEffect(() => {
    if (adminPage > totalAdminPages) {
      setAdminPage(totalAdminPages)
    }
  }, [adminPage, totalAdminPages])

  const pagedAdminUsers = useMemo(() => {
    const start = (adminPage - 1) * adminPageSize
    return filteredAdminUsers.slice(start, start + adminPageSize)
  }, [filteredAdminUsers, adminPage, adminPageSize])

  const title = DASHBOARD_TITLES[view] || 'Exception Management Dashboard'
  const canCreateException = view === 'requestor' || view === 'security'
  const notificationBadgeCount = notifications.length
  const canUpdateEndDate = ['approver', 'risk-owner', 'security'].includes(view)

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
          {KPI_CONFIG.map((kpi) => (
            <button
              key={kpi.key}
              type="button"
              className={`summary-card summary-card-clickable ${activeKpi === kpi.key ? 'summary-card-active' : ''}`}
              onClick={() => setActiveKpi((current) => (current === kpi.key ? '' : kpi.key))}
            >
              <div className="summary-label">{kpi.label}</div>
              <div className="summary-value">{summary[kpi.key] ?? 0}</div>
            </button>
          ))}
        </div>
      ) : null}

      {view === 'security' ? (
        <section className="panel" style={{ marginBottom: '20px' }}>
          <div className="panel-header">
            <h3>User Administration</h3>
            <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={loadAdminUsers}>
              Refresh
            </button>
          </div>

          <div className="admin-action-buttons">
            <button
              className={`btn ${activeAdminSection === 'create' ? '' : 'btn-secondary'}`}
              style={{ width: 'auto' }}
              onClick={() => setActiveAdminSection((current) => (current === 'create' ? '' : 'create'))}
            >
              Create User
            </button>
            <button
              className={`btn ${activeAdminSection === 'directory' ? '' : 'btn-secondary'}`}
              style={{ width: 'auto' }}
              onClick={() => setActiveAdminSection((current) => (current === 'directory' ? '' : 'directory'))}
            >
              User Directory
            </button>
          </div>

          {activeAdminSection === 'create' ? (
            <div className="admin-subsection">
              <h4>Create User</h4>
              <form className="admin-form" onSubmit={createManagedUser}>
                <input placeholder="Username" value={newUserForm.username} onChange={(e) => setNewUserForm((v) => ({ ...v, username: e.target.value }))} required />
                <input placeholder="Email" type="email" value={newUserForm.email} onChange={(e) => setNewUserForm((v) => ({ ...v, email: e.target.value }))} />
                <input placeholder="Password" type="password" value={newUserForm.password} onChange={(e) => setNewUserForm((v) => ({ ...v, password: e.target.value }))} required />
                <select className="scrollable-select" value={newUserForm.role} onChange={(e) => setNewUserForm((v) => ({ ...v, role: e.target.value }))}>
                  {(adminRoles.length ? adminRoles : ['Requestor', 'Approver', 'RiskOwner', 'Security']).map((role) => (
                    <option key={role} value={role}>{role}</option>
                  ))}
                </select>
                <label className="meta" style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <input type="checkbox" checked={newUserForm.is_active} onChange={(e) => setNewUserForm((v) => ({ ...v, is_active: e.target.checked }))} /> Active
                </label>
                <div />
                <div className="admin-create-submit">
                  <button className="btn" style={{ width: 'auto' }} type="submit">Create User</button>
                </div>
              </form>
            </div>
          ) : null}

          {activeAdminSection === 'directory' ? (
            <div className="admin-subsection">
              <h4>User Directory</h4>

              <div className="admin-toolbar">
                <input
                  placeholder="Search username/email/role"
                  value={adminSearch}
                  onChange={(event) => setAdminSearch(event.target.value)}
                />
                <select className="scrollable-select" value={adminRoleFilter} onChange={(event) => setAdminRoleFilter(event.target.value)}>
                  <option value="all">All roles</option>
                  {(adminRoles.length ? adminRoles : ['Requestor', 'Approver', 'RiskOwner', 'Security']).map((role) => (
                    <option key={role} value={role}>{role}</option>
                  ))}
                </select>
                <select className="scrollable-select" value={adminStatusFilter} onChange={(event) => setAdminStatusFilter(event.target.value)}>
                  <option value="all">All statuses</option>
                  <option value="active">Active only</option>
                  <option value="inactive">Inactive only</option>
                </select>
                <select className="scrollable-select" value={adminSortKey} onChange={(event) => setAdminSortKey(event.target.value)}>
                  <option value="username_asc">Username A→Z</option>
                  <option value="username_desc">Username Z→A</option>
                  <option value="role_asc">Role A→Z</option>
                  <option value="active_first">Active first</option>
                  <option value="inactive_first">Inactive first</option>
                </select>
                <select className="scrollable-select" value={String(adminPageSize)} onChange={(event) => setAdminPageSize(Number(event.target.value) || 25)}>
                  <option value="10">10 / page</option>
                  <option value="25">25 / page</option>
                  <option value="50">50 / page</option>
                  <option value="100">100 / page</option>
                </select>
              </div>

              {loadingAdminUsers ? <div className="meta">Loading users...</div> : null}
              {adminError ? <div className="error">{adminError}</div> : null}
              {!loadingAdminUsers ? <div className="meta">Showing {filteredAdminUsers.length} users • page {adminPage} of {totalAdminPages}</div> : null}

              <div className="admin-users-list admin-users-list-large">
                {pagedAdminUsers.map((managedUser) => (
                  <div className="admin-user-row" key={managedUser.id}>
                    <div><strong>{managedUser.username}</strong></div>
                    <input
                      type="email"
                      value={managedUser.email || ''}
                      onChange={(e) => updateAdminUserLocal(managedUser.id, { email: e.target.value })}
                      placeholder="Email"
                    />
                    <select
                      className="scrollable-select"
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

              <div className="admin-pagination">
                <button className="btn btn-secondary" style={{ width: 'auto' }} disabled={adminPage <= 1} onClick={() => setAdminPage((page) => Math.max(1, page - 1))}>Previous</button>
                <span className="meta">Page {adminPage} / {totalAdminPages}</span>
                <button className="btn btn-secondary" style={{ width: 'auto' }} disabled={adminPage >= totalAdminPages} onClick={() => setAdminPage((page) => Math.min(totalAdminPages, page + 1))}>Next</button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <h3>Exceptions</h3>
            <div className="list-controls">
              <div className="control-menu-wrap">
                <button
                  type="button"
                  className={`control-card ${sortMenuOpen ? 'control-card-active' : ''}`}
                  onClick={() => {
                    setSortMenuOpen((open) => !open)
                    setFilterMenuOpen(false)
                  }}
                >
                  Sort
                </button>
                {sortMenuOpen ? (
                  <div className="control-menu">
                    <label className="meta">Sort by</label>
                    <select className="scrollable-select" value={sortKey} onChange={(event) => setSortKey(event.target.value)}>
                      {SORT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ width: '100%' }}
                      onClick={() => {
                        setSortKey('newest')
                        setSortMenuOpen(false)
                      }}
                    >
                      Reset sorting
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="control-menu-wrap">
                <button
                  type="button"
                  className={`control-card ${filterMenuOpen ? 'control-card-active' : ''}`}
                  onClick={() => {
                    setFilterMenuOpen((open) => !open)
                    setSortMenuOpen(false)
                  }}
                >
                  Filter
                </button>
                {filterMenuOpen ? (
                  <div className="control-menu">
                    <label className="control-check">
                      <input
                        type="checkbox"
                        checked={statusFilterEnabled}
                        onChange={(event) => {
                          const enabled = event.target.checked
                          setStatusFilterEnabled(enabled)
                          if (!enabled) setSelectedStatusFilters([])
                        }}
                      />
                      Status
                    </label>
                    {statusFilterEnabled ? (
                      <div className="multi-option-list">
                        {statusOptions.map((status) => (
                          <label key={status} className="control-check">
                            <input
                              type="checkbox"
                              checked={selectedStatusFilters.includes(status)}
                              onChange={() => toggleStatusFilter(status)}
                            />
                            {status}
                          </label>
                        ))}
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ width: '100%' }}
                          onClick={() => setSelectedStatusFilters([])}
                        >
                          Clear status filters
                        </button>
                      </div>
                    ) : null}

                    {canUseRiskFilter ? (
                      <>
                        <label className="control-check">
                          <input
                            type="checkbox"
                            checked={riskFilterEnabled}
                            onChange={(event) => {
                              const enabled = event.target.checked
                              setRiskFilterEnabled(enabled)
                              if (!enabled) setSelectedRiskFilters([])
                            }}
                          />
                          Risk rating
                        </label>
                        {riskFilterEnabled ? (
                          <div className="multi-option-list">
                            {riskOptions.map((risk) => (
                              <label key={risk} className="control-check">
                                <input
                                  type="checkbox"
                                  checked={selectedRiskFilters.includes(risk)}
                                  onChange={() => toggleRiskFilter(risk)}
                                />
                                {risk}
                              </label>
                            ))}
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ width: '100%' }}
                              onClick={() => setSelectedRiskFilters([])}
                            >
                              Clear risk filters
                            </button>
                          </div>
                        ) : null}
                      </>
                    ) : null}

                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ width: '100%' }}
                      onClick={() => {
                        setStatusFilterEnabled(false)
                        setRiskFilterEnabled(false)
                        setSelectedStatusFilters([])
                        setSelectedRiskFilters([])
                        setFilterMenuOpen(false)
                      }}
                    >
                      Remove filters
                    </button>
                  </div>
                ) : null}
              </div>

              <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={loadExceptions}>
                Refresh
              </button>
            </div>
          </div>

          {loadingList ? <div className="meta">Loading exceptions...</div> : null}

          {activeKpi ? (
            <div className="meta" style={{ marginBottom: '8px' }}>
              KPI filter active: {KPI_CONFIG.find((kpi) => kpi.key === activeKpi)?.label || activeKpi}
            </div>
          ) : null}

          {!loadingList && listItems.length === 0 ? <div className="meta">No exceptions match the selected filters.</div> : null}

          <div className="list-stack">
            {listItems.map((item) => (
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
                  <div><strong>Requested Active Period:</strong> {getRequestedPeriodDays(selected) ?? '—'} day(s)</div>
                </div>
              </div>

              <div className="section-block">
                <strong>Dates</strong>
                <div className="detail-grid" style={{ marginTop: '8px' }}>
                  <div><strong>Current End Date:</strong> {formatDateTimeCompact(selected.exception_end_date)}</div>
                </div>

                {canUpdateEndDate ? (
                  <div style={{ marginTop: '10px' }}>
                    <div className="detail-grid">
                      <div>
                        <label className="meta">New End Date</label>
                        <input
                          type="datetime-local"
                          value={endDateInput}
                          onChange={(event) => setEndDateInput(event.target.value)}
                        />
                      </div>
                      <div>
                        <label className="meta">Notes</label>
                        <textarea
                          className="action-notes"
                          placeholder="Why is the end date changing?"
                          value={endDateNotes}
                          onChange={(event) => setEndDateNotes(event.target.value)}
                        />
                      </div>
                    </div>
                    <div style={{ marginTop: '8px' }}>
                      <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={updateExceptionEndDate} disabled={updatingEndDate}>
                        {updatingEndDate ? 'Updating...' : 'Update End Date'}
                      </button>
                    </div>
                    {endDateUpdateError ? <div className="error" style={{ marginTop: '8px' }}>{endDateUpdateError}</div> : null}
                  </div>
                ) : null}

                <div className="checkpoint-list" style={{ marginTop: '10px' }}>
                  {(selected.end_date_change_history || []).length === 0 ? (
                    <div className="meta">No end date changes recorded.</div>
                  ) : (
                    (selected.end_date_change_history || []).map((entry, index) => (
                      <div key={`${entry.timestamp || 'na'}-${index}`} className="checkpoint-item">
                        <div className="list-card-top">
                          <span><strong>{entry.performed_by || 'System'}</strong> updated end date</span>
                          <span className="badge badge-info">change</span>
                        </div>
                        <div className="meta">From: {formatDateTimeCompact(entry.previous_end_date)}</div>
                        <div className="meta">To: {formatDateTimeCompact(entry.new_end_date)}</div>
                        <div className="meta">When: {formatDateTimeWithSeconds(entry.timestamp)}</div>
                        {entry.notes ? <div className="meta">Notes: {entry.notes}</div> : null}
                      </div>
                    ))
                  )}
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

      <div className="notification-dock">
        {notificationsOpen ? (
          <div className="notification-dock-panel">
            <div className="panel-header">
              <h3>Notifications</h3>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={loadNotifications}>
                  Refresh
                </button>
                <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={() => setNotificationsOpen(false)}>
                  Close
                </button>
              </div>
            </div>

            {loadingNotifications ? <div className="meta">Loading notifications...</div> : null}
            {!loadingNotifications && notifications.length === 0 ? <div className="meta">No notifications right now.</div> : null}

            <div className="notification-list notification-list-scroll">
              {notifications.map((item, index) => (
                <button
                  key={`${item.event_type}-${item.exception_id || 'na'}-${item.timestamp || index}`}
                  type="button"
                  className="notification-item"
                  onClick={() => {
                    if (item.exception_id) {
                      setSelectedId(item.exception_id)
                    }
                    setNotificationsOpen(false)
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
          </div>
        ) : null}

        <button
          className="notification-dock-button"
          onClick={() => setNotificationsOpen((open) => !open)}
        >
          Notifications
          {notificationBadgeCount > 0 ? <span className="notification-dock-badge">{notificationBadgeCount > 99 ? '99+' : notificationBadgeCount}</span> : null}
        </button>
      </div>
    </div>
  )
}

export default DashboardPage