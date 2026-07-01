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

export const contactsApi = {
  list:   (params)      => http.get('/contacts/', { params }),
  stats:  (params)      => http.get('/contacts/stats/', { params }),
  update: (id, data)    => http.patch(`/contacts/${id}/`, data),
}

export const embeddingsApi = {
  status:   (params) => http.get('/intelligence/embedding-status/', { params }),
  backfill: (data)   => http.post('/intelligence/backfill/', data),
}

export const droppedApi = {
  list:     (params) => http.get('/dropped-messages/', { params }),
  clearAll: (params) => http.post('/dropped-messages/clear-all/', {}, { params }),
}

export const groupsApi = {
  list:       (params)    => http.get('/groups/', { params }),
  get:        (id)        => http.get(`/groups/${id}/`),
  stats:      (params)    => http.get('/groups/stats/', { params }),
  syncGroups: (accountId) => http.post('/groups/sync/', { account: accountId }),
}

export const tradingApi = {
  // Products
  listProducts:   (params)      => http.get('/products/', { params }),
  createProduct:  (data)        => http.post('/products/', data),
  updateProduct:  (id, data)    => http.patch(`/products/${id}/`, data),
  deleteProduct:  (id)          => http.delete(`/products/${id}/`),
  getProductStats:(params)      => http.get('/products/stats/', { params }),

  // Bulk product helpers
  parseProductText:   (text)     => http.post('/products/parse-text/', { text }),
  bulkCreateProducts: (products) => http.post('/products/bulk-create/', { products }),

  // AI Prompts
  listPrompts:      ()            => http.get('/prompts/'),
  savePrompt:       (key, body)   => http.patch(`/prompts/${key}/`, { body }),
  resetPrompt:      (key)         => http.delete(`/prompts/${key}/`),
  getActiveAgent:   ()            => http.get('/prompts/active-agent/'),
  saveAgentPricing: (data)        => http.patch('/prompts/active-agent/', data),
  listAgentLogs:    (params)      => http.get('/agent-logs/', { params }),

  // Inquiries
  listInquiries:          (params)      => http.get('/inquiries/', { params }),
  getInquiry:             (id)          => http.get(`/inquiries/${id}/`),
  updateInquiry:          (id, data)    => http.patch(`/inquiries/${id}/`, data),
  getStats:               (params)      => http.get('/inquiries/stats/', { params }),
  getOpenFeed:            (params)      => http.get('/inquiries/open-feed/', { params }),
  getClassificationActivity: (params)  => http.get('/inquiries/classification-activity/', { params }),
  backfillClassify:       (data)        => http.post('/inquiries/backfill-classify/', data),
  retryInquiries:         (data)        => http.post('/inquiries/retry-inquiries/', data),
}

export const aiProvidersApi = {
  list:        ()              => http.get('/ai-providers/'),
  get:         (id)            => http.get(`/ai-providers/${id}/`),
  create:      (data)          => http.post('/ai-providers/', data),
  update:      (id, data)      => http.patch(`/ai-providers/${id}/`, data),
  delete:      (id)            => http.delete(`/ai-providers/${id}/`),
  activate:    (id)            => http.post(`/ai-providers/${id}/activate/`),
  deactivate:  (id)            => http.post(`/ai-providers/${id}/deactivate/`),
  test:        (id)            => http.post(`/ai-providers/${id}/test/`),
  meta:        ()              => http.get('/ai-providers/meta/'),
  fetchModels: (data)          => http.post('/ai-providers/fetch-models/', data),
}
