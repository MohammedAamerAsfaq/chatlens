import { computed, ref } from 'vue'

export const feedPageSizeOptions = [25, 50, 100, 200]
export const feedSortOptions = [
  { value: 'latest', label: 'Latest first' },
  { value: 'oldest', label: 'Oldest first' },
]
export const feedDateOptions = [
  { value: 'last_30_minutes', label: 'Last 30 mins' },
  { value: 'last_hour', label: 'Last hour' },
  { value: 'last_2_hours', label: 'Last 2 hours' },
  { value: 'last_5_hours', label: 'Last 5 hours' },
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'this_week', label: 'This week' },
  { value: 'last_week', label: 'Last week' },
  { value: 'this_month', label: 'This month' },
  { value: 'last_month', label: 'Last month' },
]

function startOfWeek(date) {
  const result = new Date(date)
  const day = result.getDay() || 7
  result.setDate(result.getDate() - day + 1)
  return result
}

export function feedDateRangeParams(value, now = new Date()) {
  const todayStart = new Date(now)
  todayStart.setHours(0, 0, 0, 0)
  const start = new Date(todayStart)
  const end = new Date(todayStart)
  end.setDate(end.getDate() + 1)
  const rollingMinutes = { last_30_minutes: 30, last_hour: 60, last_2_hours: 120, last_5_hours: 300 }

  if (rollingMinutes[value]) {
    start.setTime(now.getTime() - rollingMinutes[value] * 60 * 1000)
    return { date_from: start.toISOString(), date_to: now.toISOString() }
  }
  if (value === 'yesterday') {
    start.setDate(start.getDate() - 1)
    end.setTime(todayStart.getTime())
  } else if (value === 'this_week') {
    start.setTime(startOfWeek(todayStart).getTime())
  } else if (value === 'last_week') {
    start.setTime(startOfWeek(todayStart).getTime())
    start.setDate(start.getDate() - 7)
    end.setTime(start.getTime())
  } else if (value === 'this_month') {
    start.setDate(1)
  } else if (value === 'last_month') {
    start.setMonth(todayStart.getMonth() - 1, 1)
    end.setTime(todayStart.getTime())
    end.setDate(1)
  }
  return { date_from: start.toISOString(), date_to: end.toISOString() }
}

function createFeed() {
  const items = ref([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(50)
  return {
    items,
    total,
    page,
    pageSize,
    sort: ref('latest'),
    dateRange: ref('today'),
    loading: ref(false),
    totalPages: computed(() => Math.max(1, Math.ceil(total.value / pageSize.value))),
  }
}

export function useTradingFeedController({ api, accountId, status, contacts, resetContact }) {
  const stats = ref({})
  const products = ref([])
  const lastUpdate = ref(null)
  const feeds = { buy: createFeed(), sell: createFeed() }
  const feedFor = type => feeds[type === 'buy' ? 'buy' : 'sell']

  function params(type) {
    const feed = feedFor(type)
    const contact = contacts[type].value
    return {
      ...(accountId.value ? { account: accountId.value } : {}),
      status: status.value,
      type,
      page: feed.page.value,
      page_size: feed.pageSize.value,
      sort: feed.sort.value,
      ...(contact ? { contact } : {}),
      ...feedDateRangeParams(feed.dateRange.value),
    }
  }

  async function load(type) {
    const feed = feedFor(type)
    feed.loading.value = true
    try {
      const { data } = await api.getOpenFeed(params(type))
      feed.items.value = data.results
      feed.total.value = data.count
    } finally {
      feed.loading.value = false
    }
  }

  async function refresh() {
    const accountParams = accountId.value ? { account: accountId.value } : {}
    const [statsResponse, buyResponse, sellResponse, productsResponse] = await Promise.all([
      api.getStats(accountParams),
      api.getOpenFeed(params('buy')),
      api.getOpenFeed(params('sell')),
      api.listProducts({ page_size: 1000, is_active: true }),
    ])
    stats.value = statsResponse.data
    feeds.buy.items.value = buyResponse.data.results
    feeds.buy.total.value = buyResponse.data.count
    feeds.sell.items.value = sellResponse.data.results
    feeds.sell.total.value = sellResponse.data.count
    products.value = productsResponse.data.results ?? productsResponse.data
    lastUpdate.value = Date.now()
  }

  function reloadFromFirstPage(type) {
    feedFor(type).page.value = 1
    return load(type)
  }

  function setDateRange(type) {
    resetContact(type)
    return reloadFromFirstPage(type)
  }

  function changePage(type, page) {
    const feed = feedFor(type)
    feed.page.value = Math.min(Math.max(1, page), feed.totalPages.value)
    return load(type)
  }

  function resetPages() {
    feeds.buy.page.value = 1
    feeds.sell.page.value = 1
  }

  return {
    stats,
    products,
    lastUpdate,
    buy: feeds.buy,
    sell: feeds.sell,
    refresh,
    load,
    reloadFromFirstPage,
    setDateRange,
    changePage,
    resetPages,
  }
}
