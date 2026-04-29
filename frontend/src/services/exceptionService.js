import { api } from './apiClient'

export const exceptionService = {
  getExceptions: () => api.get('/api/exceptions/'),
  getExceptionDetails: (id) => api.get(`/api/exceptions/${id}/`),
  getAuditLogs: (id, limit = 100) => api.get(`/api/exceptions/${id}/audit_logs/?limit=${limit}`),
  
  // Dashboard & Workflow
  getSummary: () => api.get('/api/worklist/summary/'),
  getNotifications: () => api.get('/api/worklist/notifications/'),

  // Actions
  submit: (id, notes = '') => api.post(`/api/exceptions/${id}/submit/`, { notes }),
  buApprove: (id, notes = '') => api.post(`/api/exceptions/${id}/bu_approve/`, { notes }),
  buReject: (id, notes = '') => api.post(`/api/exceptions/${id}/bu_reject/`, { notes }),
  riskAssess: (id, notes = '') => api.post(`/api/exceptions/${id}/risk_assess/`, { notes }),
  riskReject: (id, notes = '') => api.post(`/api/exceptions/${id}/risk_reject/`, { notes }),
  close: (id, notes = '') => api.post(`/api/exceptions/${id}/close/`, { notes }),

  // Edits
  updateEndDate: (id, isoEndDate, notes) => 
    api.post(`/api/exceptions/${id}/update_end_date/`, {
      exception_end_date: isoEndDate,
      notes: notes,
    }),
  createException: (payload) => api.post('/api/exceptions/', payload)
}
