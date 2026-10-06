<script setup>
import { reactive, ref } from 'vue'
import { clientPulseApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const props = defineProps({
  tags: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'tags-changed'])
const createForm = reactive({ name: '', color: '#23865b' })
const editForm = reactive({ name: '', color: '#23865b' })
const editingId = ref(null)
const busy = ref('')
const error = ref('')
const success = ref('')

function message(exc, fallback) {
  const data = exc.response?.data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
function toggle(tagId, selected) {
  const ids = selected
    ? [...new Set([...props.modelValue, tagId])]
    : props.modelValue.filter(id => id !== tagId)
  emit('update:modelValue', ids)
}
async function createTag() {
  if (!createForm.name.trim()) return
  busy.value = 'create'; error.value = ''; success.value = ''
  try {
    const { data } = await clientPulseApi.createTag({ ...createForm })
    toggle(data.id, true)
    Object.assign(createForm, { name: '', color: '#23865b' })
    success.value = 'Tag created and selected. Save the profile to apply it.'
    emit('tags-changed')
  } catch (exc) { error.value = message(exc, 'Unable to create tag.') }
  finally { busy.value = '' }
}
function beginEdit(tag) {
  editingId.value = tag.id
  Object.assign(editForm, { name: tag.name, color: tag.color })
  error.value = ''; success.value = ''
}
async function updateTag(tag) {
  busy.value = `edit-${tag.id}`; error.value = ''; success.value = ''
  try {
    await clientPulseApi.updateTag(tag.id, { ...editForm })
    editingId.value = null
    success.value = 'Tag updated.'
    emit('tags-changed')
  } catch (exc) { error.value = message(exc, 'Unable to update tag.') }
  finally { busy.value = '' }
}
async function deleteTag(tag) {
  const impact = tag.usage_count
    ? ` It will be removed from ${tag.usage_count} customer profile(s).`
    : ''
  if (!confirm(`Delete the “${tag.name}” tag?${impact}`)) return
  busy.value = `delete-${tag.id}`; error.value = ''; success.value = ''
  try {
    await clientPulseApi.deleteTag(tag.id)
    toggle(tag.id, false)
    if (editingId.value === tag.id) editingId.value = null
    success.value = 'Tag deleted.'
    emit('tags-changed')
  } catch (exc) { error.value = message(exc, 'Unable to delete tag.') }
  finally { busy.value = '' }
}
</script>

<template>
  <UiCard title="Profile tags" subtitle="Create reusable labels, assign them here, and manage their definitions.">
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-if="success" tone="success">{{ success }}</UiNotice>
    <form v-if="canEdit" class="tag-manager__create" @submit.prevent="createTag">
      <UiInput v-model="createForm.name" placeholder="New tag name" maxlength="100" />
      <UiInput v-model="createForm.color" type="color" aria-label="New tag color" />
      <UiButton type="submit" variant="primary" :disabled="busy === 'create'">
        {{ busy === 'create' ? 'Adding...' : 'Add tag' }}
      </UiButton>
    </form>
    <div v-if="tags.length" class="tag-manager__list">
      <article v-for="tag in tags" :key="tag.id" class="tag-manager__row">
        <template v-if="editingId === tag.id">
          <UiInput v-model="editForm.name" maxlength="100" @keyup.enter="updateTag(tag)" />
          <UiInput v-model="editForm.color" type="color" :aria-label="`${tag.name} color`" />
          <div class="tag-manager__actions">
            <UiButton size="small" variant="primary" :disabled="busy === `edit-${tag.id}`" @click="updateTag(tag)">Save</UiButton>
            <UiButton size="small" variant="outline" @click="editingId = null">Cancel</UiButton>
          </div>
        </template>
        <template v-else>
          <UiCheckbox :model-value="modelValue.includes(tag.id)" :disabled="!canEdit" @update:model-value="toggle(tag.id, $event)" />
          <span class="tag-manager__swatch" :style="{ backgroundColor: tag.color }" />
          <div class="tag-manager__copy"><strong>{{ tag.name }}</strong><small>{{ tag.usage_count }} customer{{ tag.usage_count === 1 ? '' : 's' }}</small></div>
          <div v-if="canEdit" class="tag-manager__actions">
            <UiButton size="small" variant="outline" @click="beginEdit(tag)">Edit</UiButton>
            <UiButton size="small" variant="danger" :disabled="busy === `delete-${tag.id}`" @click="deleteTag(tag)">Delete</UiButton>
          </div>
        </template>
      </article>
    </div>
    <UiEmptyState v-else title="No tags configured" description="Create the first reusable customer tag above." />
    <p v-if="canEdit && tags.length" class="tag-manager__hint">Selection changes are applied when you save the relationship profile.</p>
  </UiCard>
</template>

<style scoped>
.tag-manager__create { display: grid; grid-template-columns: minmax(180px, 1fr) 54px auto; gap: 10px; margin-bottom: 14px; }
.tag-manager__list { display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 10px; }
.tag-manager__row { display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto; align-items: center; gap: 9px; min-height: 54px; padding: 9px 10px; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-sm); background: var(--ui-surface-muted); }
.tag-manager__row:has(.ui-input-wrap) { grid-template-columns: minmax(140px, 1fr) 54px auto; }
.tag-manager__swatch { width: 14px; height: 14px; border-radius: 50%; box-shadow: 0 0 0 2px var(--ui-surface), 0 0 0 3px var(--ui-border); }
.tag-manager__copy { min-width: 0; }
.tag-manager__copy strong,.tag-manager__copy small { display: block; }
.tag-manager__copy strong { overflow: hidden; color: var(--ui-text-strong); font-size: .8rem; text-overflow: ellipsis; white-space: nowrap; }
.tag-manager__copy small,.tag-manager__hint { color: var(--ui-text-subtle); font-size: .68rem; }
.tag-manager__actions { display: flex; gap: 6px; justify-content: flex-end; }
.tag-manager__hint { margin: 12px 0 0; }
@media (max-width: 620px) { .tag-manager__create { grid-template-columns: 1fr 54px; } .tag-manager__create .ui-button { grid-column: 1 / -1; } .tag-manager__list { grid-template-columns: 1fr; } }
</style>
