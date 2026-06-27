import axios from 'axios'

function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : ''
}

const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

http.interceptors.request.use(config => {
  if (['post', 'put', 'patch', 'delete'].includes(config.method)) {
    config.headers['X-CSRFToken'] = getCsrfToken()
  }
  return config
})

export const accountsApi = {
  list: () => http.get('/accounts/'),
  create: (data) => http.post('/accounts/', data),
  get: (id) => http.get(`/accounts/${id}/`),
  startSession: (id) => http.post(`/accounts/${id}/start-session/`),
  getQR: (id) => http.get(`/accounts/${id}/qr/`),
  disconnect: (id) => http.post(`/accounts/${id}/disconnect/`),
  delete: (id) => http.delete(`/accounts/${id}/`),
  updateSettings: (id, data) => http.patch(`/accounts/${id}/update-settings/`, data),
  export: (id) => http.get(`/accounts/${id}/export/`, { responseType: 'blob' }),
  storage: (id) => http.get(`/accounts/${id}/storage/`),
  deleteMessages: (id) => http.post(`/accounts/${id}/delete-messages/`),
  deleteMedia: (id) => http.post(`/accounts/${id}/delete-media/`),
  deleteAllMessages: () => http.post('/accounts/delete-all-messages/'),
  deleteAllMedia: () => http.post('/accounts/delete-all-media/'),
  backupMedia: (id) => http.get(`/accounts/${id}/backup-media/`, { responseType: 'blob' }),
  restoreMessages: (id, file) => {
    const fd = new FormData(); fd.append('file', file)
    return http.post(`/accounts/${id}/restore-messages/`, fd)
  },
  restoreMedia: (id, file) => {
    const fd = new FormData(); fd.append('file', file)
    return http.post(`/accounts/${id}/restore-media/`, fd)
  },
  setAutoDownload: (id, enabled) => http.post(`/accounts/${id}/set-auto-download/`, { enabled }),
  setAutoDownloadAll: (enabled) => http.post('/accounts/set-auto-download-all/', { enabled }),
}

export const chatsApi = {
  list: (params) => http.get('/chats/', { params }),
  messages: (id, params = {}) => http.get(`/chats/${id}/messages/`, { params }),
  markRead: (id) => http.post(`/chats/${id}/mark-read/`),
  markAllRead: (accountId) => http.post('/chats/mark-all-read/', {}, { params: accountId ? { account: accountId } : {} }),
  info: (id) => http.get(`/chats/${id}/info/`),
  groupInfo: (id) => http.get(`/chats/${id}/group-info/`),
}

export const activityApi = {
  list: (params) => http.get('/activity/', { params }),
  clearAll: (params) => http.post('/activity/clear-all/', {}, { params }),
}

export const messageLogsApi = {
  list:  (accountId, params) => http.get(`/accounts/${accountId}/message-logs/`, { params }),
  clear: (accountId)         => http.delete(`/accounts/${accountId}/message-logs/`),
}

export const aiProvidersApi = {
  list:       ()         => http.get('/ai-providers/'),
  get:        (id)       => http.get(`/ai-providers/${id}/`),
  create:     (data)     => http.post('/ai-providers/', data),
  update:     (id, data) => http.patch(`/ai-providers/${id}/`, data),
  delete:     (id)       => http.delete(`/ai-providers/${id}/`),
  activate:   (id)       => http.post(`/ai-providers/${id}/activate/`),
  deactivate: (id)       => http.post(`/ai-providers/${id}/deactivate/`),
  test:       (id)       => http.post(`/ai-providers/${id}/test/`),
  meta:       ()         => http.get('/ai-providers/meta/'),
}
