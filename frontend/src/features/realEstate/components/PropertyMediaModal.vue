<script setup>
import { computed, reactive, ref, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiFileUpload from '@/components/ui/UiFileUpload.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { mediaTypes } from '../options'

const props = defineProps({ open: Boolean, property: { type: Object, default: null }, busy: Boolean })
const emit = defineEmits(['close', 'upload', 'remove'])
const file = ref(null)
const form = reactive({ media_type: 'image', external_url: '', caption: '', is_primary: false })
const media = computed(() => props.property?.media || [])

watch(() => props.open, open => {
  if (!open) return
  file.value = null
  Object.assign(form, { media_type: 'image', external_url: '', caption: '', is_primary: false })
})

function submit() {
  emit('upload', { ...form, file: file.value })
}
</script>

<template>
  <UiModal :open="open" :title="`Media - ${property?.title || 'Property'}`" subtitle="Upload images and documents or link externally hosted media." size="large" tall @close="emit('close')">
    <div class="media-list">
      <article v-for="item in media" :key="item.id">
        <img v-if="item.media_type === 'image' && (item.file || item.external_url)" :src="item.file || item.external_url" :alt="item.caption || item.file_name">
        <div v-else class="media-placeholder">{{ item.media_type.replaceAll('_', ' ') }}</div>
        <div><strong>{{ item.caption || item.file_name || 'Untitled media' }}</strong><small>{{ item.is_primary ? 'Primary' : item.media_type }}</small></div>
        <UiButton variant="danger" size="small" :disabled="busy" @click="emit('remove', item)">Remove</UiButton>
      </article>
      <p v-if="!media.length" class="empty">No media has been added.</p>
    </div>
    <form id="media-form" class="media-form" @submit.prevent="submit">
      <UiFormField label="Media type"><UiSelect v-model="form.media_type" :options="mediaTypes" /></UiFormField>
      <UiFormField label="Caption"><UiInput v-model="form.caption" /></UiFormField>
      <UiFormField label="Upload file" class="wide"><UiFileUpload accept="image/jpeg,image/png,image/webp,application/pdf,video/mp4" :file-name="file?.name || ''" @select="file = $event" @clear="file = null" /></UiFormField>
      <UiFormField label="Or external URL" class="wide"><UiInput v-model="form.external_url" type="url" placeholder="https://..." :disabled="Boolean(file)" /></UiFormField>
      <UiCheckbox v-model="form.is_primary" label="Primary media" class="wide" />
    </form>
    <template #footer><UiButton @click="emit('close')">Close</UiButton><UiButton variant="primary" type="submit" form="media-form" :disabled="busy || (!file && !form.external_url)">{{ busy ? 'Uploading...' : 'Add media' }}</UiButton></template>
  </UiModal>
</template>

<style scoped>
.media-list{display:grid;gap:10px;margin-bottom:22px}.media-list article{display:grid;grid-template-columns:76px 1fr auto;gap:14px;align-items:center;padding:10px;border:1px solid var(--ui-border);border-radius:10px}.media-list img,.media-placeholder{width:76px;height:58px;object-fit:cover;border-radius:7px;background:var(--ui-bg);display:grid;place-items:center;text-transform:capitalize}.media-list article>div{display:grid}.media-list small,.empty{color:var(--ui-text-subtle)}.media-form{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding-top:18px;border-top:1px solid var(--ui-border)}.wide{grid-column:1/-1}@media(max-width:650px){.media-form{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
