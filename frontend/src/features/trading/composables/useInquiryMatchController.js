import { computed, ref } from 'vue'
import { useDraggableDialog } from './useDraggableDialog'

function normalize(value) {
  return (value || '').toLowerCase().replace(/[^a-z0-9]/g, '')
}

export function useInquiryMatchController({ api, products, buildLines }) {
  const target = ref(null)
  const query = ref('')
  const results = ref(null)
  const loading = ref(false)
  const error = ref('')
  const drag = useDraggableDialog()

  const activeLine = computed(() => {
    if (!target.value?.lines?.length) return null
    return target.value.lines.find(line => line.index === target.value.selectedIndex) || target.value.lines[0]
  })

  const filteredProducts = computed(() => {
    const search = query.value.trim().toLowerCase()
    if (!search) return products.value || []
    return (products.value || []).filter(product =>
      (product.name || '').toLowerCase().includes(search)
      || (product.brand || '').toLowerCase().includes(search)
    )
  })

  function resetSearch() {
    results.value = null
    error.value = ''
    loading.value = false
  }

  function openHint(inquiry, hint) {
    target.value = {
      inq: inquiry,
      lines: [{ index: hint.index, name: hint.name, mismatch: !!hint.mismatch, unmatched: false }],
      selectedIndex: hint.index,
    }
    query.value = hint.name || ''
    resetSearch()
    drag.reset()
  }

  function openManual(inquiry) {
    const lines = buildLines(inquiry)
    if (!lines.length) return
    const preferred = lines.find(line => line.unmatched || line.mismatch) || lines[0]
    target.value = { inq: inquiry, lines, selectedIndex: preferred.index }
    query.value = preferred.name || ''
    resetSearch()
    drag.reset()
  }

  function close() {
    target.value = null
    query.value = ''
    resetSearch()
  }

  function toggle(inquiry, hint) {
    const isOpen = target.value?.inq === inquiry
      && target.value?.lines?.length === 1
      && target.value?.selectedIndex === hint.index
    if (isOpen) return close()
    openHint(inquiry, hint)
  }

  function selectLine(index) {
    if (!target.value) return
    const next = target.value.lines.find(line => line.index === index)
    if (!next) return
    target.value = { ...target.value, selectedIndex: index }
    query.value = next.name || ''
    resetSearch()
  }

  function directSearch(value) {
    const normalizedQuery = normalize(value)
    if (!normalizedQuery) return []
    return (products.value || []).filter(product => {
      const normalizedName = normalize(product.name)
      if (normalizedQuery === normalizedName || normalizedName.includes(normalizedQuery) || normalizedQuery.includes(normalizedName)) return true
      return (product.aliases || []).some(alias => normalize(alias) === normalizedQuery)
    })
  }

  async function embeddingSearch(value) {
    loading.value = true
    error.value = ''
    results.value = null
    try {
      const { data } = await api.searchProductEmbeddings({ q: value })
      results.value = (data.results || []).map(result => ({
        product: result.product,
        source: 'embedding',
        distance: result.distance,
      }))
    } catch (requestError) {
      error.value = 'Search failed: ' + (requestError.response?.data?.detail || requestError.message)
      results.value = []
    } finally {
      loading.value = false
    }
  }

  async function autoMatch(inquiry, hint) {
    openHint(inquiry, hint)
    const direct = directSearch(hint.name)
    if (direct.length) {
      results.value = direct.map(product => ({ product, source: 'direct' }))
      return
    }
    await embeddingSearch(hint.name)
  }

  async function search() {
    const line = activeLine.value
    if (!line) return
    const value = query.value.trim() || line.name
    if (value) await embeddingSearch(value)
  }

  async function selectProduct(product) {
    const currentTarget = target.value
    const line = activeLine.value
    if (!currentTarget || !line) return
    const { data } = await api.correctMatch(currentTarget.inq.id, { index: line.index, product_id: product.id })
    currentTarget.inq.products = data.products
    target.value = null
  }

  return {
    target, query, results, loading, error, activeLine, filteredProducts,
    drag: drag.position, startDrag: drag.start, stopDrag: drag.stop,
    openHint, openManual, toggle, selectLine, close, autoMatch, search, selectProduct,
  }
}
