import { ref } from 'vue'

export function useInquiryProductsController({ api, products, patchInquiry }) {
  const open = ref(false)
  const inquiry = ref(null)
  const lines = ref([])
  const loading = ref(false)
  const error = ref('')
  const creatingIndex = ref(null)
  const trackingIndex = ref(null)

  async function load(inquiryId) {
    loading.value = true
    error.value = ''
    try {
      const { data } = await api.getInquiryProductLines(inquiryId)
      lines.value = data.products || []
      inquiry.value = data.inquiry || inquiry.value
    } catch (requestError) {
      error.value = requestError.response?.data?.detail || requestError.message || 'Failed to load inquiry products'
    } finally {
      loading.value = false
    }
  }

  async function show(target) {
    inquiry.value = target
    open.value = true
    await load(target.id)
  }

  function close() {
    open.value = false
    inquiry.value = null
    lines.value = []
    error.value = ''
  }

  async function createProduct(line) {
    if (!inquiry.value) return
    creatingIndex.value = line.index
    error.value = ''
    try {
      const { data } = await api.createProductFromInquiryLine(
        inquiry.value.id,
        line.index,
        { brand: line.brand || '' },
      )
      if (data.product) {
        products.value = [data.product, ...products.value.filter(product => product.id !== data.product.id)]
      }
      if (data.inquiry) {
        inquiry.value = data.inquiry
        patchInquiry(data.inquiry)
      }
      await load(inquiry.value.id)
    } catch (requestError) {
      error.value = requestError.response?.data?.detail || requestError.message || 'Failed to create product'
    } finally {
      creatingIndex.value = null
    }
  }

  async function trackNonInventory(line) {
    if (!inquiry.value) return
    trackingIndex.value = line.index
    error.value = ''
    try {
      await api.trackNonInventoryFromInquiryLine(inquiry.value.id, line.index)
      await load(inquiry.value.id)
    } catch (requestError) {
      error.value = requestError.response?.data?.detail || requestError.message || 'Failed to track non-inventory product'
    } finally {
      trackingIndex.value = null
    }
  }

  return { open, inquiry, lines, loading, error, creatingIndex, trackingIndex, show, close, load, createProduct, trackNonInventory }
}
