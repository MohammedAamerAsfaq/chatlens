<template>
  <div class="products-view">
    <div class="view-header">
      <div class="header-left">
        <h2>Product Master</h2>
        <span class="count-badge">{{ products.length }} products</span>
      </div>
      <button class="btn-primary" @click="openCreate">+ Add Product</button>
    </div>

    <div class="toolbar">
      <input v-model="search" class="search-input" placeholder="Search products…" />
      <label class="toggle-label">
        <input type="checkbox" v-model="showInactive" /> Show inactive
      </label>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Brand</th>
            <th>Category</th>
            <th>Aliases</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filtered.length === 0">
            <td colspan="6" class="empty">No products found.</td>
          </tr>
          <tr v-for="p in filtered" :key="p.id" :class="{ inactive: !p.is_active }">
            <td class="col-name">{{ p.name }}</td>
            <td>{{ p.brand }}</td>
            <td>{{ p.category }}</td>
            <td class="col-aliases">
              <span v-for="a in p.aliases" :key="a" class="alias-chip">{{ a }}</span>
              <span v-if="!p.aliases.length" class="muted">—</span>
            </td>
            <td>
              <span :class="['status-dot', p.is_active ? 'active' : 'inactive']">
                {{ p.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="col-actions">
              <button class="btn-sm" @click="openEdit(p)">Edit</button>
              <button v-if="p.is_active" class="btn-sm danger" @click="deactivate(p)">
                Deactivate
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create / Edit modal -->
    <div v-if="modal.open" class="modal-backdrop" @click.self="closeModal">
      <div class="modal">
        <h3>{{ modal.id ? 'Edit Product' : 'Add Product' }}</h3>

        <div class="form-group">
          <label>Name *</label>
          <input v-model="modal.name" placeholder="iPhone 17 Pro Max" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Brand</label>
            <input v-model="modal.brand" placeholder="Apple" />
          </div>
          <div class="form-group">
            <label>Category</label>
            <input v-model="modal.category" placeholder="Smartphones" />
          </div>
        </div>
        <div class="form-group">
          <label>SKU</label>
          <input v-model="modal.sku" placeholder="optional" />
        </div>
        <div class="form-group">
          <label>Aliases <span class="hint">(comma-separated)</span></label>
          <textarea v-model="modal.aliasText" rows="3"
            placeholder="17PM, 17 Pro Max, 17 PRO MAX, Apple 17 PM" />
          <div class="alias-preview">
            <span v-for="a in previewAliases" :key="a" class="alias-chip">{{ a }}</span>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-ghost" @click="closeModal">Cancel</button>
          <button class="btn-primary" :disabled="saving || !modal.name.trim()" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { tradingApi } from '../api/index.js'

const products    = ref([])
const search      = ref('')
const showInactive = ref(false)
const saving      = ref(false)

const modal = ref({
  open: false, id: null,
  name: '', brand: '', category: '', sku: '', aliasText: '',
})

const previewAliases = computed(() =>
  modal.value.aliasText
    .split(',')
    .map(a => a.trim())
    .filter(Boolean)
)

const filtered = computed(() => {
  let list = products.value
  if (!showInactive.value) list = list.filter(p => p.is_active)
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    list = list.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.brand.toLowerCase().includes(q) ||
      p.aliases.some(a => a.toLowerCase().includes(q))
    )
  }
  return list
})

async function load() {
  const { data } = await tradingApi.listProducts({ active: 'all' })
  products.value = data
}

function openCreate() {
  modal.value = { open: true, id: null, name: '', brand: '', category: '', sku: '', aliasText: '' }
}

function openEdit(p) {
  modal.value = {
    open: true, id: p.id,
    name: p.name, brand: p.brand, category: p.category, sku: p.sku,
    aliasText: p.aliases.join(', '),
  }
}

function closeModal() {
  modal.value.open = false
}

async function save() {
  if (!modal.value.name.trim()) return
  saving.value = true
  try {
    const payload = {
      name:      modal.value.name.trim(),
      brand:     modal.value.brand.trim(),
      category:  modal.value.category.trim(),
      sku:       modal.value.sku.trim(),
      aliases:   previewAliases.value,
      is_active: true,
    }
    if (modal.value.id) {
      await tradingApi.updateProduct(modal.value.id, payload)
    } else {
      await tradingApi.createProduct(payload)
    }
    closeModal()
    await load()
  } finally {
    saving.value = false
  }
}

async function deactivate(p) {
  if (!confirm(`Deactivate "${p.name}"? It will no longer appear in AI classification.`)) return
  await tradingApi.updateProduct(p.id, { is_active: false })
  await load()
}

onMounted(load)
</script>

<style scoped>
.products-view { display: flex; flex-direction: column; height: 100%; padding: 20px; gap: 14px; }
.view-header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 1.2rem; }
.count-badge { background: #e5e7eb; border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.search-input { flex: 1; padding: 7px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; }
.toggle-label { font-size: 0.88rem; display: flex; gap: 6px; align-items: center; cursor: pointer; }
.table-wrap { flex: 1; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.data-table th { background: #f9fafb; padding: 10px 14px; text-align: left; font-size: 0.8rem; color: #6b7280; border-bottom: 1px solid #e5e7eb; }
.data-table td { padding: 10px 14px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tr.inactive { opacity: 0.5; }
.col-name { font-weight: 500; }
.col-aliases { display: flex; flex-wrap: wrap; gap: 4px; }
.alias-chip { background: #eff6ff; color: #1d4ed8; border-radius: 4px; padding: 1px 7px; font-size: 0.78rem; }
.col-actions { display: flex; gap: 6px; white-space: nowrap; }
.status-dot { font-size: 0.8rem; font-weight: 500; }
.status-dot.active { color: #16a34a; }
.status-dot.inactive { color: #9ca3af; }
.empty { text-align: center; color: #9ca3af; padding: 40px; }
.muted { color: #9ca3af; }
.btn-primary { padding: 7px 16px; background: #2563eb; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { padding: 7px 16px; background: transparent; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-sm { padding: 4px 10px; border: 1px solid #d1d5db; border-radius: 5px; background: #fff; cursor: pointer; font-size: 0.8rem; }
.btn-sm.danger { border-color: #fca5a5; color: #dc2626; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 10px; padding: 24px; width: 520px; max-width: 95vw; display: flex; flex-direction: column; gap: 14px; }
.modal h3 { margin: 0; font-size: 1.1rem; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group label { font-size: 0.83rem; color: #374151; font-weight: 500; }
.form-group input, .form-group textarea { padding: 7px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.hint { font-weight: 400; color: #6b7280; }
.alias-preview { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; min-height: 20px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
</style>
