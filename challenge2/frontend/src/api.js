import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
})

// Attach JWT token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sc_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('sc_token')
      localStorage.removeItem('sc_org')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
}

export const sitesApi = {
  list: () => api.get('/sites'),
}

export const solarApi = {
  readings: (siteId, hours = 24) => api.get('/solar/readings', { params: { site_id: siteId, hours } }),
  latest: (siteId) => api.get('/solar/latest', { params: { site_id: siteId } }),
}

export const evApi = {
  sessions: (siteId, hours = 24) => api.get('/ev/sessions', { params: { site_id: siteId, hours } }),
}

export const dashboardApi = {
  summary: () => api.get('/dashboard/summary'),
}

export const anomalyApi = {
  list: (resolved = false) => api.get('/anomalies', { params: { resolved } }),
  resolve: (id) => api.post(`/anomalies/${id}/resolve`),
}

export const reportsApi = {
  monthlyPdf: (year, month) => api.get('/reports/monthly-pdf', {
    params: { year, month },
    responseType: 'blob',
  }),
  weeklyDigest: (siteId) => api.get('/reports/weekly-digest', { params: { site_id: siteId } }),
}

export const ecisApi = {
  calculate: (siteId, year, month) => api.get('/ecis/calculate', {
    params: { site_id: siteId, year, month },
  }),
}

export const adminApi = {
  injectFault: (siteId, reductionPct = 60) =>
    api.post('/admin/inject-fault', null, { params: { site_id: siteId, reduction_pct: reductionPct } }),
  clearFault: (siteId) =>
    api.post('/admin/clear-fault', null, { params: { site_id: siteId } }),
}

export default api
