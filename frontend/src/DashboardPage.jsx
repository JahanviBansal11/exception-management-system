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
  renew: { endpoint: 'renew', label: 'Renew', allowedStatuses: ['Approved'] },
  close: { endpoint: 'close', label: 'Close', allowedStatuses: ['Approved'] },
}

const ACTIONS_USING_NOTES = new Set(['bu_approve', 'bu_reject', 'risk_assess', 'risk_reject', 'renew'])

function actionUsesNotes(actionKey) {
  return ACTIONS_USING_NOTES.has(actionKey)
}

function actionRequiresNotes(actionKey, exceptionItem) {
  if (actionKey === 'renew') {
    return true
  }

  if (actionKey === 'bu_reject' || actionKey === 'risk_reject') {
    return true
  }

  if (actionKey === 'bu_approve') {
    return ['High', 'Critical'].includes(exceptionItem?.risk_rating)
  }

  return false
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

const AUDIT_ACTION_LABELS = {
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
  return AUDIT_ACTION_LABELS[actionType] || actionType || 'Updated'
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
    const fromValue = details.previous_end_date ? formatDateTimeCompact(details.previous_end_date) : '—'
    const toValue = details.new_end_date ? formatDateTimeCompact(details.new_end_date) : '—'
    summary.push(`End Date: ${fromValue} → ${toValue}`)
  }

  return summary.slice(0, 3)
}

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear())}`
}

function formatDateTimeCompact(value) {
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

function isApprovalOverdue(item) {
  if (!item?.approval_deadline) return false
  if (!['Submitted', 'AwaitingRiskOwner'].includes(item.status)) return false
  const deadline = new Date(item.approval_deadline)
  if (Number.isNaN(deadline.getTime())) return false
  return deadline.getTime() < Date.now()
}

function isApprovalWindowClosed(item) {
  if (!item) return false
  if (!['Submitted', 'AwaitingRiskOwner'].includes(item.status)) return false
  if (item.reminder_stage === 'Expired_Notice') return true
  return isApprovalOverdue(item)
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

function isRiskOwnerRelevant(item) {
  if (!item) return false
  if (['High', 'Critical'].includes(item.risk_rating)) return true
  if (item.status === 'AwaitingRiskOwner') return true
  return reachedRiskOwnerStage(item)
}

const CHECKPOINT_STEPPER_ORDER = [
  { key: 'exception_requested', fallbackLabel: 'Exception Requested' },
  { key: 'bu_approval_notified', fallbackLabel: 'BU CIO Notified' },
  { key: 'bu_approval_decision', fallbackLabel: 'BU CIO Decision Received' },
  { key: 'risk_assessment_notified', fallbackLabel: 'Risk Owner Notified' },
  { key: 'risk_assessment_complete', fallbackLabel: 'Risk Assessment Complete' },
  { key: 'final_decision', fallbackLabel: 'Final Decision Made' },
]

function getCheckpointStepperStages(item) {
  if (!item) return []

  const checkpointMap = new Map((item.checkpoints || []).map((checkpoint) => [checkpoint.checkpoint, checkpoint]))
  const hideRiskOwnerCheckpoints = item.risk_rating === 'Low'

  const configuredSteps = CHECKPOINT_STEPPER_ORDER.filter((entry) => {
    if (!hideRiskOwnerCheckpoints) return true
    return !['risk_assessment_notified', 'risk_assessment_complete'].includes(entry.key)
  })

  const mapped = configuredSteps.map((entry) => {
    const checkpoint = checkpointMap.get(entry.key)
    const rawStatus = checkpoint?.status || 'pending'
    const state = ['completed', 'pending', 'skipped', 'escalated'].includes(rawStatus) ? rawStatus : 'pending'
    return {
      key: entry.key,
      label: checkpoint?.checkpoint_display || entry.fallbackLabel,
      state,
    }
  })

  const firstPendingIndex = mapped.findIndex((stage) => stage.state === 'pending')
  if (firstPendingIndex >= 0) {
    mapped[firstPendingIndex] = {
      ...mapped[firstPendingIndex],
      state: 'active',
    }
  }

  return mapped
}

function getCheckpointByKey(item, checkpointKey) {
  return (item?.checkpoints || []).find((checkpoint) => checkpoint.checkpoint === checkpointKey) || null
}

function getNotificationItemKey(item) {
  return item?.event_key || [
    item?.event_type || 'na',
    item?.exception_id || 'na',
    item?.timestamp || 'na',
    item?.title || 'na',
    item?.message || 'na',
  ].join('|')
}

function getReferenceLabel(options, selectedId, preferredLabelFields) {
  if (!Array.isArray(options) || selectedId === null || selectedId === undefined || selectedId === '') return '—'
  const selected = options.find((entry) => String(entry.id) === String(selectedId))
  if (!selected) return String(selectedId)

  for (const field of preferredLabelFields) {
    const value = selected[field]
    if (value) return String(value)
  }
  return String(selected.id)
}

function toCsvValue(value) {
  if (value === null || value === undefined) return '""'
  const text = String(value).replace(/"/g, '""')
  return `"${text}"`
}

function canAct(user, exception, actionKey) {
  const config = ACTION_CONFIG[actionKey]
  if (!config || !config.allowedStatuses.includes(exception.status)) {
    return false
  }

  if (actionKey === 'renew') {
    return String(user?.id) === String(exception.requested_by) && Boolean(exception.exception_end_date)
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
  const [auditLogs, setAuditLogs] = useState([])
  const [loadingAuditLogs, setLoadingAuditLogs] = useState(false)
  const [auditLogsError, setAuditLogsError] = useState('')
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [loadingNotifications, setLoadingNotifications] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [actionError, setActionError] = useState('')
  const [summary, setSummary] = useState(null)
  const [notifications, setNotifications] = useState([])
  const [notificationActionError, setNotificationActionError] = useState('')
  const [referenceData, setReferenceData] = useState(null)
  const [requesterPopup, setRequesterPopup] = useState(null)
  const [sortKey, setSortKey] = useState('newest')
  const [selectedStatusFilters, setSelectedStatusFilters] = useState([])
  const [selectedRiskFilters, setSelectedRiskFilters] = useState([])
  const [sortMenuOpen, setSortMenuOpen] = useState(false)
  const [filterMenuOpen, setFilterMenuOpen] = useState(false)
  const [statusFilterEnabled, setStatusFilterEnabled] = useState(false)
  const [riskFilterEnabled, setRiskFilterEnabled] = useState(false)
  const [activeKpi, setActiveKpi] = useState('')
  const [actionNotesDrafts, setActionNotesDrafts] = useState({})
  const [endDateInputDrafts, setEndDateInputDrafts] = useState({})
  const [endDateNotesDrafts, setEndDateNotesDrafts] = useState({})
  const [endDateUpdateError, setEndDateUpdateError] = useState('')
  const [updatingEndDate, setUpdatingEndDate] = useState(false)
  const [showEndDateEditor, setShowEndDateEditor] = useState(false)
  const [endDateActionMode, setEndDateActionMode] = useState('update')
  const [showEndDateHistory, setShowEndDateHistory] = useState(false)
  const [adminUsers, setAdminUsers] = useState([])
  const [adminRoles, setAdminRoles] = useState([])
  const [loadingAdminUsers, setLoadingAdminUsers] = useState(false)
  const [adminError, setAdminError] = useState('')
  const [adminSearch, setAdminSearch] = useState('')
  const [adminRoleFilter, setAdminRoleFilter] = useState('all')
  const [adminStatusFilter, setAdminStatusFilter] = useState('all')
  const [expandedTabs, setExpandedTabs] = useState({
    exceptionDetails: true,
    timeline: false,
    checkpoints: false,
    auditLogs: false,
  })
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

  const loadAuditLogs = useCallback(async (id) => {
    if (!id || view !== 'security') {
      setAuditLogs([])
      setAuditLogsError('')
      setLoadingAuditLogs(false)
      return
    }

    setLoadingAuditLogs(true)
    setAuditLogsError('')
    try {
      const response = await api.get(`/api/exceptions/${id}/audit_logs/?limit=100`)
      setAuditLogs(response.data.results || [])
    } catch (error) {
      const status = error?.response?.status
      if (status === 403) {
        setAuditLogsError('You do not have permission to view audit logs.')
      } else if (status === 404) {
        setAuditLogsError('Audit logs were not found for this exception.')
      } else {
        setAuditLogsError('Failed to load audit logs.')
      }
      setAuditLogs([])
    } finally {
      setLoadingAuditLogs(false)
    }
  }, [view])

  const loadSummary = useCallback(async () => {
    const response = await api.get('/api/worklist/summary/')
    setSummary(response.data)
  }, [])

  const loadNotifications = useCallback(async () => {
    setLoadingNotifications(true)
    setNotificationActionError('')
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
    } catch {
      setNotificationActionError('Failed to load notifications. Please refresh and try again.')
    } finally {
      setLoadingNotifications(false)
    }
  }, [view, user?.id])

  const loadReferenceData = useCallback(async () => {
    try {
      const response = await api.get('/api/reference/')
      setReferenceData(response.data || null)
    } catch {
      setReferenceData(null)
    }
  }, [])

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
    loadReferenceData()
  }, [loadReferenceData])

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
    if (view !== 'security') {
      setAuditLogs([])
      setAuditLogsError('')
      setLoadingAuditLogs(false)
      return
    }

    if (!selected?.id) {
      setAuditLogs([])
      setAuditLogsError('')
      setLoadingAuditLogs(false)
      return
    }

    loadAuditLogs(selected.id)
  }, [view, selected?.id, loadAuditLogs])

  useEffect(() => {
    if (!selected) {
      setEndDateUpdateError('')
      setShowEndDateEditor(false)
      setEndDateActionMode('update')
      return
    }
    setEndDateUpdateError('')
    setShowEndDateEditor(false)
    setShowEndDateHistory(false)
    setEndDateActionMode('update')
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
  const canViewAuditLogs = view === 'security'
  const toggleTab = (tabName) => {
    setExpandedTabs((current) => ({
      ...current,
      [tabName]: !current[tabName],
    }))
  }
  const selectedActionNotes = selected?.id ? (actionNotesDrafts[selected.id] || '') : ''
  const selectedEndDateInput = selected?.id ? (endDateInputDrafts[selected.id] ?? toDateTimeLocalValue(selected.exception_end_date)) : ''
  const selectedEndDateNotes = selected?.id ? (endDateNotesDrafts[selected.id] || '') : ''
  const availableActionsUsingNotes = useMemo(
    () => availableActions.filter(([actionKey]) => actionUsesNotes(actionKey)),
    [availableActions],
  )
  const hasRequiredNotesAction = useMemo(
    () => availableActionsUsingNotes.some(([actionKey]) => actionRequiresNotes(actionKey, selected)),
    [availableActionsUsingNotes, selected],
  )
  const showActionNotesBox = availableActionsUsingNotes.length > 0
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
      const notes = selectedActionNotes.trim()
      const requiresNotes = actionRequiresNotes(actionKey, selected)

      if (requiresNotes && !notes) {
        if (actionKey === 'bu_approve') {
          setActionError('Notes are mandatory for High/Critical BU approval.')
        } else if (actionKey === 'renew') {
          setActionError('Notes are mandatory for renewal requests.')
        } else {
          setActionError('Feedback is mandatory for rejection.')
        }
        return
      }

      await api.post(`/api/exceptions/${selected.id}/${config.endpoint}/`, { notes })
      await loadExceptions()
      await loadExceptionDetail(selected.id)
      await loadSummary()
      await loadNotifications()
      setActionNotesDrafts((current) => {
        const next = { ...current }
        delete next[selected.id]
        return next
      })
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

    if (!selectedEndDateInput) {
      setEndDateUpdateError('Please select a new end date.')
      return
    }
    if (!selectedEndDateNotes.trim()) {
      setEndDateUpdateError('Please provide notes for this end date update.')
      return
    }

    setUpdatingEndDate(true)
    try {
      const isoEndDate = new Date(selectedEndDateInput).toISOString()
      const endpoint = endDateActionMode === 'renew' ? 'renew' : 'update_end_date'
      await api.post(`/api/exceptions/${selected.id}/${endpoint}/`, {
        exception_end_date: isoEndDate,
        notes: selectedEndDateNotes.trim(),
      })

      await loadExceptions()
      await loadExceptionDetail(selected.id)
      await loadSummary()
      await loadNotifications()
      setEndDateInputDrafts((current) => {
        const next = { ...current }
        delete next[selected.id]
        return next
      })
      setEndDateNotesDrafts((current) => {
        const next = { ...current }
        delete next[selected.id]
        return next
      })
      setShowEndDateEditor(false)
      setEndDateActionMode('update')
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

  function openEndDateEditor(mode = 'update') {
    setEndDateActionMode(mode)
    setShowEndDateEditor(true)
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
  const canShowEndDateEditor = canUpdateEndDate || endDateActionMode === 'renew'
  const selectedCheckpointStepperStages = useMemo(() => getCheckpointStepperStages(selected), [selected])
  const canViewRiskContextTooltip = ['approver', 'risk-owner', 'security'].includes(view)

  const selectedRiskContext = useMemo(() => {
    if (!selected || !referenceData) return null
    return {
      assetType: getReferenceLabel(referenceData.asset_types, selected.asset_type, ['name']),
      assetPurpose: getReferenceLabel(referenceData.asset_purposes, selected.asset_purpose, ['name']),
      dataClassification: getReferenceLabel(referenceData.data_classifications, selected.data_classification, ['level', 'name']),
      internetExposure: getReferenceLabel(referenceData.internet_exposures, selected.internet_exposure, ['label', 'name']),
      dataComponents: Array.isArray(selected.data_components) && selected.data_components.length > 0
        ? selected.data_components
          .map((componentId) => getReferenceLabel(referenceData.data_components, componentId, ['name']))
          .join(', ')
        : '—',
    }
  }, [selected, referenceData])

  const selectedNoteSections = useMemo(() => {
    if (!selected) return []

    const sections = []
    const canSeeRequesterNotes = ['approver', 'risk-owner', 'security'].includes(view)

    if (canSeeRequesterNotes && selected.short_description) {
      sections.push({
        label: 'Short Description',
        value: selected.short_description,
        recipient: 'Approver and Risk Owner',
      })
    }

    if (canSeeRequesterNotes && selected.reason_for_exception) {
      sections.push({
        label: 'Reason for Exception',
        value: selected.reason_for_exception,
        recipient: 'Approver and Risk Owner',
      })
    }

    const buDecisionCheckpoint = getCheckpointByKey(selected, 'bu_approval_decision')
    if (buDecisionCheckpoint?.notes && ['risk-owner', 'security'].includes(view)) {
      sections.push({
        label: 'BU CIO Notes',
        value: buDecisionCheckpoint.notes,
        recipient: 'Risk Owner',
      })
    }

    const riskDecisionCheckpoint = getCheckpointByKey(selected, 'risk_assessment_complete')
    if (riskDecisionCheckpoint?.notes && isRiskOwnerRelevant(selected) && ['requestor', 'security'].includes(view)) {
      sections.push({
        label: 'Risk Owner Notes',
        value: riskDecisionCheckpoint.notes,
        recipient: 'Requestor',
      })
    }

    const finalDecisionCheckpoint = getCheckpointByKey(selected, 'final_decision')
    if (finalDecisionCheckpoint?.notes && ['requestor', 'security'].includes(view)) {
      sections.push({
        label: 'Decision Notes',
        value: finalDecisionCheckpoint.notes,
        recipient: 'Requestor',
      })
    }

    return sections
  }, [selected, view])

  async function dismissNotification(item) {
    const eventKey = getNotificationItemKey(item)
    setNotificationActionError('')
    try {
      await api.post('/api/worklist/notifications/dismiss/', { event_key: eventKey })
      setNotifications((current) => current.filter((entry) => getNotificationItemKey(entry) !== eventKey))
    } catch {
      setNotificationActionError('Failed to dismiss notification. Please retry.')
    }
  }

  function downloadSecurityReport() {
    if (view !== 'security') return

    const headers = [
      'Exception ID',
      'Status',
      'Risk Rating',
      'Risk Score',
      'Business Unit',
      'Short Description',
      'Requested By User ID',
      'Requested By Username',
      'Assigned Approver User ID',
      'Assigned Approver Username',
      'Risk Owner User ID',
      'Risk Owner Username',
      'Created At',
      'Submitted At',
      'Updated At',
      'Approval Deadline',
      'Exception End Date',
    ]

    const rows = listItems.map((item) => [
      item.id,
      item.status,
      item.risk_rating || '',
      item.risk_score ?? '',
      item.business_unit,
      item.short_description,
      item.requested_by,
      item.requested_by_username || '',
      item.assigned_approver,
      item.assigned_approver_username || '',
      item.risk_owner,
      item.risk_owner_username || '',
      item.created_at || '',
      item.submitted_at || '',
      item.updated_at || '',
      item.approval_deadline || '',
      item.exception_end_date || '',
    ])

    const csvLines = [headers, ...rows].map((line) => line.map((value) => toCsvValue(value)).join(','))
    const csvText = csvLines.join('\n')
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' })
    const href = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = href
    link.download = `security-dashboard-report-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(href)
  }

  return (
    <div className="shell">
      <div className="shell-header">
        <div>
          <h2>{title}</h2>
          <div className="meta">
            Signed in as <strong>{user?.username}</strong> (ID: {user?.id ?? '—'}) ({(user?.groups || []).join(', ') || 'No Group'})
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {canCreateException ? (
            <button className="btn" style={{ width: 'auto' }} onClick={() => navigate('/exceptions/new')}>
              + New Exception
            </button>
          ) : null}
          {view === 'security' ? (
            <button className="btn" style={{ width: 'auto' }} onClick={() => navigate('/audit-log')}>
              Audit Log
            </button>
          ) : null}
          {view === 'security' ? (
            <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={downloadSecurityReport}>
              Download Report
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
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    <span className={`badge badge-${statusTone(item.status)}`}>{item.status}</span>
                    {isApprovalWindowClosed(item) ? <span className="badge badge-warning">Approval Window Closed</span> : null}
                  </div>
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
              {/* Exception Details Tab */}
              <div className="section-block" style={{ marginBottom: '0', borderBottom: '1px solid #e5e7eb', paddingBottom: '0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', padding: '12px 0' }} onClick={() => toggleTab('exceptionDetails')}>
                  <span style={{ fontSize: '1.2em', transition: 'transform 0.2s', transform: expandedTabs.exceptionDetails ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
                  <strong>Exception Details</strong>
                </div>
                {expandedTabs.exceptionDetails && (
                  <div style={{ paddingTop: '12px' }}>
                    <div className="detail-grid">
                      <div><strong>ID:</strong> #{selected.id}</div>
                      <div>
                        <strong>Status:</strong>{' '}
                        <span className={`badge badge-${statusTone(selected.status)}`}>{selected.status}</span>
                        {isApprovalWindowClosed(selected) ? <span className="badge badge-warning" style={{ marginLeft: '8px' }}>Approval Window Closed</span> : null}
                      </div>
                      <div>
                        <strong>Risk:</strong> {selected.risk_rating || 'Pending'} ({selected.risk_score ?? '—'})
                        {canViewRiskContextTooltip ? (
                          <span className="tooltip-wrap" style={{ marginLeft: '6px' }}>
                            <button type="button" className="tooltip-trigger" aria-label="Risk score context">ⓘ</button>
                            <span className="tooltip-content tooltip-content-wide">
                              <strong>Selected Risk Inputs</strong>
                              <br />Asset Type: {selectedRiskContext?.assetType || '—'}
                              <br />Asset Purpose: {selectedRiskContext?.assetPurpose || '—'}
                              <br />Data Classification: {selectedRiskContext?.dataClassification || '—'}
                              <br />Internet Exposure: {selectedRiskContext?.internetExposure || '—'}
                              <br />Data Components: {selectedRiskContext?.dataComponents || '—'}
                            </span>
                          </span>
                        ) : null}
                      </div>
                      <div><strong>Business Unit:</strong> {selected.business_unit}</div>
                      <div><strong>Created By:</strong> {selected.requested_by} ({selected.requested_by_username || '—'})</div>
                      <div><strong>Assigned Approver:</strong> {selected.assigned_approver} ({selected.assigned_approver_username || '—'})</div>
                      <div><strong>Risk Owner:</strong> {selected.risk_owner} ({selected.risk_owner_username || '—'})</div>
                    </div>

                    {selectedNoteSections.length > 0 ? (
                      <div style={{ marginTop: '12px', display: 'grid', gap: '8px' }}>
                        <strong>Notes visible for this exception</strong>
                        {selectedNoteSections.map((section) => (
                          <div key={section.label} className="checkpoint-item" style={{ padding: '12px' }}>
                            <div className="list-card-top">
                              <span><strong>{section.label}</strong></span>
                              <span className="badge badge-info">{section.recipient}</span>
                            </div>
                            <div style={{ whiteSpace: 'pre-wrap' }}>{section.value}</div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}
              </div>

              <div className="section-block" style={{ borderBottom: '1px solid #e5e7eb', paddingBottom: '12px' }}>
                <strong>Available Actions</strong>
                <div style={{ marginTop: '10px' }}>
                  {showActionNotesBox ? (
                    <>
                      <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>
                        Notes {hasRequiredNotesAction ? <span className="error" style={{ display: 'inline', marginBottom: 0 }}>*</span> : null}
                      </label>
                      <textarea
                        className="action-notes"
                        placeholder="Add notes"
                        value={selectedActionNotes}
                        onChange={(event) => {
                          if (!selected?.id) return
                          setActionNotesDrafts((current) => ({
                            ...current,
                            [selected.id]: event.target.value,
                          }))
                        }}
                      />
                      <div className="meta" style={{ marginTop: '4px' }}>
                        Notes are required for rejection and renewal. For approvals, notes are optional except High/Critical BU approvals.
                      </div>
                    </>
                  ) : null}

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: showActionNotesBox ? '8px' : 0 }}>
                    {availableActions.length === 0 ? <span className="meta">No actions available for this exception in your current role/state.</span> : null}
                    {availableActions.map(([actionKey, config]) => (
                      <button
                        key={actionKey}
                        className="btn"
                        style={{ width: 'auto' }}
                        onClick={() => {
                          if (actionKey === 'renew') {
                            openEndDateEditor('renew')
                            return
                          }
                          runAction(actionKey)
                        }}
                      >
                        {config.label}
                        {actionRequiresNotes(actionKey, selected) ? <span className="error" style={{ display: 'inline', marginLeft: '4px', marginBottom: 0 }}>*</span> : null}
                      </button>
                    ))}
                  </div>
                  {actionError ? <div className="error" style={{ marginTop: '8px' }}>{actionError}</div> : null}
                </div>
              </div>

              {/* Timeline Tab */}
              <div className="section-block" style={{ marginBottom: '0', borderBottom: '1px solid #e5e7eb', paddingBottom: '0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', padding: '12px 0' }} onClick={() => toggleTab('timeline')}>
                  <span style={{ fontSize: '1.2em', transition: 'transform 0.2s', transform: expandedTabs.timeline ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
                  <strong>Timeline</strong>
                </div>
                {expandedTabs.timeline && (
                  <div style={{ paddingTop: '12px' }}>
                    <div className="detail-grid">
                      {['approver', 'risk-owner'].includes(view)
                        ? <div><strong>Submitted On:</strong> {formatDateTime(selected.submitted_at)}</div>
                        : <div><strong>Created On:</strong> {formatDateTime(selected.created_at)}</div>}
                      <div><strong>Last Updated On:</strong> {formatDateTime(selected.updated_at)}</div>
                      {view !== 'requestor' ? (
                        <div>
                          <strong>Approval Deadline:</strong> {formatDateTimeCompact(selected.approval_deadline)}
                          {['approver', 'risk-owner'].includes(view) && isApprovalOverdue(selected) ? (
                            <span className="badge badge-danger" style={{ marginLeft: '8px', verticalAlign: 'middle' }}>⚠ Overdue</span>
                          ) : null}
                        </div>
                      ) : null}
                      {view !== 'approver' ? <div><strong>Approved On:</strong> {formatDateTime(selected.approved_at)}</div> : null}
                      <div><strong>Requested Active Period:</strong> {getRequestedPeriodDays(selected) ?? '—'} day(s)</div>
                      <div>
                        <strong>Current End Date:</strong> {formatDateTimeCompact(selected.exception_end_date)}
                        {canUpdateEndDate ? (
                          <button
                            className="btn btn-secondary"
                            style={{ width: 'auto', marginLeft: '12px', fontWeight: 'normal' }}
                            onClick={() => openEndDateEditor('update')}
                          >
                            {showEndDateEditor ? 'Cancel' : 'Update End Date'}
                          </button>
                        ) : null}
                      </div>
                    </div>

                    {canShowEndDateEditor && showEndDateEditor ? (
                      <div style={{ marginTop: '10px', padding: '12px', border: '1px solid #e5e7eb', borderRadius: '0.375rem', backgroundColor: '#f9fafb' }}>
                        <div className="detail-grid">
                          <div>
                            <label className="meta">New End Date</label>
                            <input
                              type="datetime-local"
                              value={selectedEndDateInput}
                              onChange={(event) => {
                                if (!selected?.id) return
                                setEndDateInputDrafts((current) => ({
                                  ...current,
                                  [selected.id]: event.target.value,
                                }))
                              }}
                            />
                          </div>
                          <div>
                            <label className="meta">Notes <span className="error" style={{ display: 'inline', marginBottom: 0 }}>*</span></label>
                            <textarea
                              className="action-notes"
                              placeholder="Why is the end date changing?"
                              value={selectedEndDateNotes}
                              onChange={(event) => {
                                if (!selected?.id) return
                                setEndDateNotesDrafts((current) => ({
                                  ...current,
                                  [selected.id]: event.target.value,
                                }))
                              }}
                            />
                          </div>
                        </div>
                        <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
                          <button className="btn" style={{ width: 'auto' }} onClick={updateExceptionEndDate} disabled={updatingEndDate}>
                            {updatingEndDate ? 'Updating...' : (endDateActionMode === 'renew' ? 'Save Renewal' : 'Save End Date')}
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ width: 'auto' }}
                            onClick={() => {
                              setShowEndDateEditor(false)
                              setEndDateInputDrafts((current) => {
                                const next = { ...current }
                                delete next[selected.id]
                                return next
                              })
                              setEndDateNotesDrafts((current) => {
                                const next = { ...current }
                                delete next[selected.id]
                                return next
                              })
                            }}
                            disabled={updatingEndDate}
                          >
                            Clear
                          </button>
                        </div>
                        {endDateUpdateError ? <div className="error" style={{ marginTop: '8px' }}>{endDateUpdateError}</div> : null}
                      </div>
                    ) : null}

                    <div className="checkpoint-list" style={{ marginTop: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', marginBottom: '8px', fontWeight: 'bold' }} onClick={() => setShowEndDateHistory((current) => !current)}>
                        <span style={{ fontSize: '1.2em', transition: 'transform 0.2s' }}>{showEndDateHistory ? '▼' : '▶'}</span>
                        <span>End Date Change History ({(selected.end_date_change_history || []).length})</span>
                      </div>

                      {(selected.end_date_change_history || []).length === 0 ? (
                        <div className="meta">No end date changes recorded.</div>
                      ) : null}

                      {showEndDateHistory && (selected.end_date_change_history || []).map((entry, index) => (
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
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Checkpoints Tab */}
              <div className="section-block" style={{ marginBottom: '0', borderBottom: '1px solid #e5e7eb', paddingBottom: '0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', padding: '12px 0' }} onClick={() => toggleTab('checkpoints')}>
                  <span style={{ fontSize: '1.2em', transition: 'transform 0.2s', transform: expandedTabs.checkpoints ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
                  <strong>Checkpoints</strong>
                </div>
                {expandedTabs.checkpoints && (
                  <div style={{ paddingTop: '12px' }}>
                    <div className="checkpoint-stepper">
                      {selectedCheckpointStepperStages.map((stage, index) => (
                        <div key={stage.key} className="checkpoint-stepper-item">
                          <div className={`checkpoint-stepper-dot checkpoint-stepper-dot-${stage.state}`}>
                            {stage.state === 'completed' ? '✓' : stage.state === 'skipped' ? '↷' : stage.state === 'escalated' ? '!' : index + 1}
                          </div>
                          <div className="checkpoint-stepper-texts">
                            <div className="checkpoint-stepper-label">{stage.label}</div>
                            <div className={`checkpoint-stepper-state checkpoint-stepper-state-${stage.state}`}>{stage.state}</div>
                          </div>
                          {index < selectedCheckpointStepperStages.length - 1 ? <div className="checkpoint-stepper-line" /> : null}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Audit Logs Tab */}
              {canViewAuditLogs ? (
                <div className="section-block" style={{ marginBottom: '0', borderBottom: '1px solid #e5e7eb', paddingBottom: '0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', padding: '12px 0' }} onClick={() => toggleTab('auditLogs')}>
                    <span style={{ fontSize: '1.2em', transition: 'transform 0.2s', transform: expandedTabs.auditLogs ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
                    <strong>Audit Logs</strong>
                  </div>
                  {expandedTabs.auditLogs && (
                    <div style={{ paddingTop: '12px' }}>
                      <div className="meta" style={{ marginBottom: '10px' }}>
                        Full status history for this exception. Security only.
                      </div>

                      {loadingAuditLogs ? <div className="meta">Loading audit logs...</div> : null}
                      {!loadingAuditLogs && auditLogsError ? <div className="error">{auditLogsError}</div> : null}
                      {!loadingAuditLogs && !auditLogsError && auditLogs.length === 0 ? (
                        <div className="meta">No audit logs recorded yet.</div>
                      ) : null}

                      <div className="checkpoint-list">
                        {auditLogs.map((log) => (
                          <div key={log.id} className="checkpoint-item">
                            <div className="list-card-top">
                              <span><strong>{getAuditActionLabel(log.action_type)}</strong></span>
                              <span className="badge badge-info">audit</span>
                            </div>
                            <div className="meta">By: {log.performed_by_name || log.performed_by || 'System'}</div>
                            <div className="meta">Status: {log.previous_status || '—'} → {log.new_status || '—'}</div>
                            <div className="meta">When: {formatDateTimeWithSeconds(log.timestamp)}</div>
                            {getAuditSummary(log).map((line, index) => (
                              <div key={`${log.id}-summary-${index}`} className="meta">{line}</div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
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
            {notificationActionError ? <div className="error" style={{ marginTop: '8px' }}>{notificationActionError}</div> : null}

            <div className="notification-list notification-list-scroll">
              {notifications.map((item, index) => (
                <div
                  key={`${item.event_type}-${item.exception_id || 'na'}-${item.timestamp || index}`}
                  className="notification-item"
                >
                  <div className="list-card-top">
                    <strong>{item.title}</strong>
                    <span className={`badge badge-${item.severity === 'danger' ? 'danger' : item.severity === 'warning' ? 'warning' : 'info'}`}>
                      {item.severity}
                    </span>
                  </div>
                  <div>{item.message}</div>
                  <div className="meta">{formatDateTime(item.timestamp)}</div>
                  <div className="notification-item-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ width: 'auto', padding: '6px 10px' }}
                      onClick={() => {
                        if (item.exception_id) {
                          setSelectedId(item.exception_id)
                        }
                        setNotificationsOpen(false)
                      }}
                    >
                      View
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary notification-dismiss-btn"
                      style={{ width: 'auto', padding: '6px 10px' }}
                      onClick={() => dismissNotification(item)}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
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