import { computed, ref } from 'vue'
import { useDraggableDialog } from './useDraggableDialog'

export function useMarketPartiesController(api) {
  const open = ref(false)
  const inquiry = ref(null)
  const products = ref([])
  const loading = ref(false)
  const error = ref('')
  const actionLabel = ref('')
  const source = ref('inventory')
  const method = ref('exact')
  const drag = useDraggableDialog()

  const title = computed(() => inquiry.value?.inquiry_type === 'sell' ? 'Potential Buyers' : 'Available Sellers')

  async function load(inquiryId) {
    loading.value = true
    error.value = ''
    try {
      const { data } = await api.getInquiryMarketParties(inquiryId, {
        limit: 25,
        market_source: source.value,
        market_method: method.value,
      })
      products.value = data.products || []
      inquiry.value = data.inquiry || inquiry.value
      actionLabel.value = data.action_label || ''
      source.value = data.source || source.value
      method.value = data.method || method.value
    } catch (requestError) {
      error.value = requestError.response?.data?.detail || requestError.message || 'Failed to load market offers'
    } finally {
      loading.value = false
    }
  }

  async function show(target) {
    inquiry.value = target
    open.value = true
    source.value = 'inventory'
    method.value = 'exact'
    drag.reset()
    await load(target.id)
  }

  function close() {
    open.value = false
    inquiry.value = null
    products.value = []
    error.value = ''
    drag.stop()
  }

  async function setSource(value) {
    if (source.value === value || !inquiry.value) return
    source.value = value
    await load(inquiry.value.id)
  }

  async function setMethod(value) {
    if (method.value === value || !inquiry.value) return
    method.value = value
    await load(inquiry.value.id)
  }

  return {
    open, inquiry, products, loading, error, actionLabel, source, method, title,
    drag: drag.position, startDrag: drag.start, stopDrag: drag.stop,
    show, close, load, setSource, setMethod,
  }
}
