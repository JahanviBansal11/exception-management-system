import { api } from './apiClient'

export const securityService = {
  getUsers: () => api.get('/api/security/users/'),
  createUser: (payload) => api.post('/api/security/users/', payload),
  updateUser: (id, payload) => api.patch(`/api/security/users/${id}/`, payload),
  
  getAuditList: (params) => api.get('/api/security/audit-list/', { params }),
  getAuditTrail: (params) => api.get('/api/security/audit-trail/', { params }),
}
