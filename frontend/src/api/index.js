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
}

export const chatsApi = {
  list: (params) => http.get('/chats/', { params }),
  messages: (id, params = {}) => http.get(`/chats/${id}/messages/`, { params }),
  markRead: (id) => http.post(`/chats/${id}/mark-read/`),
}

export const activityApi = {
  list: (params) => http.get('/activity/', { params }),
}
