import { useState, useCallback } from 'react'
import { exceptionService } from '../services/exceptionService'
import { useAuth } from '../useAuth' // or move useAuth.js to hooks

// Shared utility functions from the old DashboardPage
export function matchesView(item, view, userId) {
  if (!item || !view || !userId) return false

  const hideDraftsForView = ['approver', 'risk-owner', 'security'].includes(view)
  if (hideDraftsForView && item.status === 'Draft') return false

  if (view === 'security') return true
  if (view === 'requestor') return item.requested_by === userId
  if (view === 'approver') return item.assigned_approver === userId
  if (view === 'risk-owner') {
    if (item.risk_owner !== userId) return false
    if (item.status === 'AwaitingRiskOwner') return true
    if (['Approved', 'Rejected', 'ApprovalDeadlinePassed', 'Expired', 'Modified', 'Extended', 'Closed'].includes(item.status)) {
      return reachedRiskOwnerStage(item)
    }
    return false
  }

  return false
}

export function reachedRiskOwnerStage(item) {
  if (!item) return false
  const checkpoints = item.checkpoints || []
  const riskNotifiedCheckpoint = checkpoints.find((checkpoint) => checkpoint.checkpoint === 'risk_assessment_notified')
  return ['pending', 'completed', 'escalated'].includes(riskNotifiedCheckpoint?.status)
}

export function sortExceptions(items, sortKey) {
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

export function matchesKpi(item, kpiKey) {
  if (!kpiKey || kpiKey === 'my_queue_total') return true
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

export function useExceptions(view) {
  const { user } = useAuth()
  const [items, setItems] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selected, setSelected] = useState(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [actionError, setActionError] = useState('')

  const loadExceptions = useCallback(async (forcedExceptionId = null) => {
    setLoadingList(true)
    try {
      const response = await exceptionService.getExceptions()
      const results = response.data.results || []
      const filtered = results.filter((item) => matchesView(item, view, user?.id))
      setItems(filtered)
      
      setSelectedId((current) => {
        if (forcedExceptionId && filtered.some((item) => item.id === forcedExceptionId)) {
          return forcedExceptionId
        }
        return current ?? filtered[0]?.id ?? null
      })
    } finally {
      setLoadingList(false)
    }
  }, [view, user?.id])

  const loadExceptionDetail = useCallback(async (id) => {
    if (!id) {
      setSelected(null)
      return
    }
    setLoadingDetail(true)
    setActionError('')
    try {
      const response = await exceptionService.getExceptionDetails(id)
      setSelected(response.data)
    } catch (error) {
      setActionError(error?.response?.status === 404 ? 'You do not have access to this exception.' : 'Failed to load exception details.')
      setSelected(null)
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  return {
    items,
    selectedId,
    setSelectedId,
    selected,
    loadingList,
    loadingDetail,
    actionError,
    setActionError,
    loadExceptions,
    loadExceptionDetail
  }
}
