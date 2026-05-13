import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { api } from '../../services/apiClient'
import { useAuth } from '../../useAuth.js'
import { matchesView, sortExceptions, matchesKpi } from '../../hooks/useExceptions.js'
import { useNotifications } from '../../hooks/useNotifications.js'

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

const ACTIONS_USING_NOTES = new Set(['bu_approve', 'bu_reject', 'risk_assess', 'risk_reject'])

function actionUsesNotes(actionKey) {
  return ACTIONS_USING_NOTES.has(actionKey)
}

function actionRequiresNotes(actionKey, exceptionItem) {
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
    ApprovalDeadlinePassed: 'danger',
    Expired: 'warning',
    Modified: 'muted',
    Extended: 'muted',
    Closed: 'muted',
  }
  return tones[status] || 'muted'
}

const DIFF_FIELDS = [
  { key: 'short_description',        label: 'Short Description' },
  { key: 'reason_for_exception',     label: 'Reason for Exception' },
  { key: 'compensatory_controls',    label: 'Compensatory Controls' },
  { key: 'exception_end_date',       label: 'End Date', format: 'date' },
  { key: 'number_of_assets',         label: 'Number of Assets' },
  { key: 'exception_type_name',      label: 'Exception Type' },
  { key: 'asset_type_name',          label: 'Asset Type' },
  { key: 'asset_purpose_name',       label: 'Asset Purpose' },
  { key: 'data_classification_name', label: 'Data Classification' },
  { key: 'internet_exposure_name',   label: 'Internet Exposure' },
  { key: 'risk_owner_name',          label: 'Risk Owner' },
  { key: 'assigned_approver_name',   label: 'Assigned Approver' },
  { key: 'data_component_names',     label: 'Data Components', format: 'list' },
]

function computeDiff(current, snapshot) {
  return DIFF_FIELDS.flatMap(({ key, label, format }) => {
    const normalise = (val) => {
      if (format === 'list') return (Array.isArray(val) ? val : []).slice().sort().join(', ')
      if (format === 'date') return val ? formatDateTime(val) : ''
      return String(val ?? '')
    }
    const curVal = normalise(current[key])
    const oldVal = normalise(snapshot[key])
    if (curVal === oldVal) return []
    return [{ label, old: oldVal, cur: curVal, format }]
  })
}

const AUDIT_ACTION_LABELS = {
  SUBMIT: 'Submitted',
  APPROVE: 'Approved',
  REJECT: 'Rejected',
  CLOSE: 'Closed',
  MODIFY: 'Modified',
  EXTEND: 'Extended',
  REMIND: 'Reminder Sent',
  ESCALATE: 'Escalated',
  UPDATE: 'Updated',
}

