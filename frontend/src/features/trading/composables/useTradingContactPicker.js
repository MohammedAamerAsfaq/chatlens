import { ref } from 'vue'

const PAGE_SIZE = 10

function displayLabel(contact) {
  return contact?.display_name
    || contact?.push_name
    || contact?.phone_number
    || contact?.wa_contact_id
    || `Contact ${contact?.id || ''}`
}

function createPickerState() {
  return {
    selected: ref(''),
    search: ref(''),
    open: ref(false),
    loading: ref(false),
    page: ref(1),
    totalPages: ref(1),
    options: ref([]),
  }
}

export function useTradingContactPicker({ accountId, listContacts, onSelectionChange }) {
  const states = { buy: createPickerState(), sell: createPickerState() }
  const timers = { buy: null, sell: null }
  const stateFor = type => states[type === 'buy' ? 'buy' : 'sell']

  async function load(type, { reset = false } = {}) {
    const state = stateFor(type)
    if (state.loading.value) return
    if (!reset && state.page.value >= state.totalPages.value) return

    if (reset) {
      state.page.value = 1
      state.totalPages.value = 1
      state.options.value = []
    } else {
      state.page.value += 1
    }

    state.loading.value = true
    try {
      const params = { page: state.page.value, page_size: PAGE_SIZE, ordering: 'display_name', type: 'phone' }
      if (accountId.value) params.account = accountId.value
      if (state.search.value.trim()) params.search = state.search.value.trim()

      const { data } = await listContacts(params)
      const incoming = data.results ?? data
      state.totalPages.value = data.total_pages || Math.max(1, Math.ceil((data.count || incoming.length) / PAGE_SIZE))
      const seen = new Set(state.options.value.map(contact => contact.id))
      const merged = reset ? [] : [...state.options.value]
      for (const contact of incoming) {
        if (seen.has(contact.id)) continue
        merged.push(contact)
        seen.add(contact.id)
      }
      state.options.value = merged
    } finally {
      state.loading.value = false
    }
  }

  function open(type) {
    const state = stateFor(type)
    state.open.value = true
    if (!state.options.value.length) load(type, { reset: true })
  }

  function search(type) {
    clearTimeout(timers[type])
    timers[type] = setTimeout(() => load(type, { reset: true }), 250)
  }

  function loadNext(type, event) {
    const element = event.target
    if (element.scrollTop + element.clientHeight >= element.scrollHeight - 20) load(type)
  }

  function select(type, contact) {
    const state = stateFor(type)
    state.selected.value = contact.id
    state.search.value = displayLabel(contact)
    state.open.value = false
    onSelectionChange(type)
  }

  function clear(type, { notify = true, reload = false } = {}) {
    const state = stateFor(type)
    state.selected.value = ''
    state.search.value = ''
    state.open.value = false
    if (reload) load(type, { reset: true })
    if (notify) onSelectionChange(type)
  }

  function clearAll(options = {}) {
    clear('buy', { notify: false, ...options })
    clear('sell', { notify: false, ...options })
  }

  function closeOnOutsideClick(event) {
    if (event.target.closest?.('.contact-picker')) return
    states.buy.open.value = false
    states.sell.open.value = false
  }

  function destroy() {
    clearTimeout(timers.buy)
    clearTimeout(timers.sell)
  }

  return {
    buy: states.buy,
    sell: states.sell,
    load,
    open,
    search,
    loadNext,
    select,
    clear,
    clearAll,
    closeOnOutsideClick,
    destroy,
  }
}
