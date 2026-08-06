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

http.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401 && !err.config?.url?.includes('/auth/')) {
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export const authApi = {
  login:  (data)  => http.post('/auth/login/',  data),
  logout: ()      => http.post('/auth/logout/'),
  me:     ()      => http.get('/auth/me/'),
  selectCompany: (company_id) => http.post('/auth/select-company/', { company_id }),
}

export const accountsApi = {
  list: () => http.get('/accounts/'),
  create: (data) => http.post('/accounts/', data),
  get: (id) => http.get(`/accounts/${id}/`),
  startSession: (id) => http.post(`/accounts/${id}/start-session/`),
  getQR: (id) => http.get(`/accounts/${id}/qr/`),
  disconnect: (id) => http.post(`/accounts/${id}/disconnect/`),
  softDisconnect: (id) => http.post(`/accounts/${id}/soft-disconnect/`),
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
  syncProgress: (id) => http.get(`/accounts/${id}/sync-progress/`),
}

export const chatsApi = {
  list: (params) => http.get('/chats/', { params }),
  messages: (id, params = {}) => http.get(`/chats/${id}/messages/`, { params }),
  markRead: (id) => http.post(`/chats/${id}/mark-read/`),
  markAllRead: (accountId) => http.post('/chats/mark-all-read/', {}, { params: accountId ? { account: accountId } : {} }),
  info: (id) => http.get(`/chats/${id}/info/`),
  groupInfo: (id) => http.get(`/chats/${id}/group-info/`),
  setAiParsing: (id, value) => http.patch(`/chats/${id}/set-ai-parsing/`, { ai_parsing: value }),
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
  list:            (params)       => http.get('/contacts/', { params }),
  stats:           (params)       => http.get('/contacts/stats/', { params }),
  update:          (id, data)     => http.patch(`/contacts/${id}/`, data),
  setAiParsing:    (id, value)    => http.patch(`/contacts/${id}/set-ai-parsing/`, { ai_parsing: value }),
  confirmCategory: (id, category) => http.patch(`/contacts/${id}/confirm-category/`, { category }),
}

export const embeddingsApi = {
  status:   (params) => http.get('/intelligence/embedding-status/', { params }),
  backfill: (data)   => http.post('/intelligence/backfill/', data),
}

export const droppedApi = {
  list:     (params) => http.get('/dropped-messages/', { params }),
  clearAll: (params) => http.post('/dropped-messages/clear-all/', {}, { params }),
}

export const workerAlertsApi = {
  list:               (params) => http.get('/worker-alerts/', { params }),
  unacknowledgedCount: ()      => http.get('/worker-alerts/unacknowledged-count/'),
  acknowledge:        (id)     => http.post(`/worker-alerts/${id}/acknowledge/`),
  acknowledgeAll:     (params) => http.post('/worker-alerts/acknowledge-all/', {}, { params }),
}

export const baileysEventsApi = {
  list: (params) => http.get('/baileys-events/', { params }),
}

export const stuckReceiptsApi = {
  list:            (params) => http.get('/stuck-receipts/', { params }),
  unresolvedCount:  ()      => http.get('/stuck-receipts/unresolved-count/'),
  resolve:          (id)    => http.post(`/stuck-receipts/${id}/resolve/`),
}

export const unresolvedMessagesApi = {
  list:               (params) => http.get('/unresolved-messages/', { params }),
  counts:             (params) => http.get('/unresolved-messages/counts/', { params }),
  retryResolution:    (id)     => http.post(`/unresolved-messages/${id}/retry-resolution/`),
  resolveWithContact: (id, contactId) => http.post(`/unresolved-messages/${id}/resolve-with-contact/`, { contact_id: contactId }),
  createContactAndResolve: (id, data) => http.post(`/unresolved-messages/${id}/create-contact-and-resolve/`, data),
  dismiss:            (id, reason) => http.post(`/unresolved-messages/${id}/dismiss/`, { reason }),
}

export const messageTraceApi = {
  list:  (params) => http.get('/message-trace/list/', { params }),
  trace: (accountId, providerMessageId) => http.get('/message-trace/', {
    params: { account: accountId, provider_message_id: providerMessageId },
  }),
}

export const groupsApi = {
  list:         (params)    => http.get('/groups/', { params }),
  get:          (id)        => http.get(`/groups/${id}/`),
  stats:        (params)    => http.get('/groups/stats/', { params }),
  syncGroups:   (accountId) => http.post('/groups/sync/', { account: accountId }),
  setAiParsing: (id, value) => http.patch(`/groups/${id}/set-ai-parsing/`, { ai_parsing: value }),
}

export const tradingApi = {
  // Products
  listProducts:   (params)      => http.get('/products/', { params }),
  createProduct:  (data)        => http.post('/products/', data),
  updateProduct:  (id, data)    => http.patch(`/products/${id}/`, data),
  deleteProduct:  (id)          => http.delete(`/products/${id}/`),
  getProductStats:(params)      => http.get('/products/stats/', { params }),

  // Product aliases — each one gets its own embedding (see backend ProductAliasEmbedding),
  // so these are managed live/independently of the main product create/update.
  listProductAliases:  (productId)         => http.get(`/products/${productId}/aliases/`),
  addProductAlias:     (productId, alias)  => http.post(`/products/${productId}/aliases/`, { alias }),
  deleteProductAlias:  (productId, aliasId) => http.delete(`/products/${productId}/aliases/${aliasId}/`),

  // Product attributes — hot-addable key/value pairs, independent of the main product
  // create/update, same live-CRUD pattern as aliases above.
  listProductAttributes:  (productId)                  => http.get(`/products/${productId}/attributes/`),
  addProductAttribute:    (productId, key, value)       => http.post(`/products/${productId}/attributes/`, { key, value }),
  updateProductAttribute: (productId, attributeId, patch) => http.patch(`/products/${productId}/attributes/${attributeId}/`, patch),
  deleteProductAttribute: (productId, attributeId)      => http.delete(`/products/${productId}/attributes/${attributeId}/`),

  // Bulk product helpers
  parseProductText:     (text)           => http.post('/products/parse-text/', { text }),
  bulkCreateProducts:   (products)       => http.post('/products/bulk-create/', { products }),
  parseInventory:       (cost_text, sale_text) => http.post('/products/parse-inventory/', { cost_text, sale_text }),
  bulkUpdateInventory:  (items)          => http.post('/products/bulk-update-inventory/', { items }),

  // AI-formatted price list (for the WhatsApp "Price List" button)
  getPriceList:         ()               => http.get('/products/price-list/'),
  regeneratePriceList:  ()               => http.post('/products/regenerate-price-list/'),

  // Product Price Update page — new, independent qty/cost + sale-price pipeline,
  // separate from parseInventory/bulkUpdateInventory above.
  parseQtyCost:    (text)  => http.post('/product-price-update/parse-qty-cost/', { text }),
  applyQtyCost:    (items) => http.post('/product-price-update/apply-qty-cost/', { items }),
  previewZeroQty:  (items) => http.post('/product-price-update/preview-zero-qty/', { items }),
  parseSalePrice:  (text)  => http.post('/product-price-update/parse-sale-price/', { text }),
  applySalePrice:  (items) => http.post('/product-price-update/apply-sale-price/', { items }),

  // Automated Price Updates (Sale Price tab) — watch rules + review queue
  listAutomationRules:   ()          => http.get('/automation-rules/'),
  createAutomationRule:  (data)      => http.post('/automation-rules/', data),
  updateAutomationRule:  (id, data)  => http.patch(`/automation-rules/${id}/`, data),
  deleteAutomationRule:  (id)        => http.delete(`/automation-rules/${id}/`),
  toggleAutomationRule:  (id)        => http.post(`/automation-rules/${id}/toggle/`),
  listPriceCaptures:     (params)    => http.get('/automated-price-captures/', { params }),
  captureSummary:        ()          => http.get('/automated-price-captures/summary/'),
  applyPriceCapture:     (id, items) => http.post(`/automated-price-captures/${id}/apply/`, items ? { items } : {}),
  ignorePriceCapture:    (id)        => http.post(`/automated-price-captures/${id}/ignore/`),

  // AI Prompts
  listPrompts:      ()            => http.get('/prompts/'),
  savePrompt:       (key, body)   => http.patch(`/prompts/${key}/`, { body }),
  resetPrompt:      (key)         => http.delete(`/prompts/${key}/`),
  getActiveAgent:   ()            => http.get('/prompts/active-agent/'),
  saveAgentPricing: (data)        => http.patch('/prompts/active-agent/', data),
  listAgentLogs:    (params)      => http.get('/agent-logs/', { params }),
  listAiParsingLogs: (params)     => http.get('/ai-parsing-logs/', { params }),
  listAiParseV2Logs: (params)     => http.get('/ai-parse-v2-logs/', { params }),

  // Inquiries
  listInquiries:          (params)      => http.get('/inquiries/', { params }),
  listInquiryProducts:    (params)      => http.get('/inquiry-products/', { params }),
  listNonInventoryProducts: (params)    => http.get('/non-inventory-products/', { params }),
  searchInquiryProductEmbeddings: (params) => http.get('/inquiry-products/search-embeddings/', { params }),
  backfillInquiryProductEmbeddings: (data) => http.post('/inquiry-products/backfill-embeddings/', data || {}),
  getInquiry:             (id)          => http.get(`/inquiries/${id}/`),
  getInquiryProductLines:  (id)          => http.get(`/inquiries/${id}/product-lines/`),
  createProductFromInquiryLine: (id, index, data) => http.post(`/inquiries/${id}/product-lines/${index}/create-product/`, data),
  createInquiryProductFromLine: (id, index) => http.post(`/inquiries/${id}/product-lines/${index}/create-inquiry/`),
  trackNonInventoryFromInquiryLine: (id, index) => http.post(`/inquiries/${id}/product-lines/${index}/track-non-inventory/`),
  updateInquiry:          (id, data)    => http.patch(`/inquiries/${id}/`, data),
  getStats:               (params)      => http.get('/inquiries/stats/', { params }),
  getOpenFeed:            (params)      => http.get('/inquiries/open-feed/', { params }),
  getClassificationActivity: (params)  => http.get('/inquiries/classification-activity/', { params }),
  backfillClassify:       (data)        => http.post('/inquiries/backfill-classify/', data),
  retryInquiries:         (data)        => http.post('/inquiries/retry-inquiries/', data),
  correctMatch:           (id, data)    => http.post(`/inquiries/${id}/correct-match/`, data),
  verifyMatch:            (id, data)    => http.post(`/inquiries/${id}/verify-match/`, data),
  searchProductEmbeddings: (params)    => http.get('/products/search-embeddings/', { params }),
  searchV2Candidates:      (params)    => http.get('/products/search-v2-candidates/', { params }),
  getEmbeddingStatus:      ()          => http.get('/products/embedding-status/'),
  backfillEmbeddings:      ()          => http.post('/products/backfill-embeddings/'),
  closeStaleInquiries:    (data)        => http.post('/inquiries/close-stale/', data),

  // Reports
  getReportSummary: (params) => http.get('/reports/summary/', { params }),
  getInventoryProductMentions: (params) => http.get('/reports/inventory-product-mentions/', { params }),

  // Trading settings (hot-settable plain UI values, not AI prompts)
  getWtsReplySettings: () => http.get('/trading-settings/wts-reply/'),
  setWtsReplySettings: (data) => http.put('/trading-settings/wts-reply/', data),
  getInquiryProductSaveSettings: () => http.get('/trading-settings/inquiry-products/'),
  setInquiryProductSaveSettings: (data) => http.put('/trading-settings/inquiry-products/', data),
  getV2MatchingSettings: () => http.get('/trading-settings/v2-matching/'),
  setV2MatchingSettings: (data) => http.put('/trading-settings/v2-matching/', data),
  getV2MatchingThresholds: () => http.get('/trading-settings/v2-matching/'),
  setV2MatchingThresholds: (data) => http.put('/trading-settings/v2-matching/', data),

  // Buying Inquiries (manual RFQ-to-suppliers workflow)
  listBuyingInquiries:  (params)     => http.get('/buying-inquiries/', { params }),
  createBuyingInquiry:  (data)       => http.post('/buying-inquiries/', data),
  updateBuyingInquiry:  (id, data)   => http.patch(`/buying-inquiries/${id}/`, data),
  deleteBuyingInquiry:  (id)         => http.delete(`/buying-inquiries/${id}/`),
  addSupplierToInquiry: (id, supplier_id) => http.post(`/buying-inquiries/${id}/add-supplier/`, { supplier_id }),

  askSupplierQuote:     (id)         => http.post(`/supplier-quotes/${id}/ask/`),
  updateSupplierQuote:  (id, data)   => http.patch(`/supplier-quotes/${id}/`, data),
  deleteSupplierQuote:  (id)         => http.delete(`/supplier-quotes/${id}/`),
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

export const tenantAdminApi = {
  listCompanies: () => http.get('/admin/companies/'),
  updateCompany: (id, data) => http.patch(`/admin/companies/${id}/`, data),
  enrollCompany: (data) => http.post('/admin/companies/enroll/', data),
  listUsers: (params) => http.get('/admin/users/', { params }),
  createUser: (data) => http.post('/admin/users/', data),
}