function getAuditActionLabel(log) {
  if (log.action_type === 'EXPIRE') {
    return log.new_status === 'Expired' ? 'Exception Expired' : 'Approval Deadline Passed'
  }
  return AUDIT_ACTION_LABELS[log.action_type] || log.action_type || 'Updated'
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

  if (details.new_exception_id) {
    summary.push(`Superseding exception: #${details.new_exception_id}`)
  }

  return summary.slice(0, 4)
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
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [actionError, setActionError] = useState('')
  const [summary, setSummary] = useState(null)
  const { notifications, unreadCount, markRead, markAllRead, refresh: loadNotifications } = useNotifications(user)
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
  const [showEndDateHistory, setShowEndDateHistory] = useState(false)
  const [extendLoading, setExtendLoading] = useState(false)
  const [extendError, setExtendError] = useState('')
  const [remediateLoading, setRemediateLoading] = useState(false)
  const [remediateError, setRemediateError] = useState('')
  const [remediateNotes, setRemediateNotes] = useState('')
  const [modifyLoading, setModifyLoading] = useState(false)
  const [modifyError, setModifyError] = useState('')
  const [closeRejectedLoading, setCloseRejectedLoading] = useState(false)
  const [closeRejectedError, setCloseRejectedError] = useState('')
  const [deleteDraftLoading, setDeleteDraftLoading] = useState(false)
  const [deleteDraftError, setDeleteDraftError] = useState('')
  const [riskTooltipOpen, setRiskTooltipOpen] = useState(false)
  const [adminUsers, setAdminUsers] = useState([])
  const [adminRoles, setAdminRoles] = useState([])
  const [loadingAdminUsers, setLoadingAdminUsers] = useState(false)
  const [adminError, setAdminError] = useState('')
  const [adminSearch, setAdminSearch] = useState('')
  const [adminRoleFilter, setAdminRoleFilter] = useState('all')
  const [adminStatusFilter, setAdminStatusFilter] = useState('all')
  const [expandedTabs, setExpandedTabs] = useState({
    exceptionDetails: true,
    diffVsParent: true,
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
      return
    }
    setEndDateUpdateError('')
    setShowEndDateEditor(false)
    setShowEndDateHistory(false)
    setExtendError('')
    setRemediateError('')
    setRemediateNotes('')
    setModifyError('')
    setCloseRejectedError('')
    setDeleteDraftError('')

  }, [selected])

  const availableActions = useMemo(() => {
    if (!selected || !user) return []
    const _isSecurity = (user?.groups || []).includes('Security')
    const _isRequestor = Number(user?.id) === Number(selected.requested_by)
    const _hideClose = selected.status === 'Approved' && (_isRequestor || _isSecurity)
    return Object.entries(ACTION_CONFIG)
      .filter(([key]) => canAct(user, selected, key))
      .filter(([key]) => !(key === 'close' && _hideClose))
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
      await api.post(`/api/exceptions/${selected.id}/update_end_date/`, {
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

  async function requestModification() {
    if (!selected) return
    setModifyError('')

    setModifyLoading(true)
    try {
      const response = await api.post(`/api/exceptions/${selected.id}/modify/`, {})
      const newId = response.data.new_exception_id
      navigate(`/exceptions/${newId}/edit`)
    } catch (error) {
      const s = error?.response?.status
      if (s === 403) {
        setModifyError('You do not have permission to request a modification.')
      } else if (s === 400) {
        setModifyError(error?.response?.data?.detail || 'Could not create modification.')
      } else {
        setModifyError('Failed to create modification. Please try again.')
      }
      setModifyLoading(false)
    }
  }

  async function requestExtension() {
    if (!selected) return
    setExtendError('')

    setExtendLoading(true)
    try {
      const response = await api.post(`/api/exceptions/${selected.id}/extend/`, {})
      const newId = response.data.new_exception_id
      navigate(`/exceptions/${newId}/edit`)
    } catch (error) {
      const s = error?.response?.status
      if (s === 403) {
        setExtendError('You do not have permission to request an extension.')
      } else if (s === 400) {
        setExtendError(error?.response?.data?.detail || 'Could not create extension.')
      } else {
        setExtendError('Failed to create extension. Please try again.')
      }
      setExtendLoading(false)
    }
  }

  async function remediateAndClose() {
    if (!selected) return
    const notes = remediateNotes.trim()
    if (!notes) {
      setRemediateError('Remediation notes are required.')
      return
    }
    if (!window.confirm('Remediate and permanently close this exception? This cannot be undone.')) return
    setRemediateError('')
    setRemediateLoading(true)
    try {
      await api.post(`/api/exceptions/${selected.id}/remediate/`, { notes })
      await loadExceptions()
      await loadExceptionDetail(selected.id)
      await loadSummary()
      await loadNotifications()
      setRemediateNotes('')
    } catch (error) {
      const s = error?.response?.status
      if (s === 403) {
        setRemediateError('You do not have permission to remediate this exception.')
      } else if (s === 400) {
        const detail = error?.response?.data
        if (typeof detail?.detail === 'string') {
          setRemediateError(detail.detail)
        } else if (detail?.notes) {
          setRemediateError(Array.isArray(detail.notes) ? detail.notes[0] : String(detail.notes))
        } else {
          setRemediateError('Could not remediate exception.')
        }
      } else {
        setRemediateError('Failed to remediate. Please try again.')
      }
    } finally {
      setRemediateLoading(false)
    }
  }

  async function closeRejected() {
    if (!selected) return
    if (!window.confirm('Permanently close this rejected exception? This cannot be undone.')) return
    setCloseRejectedError('')

    setCloseRejectedLoading(true)
    try {
      await api.post(`/api/exceptions/${selected.id}/close_rejected/`, {})
      await loadExceptions()
      await loadExceptionDetail(selected.id)
      await loadSummary()
      await loadNotifications()
    } catch (error) {
      const s = error?.response?.status
      if (s === 403) {
        setCloseRejectedError('You do not have permission to close this exception.')
      } else {
        setCloseRejectedError('Failed to close exception. Please try again.')
      }
    } finally {
      setCloseRejectedLoading(false)
    }
  }

  async function deleteDraft() {
    if (!selected) return
    if (!window.confirm('Permanently delete this draft? This cannot be undone.')) return
    setDeleteDraftError('')
    setDeleteDraftLoading(true)
    try {
      await api.delete(`/api/exceptions/${selected.id}/`)
      await loadExceptions()
      setSelectedId(null)
      setSelected(null)
      await loadSummary()
    } catch (error) {
      const s = error?.response?.status
      if (s === 403) {
        setDeleteDraftError('You do not have permission to delete this draft.')
      } else if (s === 400) {
        setDeleteDraftError(error?.response?.data?.detail || 'Only Draft exceptions can be deleted.')
      } else {
        setDeleteDraftError('Failed to delete draft. Please try again.')
      }
    } finally {
      setDeleteDraftLoading(false)
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
  const notificationBadgeCount = unreadCount
  const canUpdateEndDate = ['approver', 'risk-owner', 'security'].includes(view)
  const isSecurity = (user?.groups || []).includes('Security')
  const isRequestor = selected ? Number(user?.id) === Number(selected.requested_by) : false
  const canModify = selected?.status === 'Rejected' && (isRequestor || isSecurity)
  const canCloseRejected = selected?.status === 'Rejected' && (isRequestor || isSecurity)
  const canRemediate = selected?.status === 'Expired' && (isRequestor || isSecurity)
  const extendWindowInfo = useMemo(() => {
    if (!selected || !(isRequestor || isSecurity)) return null
    if (!['Approved', 'Expired'].includes(selected.status)) return null
    const approvedAt = selected.approved_at ? new Date(selected.approved_at).getTime() : null
    const endDate = selected.exception_end_date ? new Date(selected.exception_end_date).getTime() : null
    if (!approvedAt || !endDate) return null
    const now = Date.now()
    const midpoint = approvedAt + (endDate - approvedAt) / 2
    const graceCutoff = endDate + 14 * 24 * 60 * 60 * 1000
    if (now > graceCutoff) return null
    if (now < midpoint) return { open: false, opensAt: new Date(midpoint) }
    return { open: true }
  }, [selected, isRequestor, isSecurity])
  const canEditDraft = selected?.status === 'Draft' && (isRequestor || isSecurity)
  const canDeleteDraft = selected?.status === 'Draft' && (isRequestor || isSecurity)
  // Whether the current user can navigate to the parent exception.
  // Risk owners only get access if the parent reached the risk assessment stage (they were involved).
  // Approvers always can (same approver on parent). Requestors always can (their own exception).
  const canAccessParent = useMemo(() => {
    if (!selected?.parent_exception || !selected?.parent_snapshot) return false
    if (isSecurity) return true
    if (view === 'requestor') return true
    if (view === 'approver') return true
    if (view === 'risk-owner') return Boolean(selected.parent_snapshot?.parent_reached_risk_owner)
    return false
  }, [selected, isSecurity, view])

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
                      <div><strong>Status:</strong> <span className={`badge badge-${statusTone(selected.status)}`}>{selected.status}</span></div>
                      <div>
                        <strong>Risk:</strong>{' '}
                        {selected.risk_rating || 'Pending'} ({selected.risk_score ?? '—'})
                        {selected.asset_type_name ? (
                          <span style={{ position: 'relative', display: 'inline-block', marginLeft: '5px', verticalAlign: 'middle' }}>
                            <span
                              onMouseEnter={() => setRiskTooltipOpen(true)}
                              onMouseLeave={() => setRiskTooltipOpen(false)}
                              style={{ cursor: 'default', color: '#6b7280', fontSize: '0.7rem', border: '1px solid #d1d5db', borderRadius: '50%', width: '13px', height: '13px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1, userSelect: 'none' }}
                            >
                              i
                            </span>
                            {riskTooltipOpen ? (
                              <div style={{ position: 'absolute', top: '50%', left: 'calc(100% + 6px)', transform: 'translateY(-50%)', zIndex: 200, background: 'white', border: '1px solid #e5e7eb', borderRadius: '0.375rem', padding: '6px 8px', width: '190px', boxShadow: '0 2px 8px rgba(0,0,0,0.12)', fontSize: '0.72rem', lineHeight: '1.6', pointerEvents: 'none', whiteSpace: 'normal' }}>
                                <div style={{ fontWeight: '600', marginBottom: '3px', color: '#374151' }}>
                                  {selected.risk_rating ? 'Risk Factors' : 'Contributing Factors (rating pending)'}
                                </div>
                                {selected.asset_type_name ? <div><span style={{ color: '#6b7280' }}>Asset Type: </span>{selected.asset_type_name}</div> : null}
                                {selected.asset_purpose_name ? <div><span style={{ color: '#6b7280' }}>Asset Purpose: </span>{selected.asset_purpose_name}</div> : null}
                                {selected.data_classification_name ? <div><span style={{ color: '#6b7280' }}>Classification: </span>{selected.data_classification_name}</div> : null}
                                {selected.internet_exposure_name ? <div><span style={{ color: '#6b7280' }}>Internet Exposure: </span>{selected.internet_exposure_name}</div> : null}
                                {selected.data_component_names?.length > 0 ? <div><span style={{ color: '#6b7280' }}>Data Components: </span>{selected.data_component_names.join(', ')}</div> : null}
                              </div>
                            ) : null}
                          </span>
                        ) : null}
                      </div>
                      <div><strong>Business Unit:</strong> {selected.business_unit_code ? `${selected.business_unit_code} (${selected.business_unit_name})` : selected.business_unit}</div>
                      <div><strong>Created By:</strong> {selected.requested_by} ({selected.requested_by_username || '—'})</div>
                      <div><strong>Assigned Approver:</strong> {selected.assigned_approver} ({selected.assigned_approver_username || '—'})</div>
                      <div><strong>Risk Owner:</strong> {selected.risk_owner} ({selected.risk_owner_username || '—'})</div>
                      {selected.parent_exception ? (
                        <div>
                          <strong>Parent Exception:</strong>{' '}
                          {canAccessParent ? (
                            <button
                              className="btn btn-secondary"
                              style={{ width: 'auto', fontWeight: 'normal', padding: '2px 8px', fontSize: '0.8rem' }}
                              onClick={() => setSelectedId(selected.parent_exception)}
                            >
                              #{selected.parent_exception} ↗
                            </button>
                          ) : (
                            <span style={{ fontSize: '0.875rem', color: '#374151' }}>#{selected.parent_exception}</span>
                          )}
                        </div>
                      ) : null}
                      {selected.derived_request_ids?.length > 0 ? (
                        <div style={{ gridColumn: 'span 2' }}>
                          <strong>Superseded by:</strong>{' '}
                          {selected.derived_request_ids.map(childId => (
                            <button
                              key={childId}
                              className="btn btn-secondary"
                              style={{ width: 'auto', fontWeight: 'normal', padding: '2px 8px', fontSize: '0.8rem', marginLeft: '6px' }}
                              onClick={() => setSelectedId(childId)}
                            >
                              #{childId} ↗
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>

                    {selected.parent_snapshot ? (() => {
                      const diffs = computeDiff(selected, selected.parent_snapshot)
                      const parentStatus = selected.parent_snapshot.parent_status
                      const parentReachedRiskOwner = selected.parent_snapshot.parent_reached_risk_owner
                      const showRiskOwnerNote = view === 'risk-owner' && !parentReachedRiskOwner
                      return (
                        <div style={{ marginTop: '16px', borderTop: '1px solid #e5e7eb', paddingTop: '4px' }}>
                          <div
                            style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', padding: '8px 0' }}
                            onClick={() => toggleTab('diffVsParent')}
                          >
                            <span style={{ fontSize: '1.1em', transition: 'transform 0.2s', transform: expandedTabs.diffVsParent ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
                            <strong style={{ fontSize: '0.875rem' }}>
                              Changes vs. Parent #{selected.parent_exception}
                              {diffs.length > 0 ? <span style={{ marginLeft: '6px', fontWeight: 'normal', color: '#6b7280' }}>({diffs.length} changed)</span> : null}
                            </strong>
                          </div>
                          {expandedTabs.diffVsParent ? (
                            <>
                              {showRiskOwnerNote ? (
                                <div style={{ marginBottom: '8px', padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.375rem', fontSize: '0.78rem', color: '#64748b', lineHeight: '1.5' }}>
                                  This request is a modification of Exception #{selected.parent_exception}
                                  {parentStatus ? ` (status: ${parentStatus})` : ''}.
                                  {' '}The original was declined before reaching the risk assessment stage — you were not involved in that process. The field changes below reflect what was updated before resubmission.
                                </div>
                              ) : null}
                              {diffs.length === 0 ? (
                                <div className="meta" style={{ paddingBottom: '8px' }}>No field changes — this is a pure extension with identical fields.</div>
                              ) : (
                                <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '8px', fontSize: '0.8rem' }}>
                                  <thead>
                                    <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                                      <th style={{ textAlign: 'left', padding: '4px 8px', width: '22%', color: '#6b7280' }}>Field</th>
                                      <th style={{ textAlign: 'left', padding: '4px 8px', width: '39%', color: '#6b7280' }}>Before (parent)</th>
                                      <th style={{ textAlign: 'left', padding: '4px 8px', width: '39%', color: '#6b7280' }}>After (this request)</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {diffs.map(({ label, old, cur, format }) => (
                                      <tr key={label} style={{ borderBottom: '1px solid #f3f4f6', background: '#fffbeb' }}>
                                        <td style={{ padding: '5px 8px', fontWeight: '600', verticalAlign: 'top' }}>{label}</td>
                                        <td style={{ padding: '5px 8px', color: '#dc2626', verticalAlign: 'top', whiteSpace: format === 'list' ? 'normal' : 'pre-wrap', wordBreak: 'break-word' }}>
                                          {format === 'date' && old ? formatDateTime(old) : (old || '—')}
                                        </td>
                                        <td style={{ padding: '5px 8px', color: '#15803d', verticalAlign: 'top', whiteSpace: format === 'list' ? 'normal' : 'pre-wrap', wordBreak: 'break-word' }}>
                                          {format === 'date' && cur ? formatDateTime(cur) : (cur || '—')}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              )}
                            </>
                          ) : null}
                        </div>
                      )
                    })() : null}
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
                        Notes are required for rejection. For approvals, notes are optional except High/Critical BU approvals.
                      </div>
                    </>
                  ) : null}

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: showActionNotesBox ? '8px' : 0 }}>
                    {availableActions.length === 0 && !canModify && !canCloseRejected && !extendWindowInfo && !canEditDraft && !canDeleteDraft && !canRemediate ? <span className="meta">No actions available for this exception in your current role/state.</span> : null}
                    {availableActions.map(([actionKey, config]) => (
                      <button
                        key={actionKey}
                        className="btn"
                        style={{ width: 'auto' }}
                        onClick={() => runAction(actionKey)}
                      >
                        {config.label}
                        {actionRequiresNotes(actionKey, selected) ? <span className="error" style={{ display: 'inline', marginLeft: '4px', marginBottom: 0 }}>*</span> : null}
                      </button>
                    ))}
                    {canModify ? (
                      <button
                        className="btn"
                        style={{ width: 'auto' }}
                        onClick={requestModification}
                        disabled={modifyLoading}
                      >
                        {modifyLoading ? 'Creating...' : 'Request Modification'}
                      </button>
                    ) : null}
                    {canCloseRejected ? (
                      <button
                        className="btn btn-secondary"
                        style={{ width: 'auto' }}
                        onClick={closeRejected}
                        disabled={closeRejectedLoading}
                      >
                        {closeRejectedLoading ? 'Closing...' : 'Close Request'}
                      </button>
                    ) : null}
                    {extendWindowInfo ? (
                      extendWindowInfo.open ? (
                        <button
                          className="btn"
                          style={{ width: 'auto' }}
                          onClick={requestExtension}
                          disabled={extendLoading}
                        >
                          {extendLoading ? 'Creating...' : 'Request Extension'}
                        </button>
                      ) : (
                        <button
                          className="btn btn-secondary"
                          style={{ width: 'auto', cursor: 'not-allowed', opacity: 0.65 }}
                          disabled
                          title={`Extension window opens at ${formatDateTimeCompact(extendWindowInfo.opensAt)}`}
                        >
                          Request Extension (opens {formatDateTime(extendWindowInfo.opensAt)})
                        </button>
                      )
                    ) : null}
                    {canEditDraft ? (
                      <button
                        className="btn"
                        style={{ width: 'auto' }}
                        onClick={() => navigate(`/exceptions/${selected.id}/edit`)}
                      >
                        Edit Draft
                      </button>
                    ) : null}
                    {canDeleteDraft ? (
                      <button
                        className="btn btn-secondary"
                        style={{ width: 'auto', color: '#dc2626', borderColor: '#dc2626' }}
                        onClick={deleteDraft}
                        disabled={deleteDraftLoading}
                      >
                        {deleteDraftLoading ? 'Deleting...' : 'Delete Draft'}
                      </button>
                    ) : null}
                  </div>
                  {actionError ? <div className="error" style={{ marginTop: '8px' }}>{actionError}</div> : null}
                  {modifyError ? <div className="error" style={{ marginTop: '8px' }}>{modifyError}</div> : null}
                  {extendError ? <div className="error" style={{ marginTop: '8px' }}>{extendError}</div> : null}
                  {closeRejectedError ? <div className="error" style={{ marginTop: '8px' }}>{closeRejectedError}</div> : null}
                  {deleteDraftError ? <div className="error" style={{ marginTop: '8px' }}>{deleteDraftError}</div> : null}

                  {canRemediate ? (
                    <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
                      <div className="meta" style={{ marginBottom: '6px', fontWeight: 500 }}>Remediate &amp; Close</div>
                      <div className="meta" style={{ marginBottom: '8px' }}>
                        Document the remediation steps taken and permanently close this exception. This cannot be undone.
                      </div>
                      <textarea
                        placeholder="Describe the remediation steps taken (required)"
                        value={remediateNotes}
                        onChange={(e) => setRemediateNotes(e.target.value)}
                        rows={3}
                        style={{ width: '100%', boxSizing: 'border-box', marginBottom: '8px', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem', resize: 'vertical' }}
                      />
                      <button
                        className="btn btn-secondary"
                        style={{ width: 'auto', color: '#dc2626', borderColor: '#dc2626' }}
                        onClick={remediateAndClose}
                        disabled={remediateLoading || !remediateNotes.trim()}
                      >
                        {remediateLoading ? 'Closing...' : 'Remediate & Close'}
                      </button>
                      {remediateError ? <div className="error" style={{ marginTop: '8px' }}>{remediateError}</div> : null}
                    </div>
                  ) : null}
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
                            onClick={() => setShowEndDateEditor((current) => !current)}
                          >
                            {showEndDateEditor ? 'Cancel' : 'Update End Date'}
                          </button>
                        ) : null}
                      </div>
                    </div>

                    {canUpdateEndDate && showEndDateEditor ? (
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
                            {updatingEndDate ? 'Updating...' : 'Save End Date'}
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
                        {auditLogs.filter(l => l.action_type === 'MODIFY' || l.action_type === 'EXTEND').length > 0
                          ? ` · ${auditLogs.filter(l => l.action_type === 'MODIFY' || l.action_type === 'EXTEND').length} superseding request(s) recorded.`
                          : null}
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
                              <span><strong>{getAuditActionLabel(log)}</strong></span>
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
                {unreadCount > 0 && (
                  <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={markAllRead}>
                    Mark all read
                  </button>
                )}
                <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={loadNotifications}>
                  Refresh
                </button>
                <button className="btn btn-secondary" style={{ width: 'auto' }} onClick={() => setNotificationsOpen(false)}>
                  Close
                </button>
              </div>
            </div>

            {notifications.length === 0 ? <div className="meta">No notifications right now.</div> : null}

            <div className="notification-list notification-list-scroll">
              {notifications.map((item) => (
                <div
                  key={item.id}
                  className={`notification-item${!item.is_read ? ' unread' : ''}`}
                >
                  <button
                    type="button"
                    className="notification-item-body"
                    onClick={() => {
                      if (!item.is_read) markRead(item.id)
                      if (item.exception_id) setSelectedId(item.exception_id)
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
                    <div className="meta">{formatDateTime(item.created_at)}</div>
                  </button>
                  {!item.is_read && (
                    <button
                      type="button"
                      className="notification-dismiss-btn"
                      title="Dismiss"
                      onClick={(e) => {
                        e.stopPropagation()
                        markRead(item.id)
                      }}
                    >
                      ×
                    </button>
                  )}
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