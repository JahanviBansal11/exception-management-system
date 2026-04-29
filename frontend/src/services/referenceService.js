import { api } from './apiClient'

export const referenceService = {
  getReferenceData: () => api.get('/api/reference/'),
  getAssignmentDefaults: (buId, etId) => {
    const params = new URLSearchParams()
    if (buId) params.append('business_unit_id', buId)
    if (etId) params.append('exception_type_id', etId)
    return api.get(`/api/exceptions/get_assignment_defaults/?${params.toString()}`)
  },
}
