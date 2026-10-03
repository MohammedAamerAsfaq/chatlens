<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { campaignCharacterCount, campaignMessageLimit } from '../constants'

const props = defineProps({
  file: { type: Object, default: null },
  asset: { type: Object, default: null },
  message: { type: String, default: '' },
  description: { type: String, default: 'The image and message are queued together by ChatLens.' },
})
defineEmits(['remove', 'select'])

const previewUrl = ref('')
const hasImage = computed(() => Boolean(props.file || props.asset?.image_asset))
const characterCount = computed(() => campaignCharacterCount(props.message))
const characterLimit = computed(() => campaignMessageLimit(hasImage.value))
const isOverLimit = computed(() => characterCount.value > characterLimit.value)
const isNearLimit = computed(() => characterCount.value >= characterLimit.value * 0.9)
const fileName = computed(() => props.file?.name || props.asset?.image_filename || 'Campaign image')
const mimeType = computed(() => props.file?.type || props.asset?.image_mime_type || '')
const fileSize = computed(() => {
  const size = props.file?.size || props.asset?.image_size_bytes
  if (!size) return ''
  return size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(size / 1024)} KB`
})

function releasePreview() {
  if (previewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}

watch(() => props.file, file => {
  releasePreview()
  previewUrl.value = file ? URL.createObjectURL(file) : (props.asset?.image_url || '')
}, { immediate: true })
watch(() => props.asset?.image_url, url => {
  if (!props.file) previewUrl.value = url || ''
})
onBeforeUnmount(releasePreview)
</script>

<template>
  <section class="campaign-attachment-panel">
    <div class="attachment-copy">
      <h3>Optional image</h3>
      <p>{{ description }}</p>
      <div class="character-row" :class="{ warning: isNearLimit, invalid: isOverLimit }">
        <strong>{{ characterCount.toLocaleString() }} / {{ characterLimit.toLocaleString() }}</strong>
        <span>{{ hasImage ? 'image caption characters' : 'text message characters' }}</span>
      </div>
      <p class="limit-note">{{ hasImage ? 'Image caption limit: 1,024 characters.' : 'Text message limit: 10,000 characters.' }}</p>
      <p v-if="hasImage" class="saved-note">Saved with this campaign and retained after refresh.</p>
      <p v-if="isOverLimit" class="limit-error">Reduce the message by {{ (characterCount - characterLimit).toLocaleString() }} characters before sending.</p>
    </div>
    <div v-if="hasImage" class="image-card">
      <img :src="previewUrl" :alt="fileName" />
      <div><strong>{{ fileName }}</strong><span>{{ fileSize }}<template v-if="fileSize && mimeType"> &middot; </template>{{ mimeType }}</span></div>
    </div>
    <div class="attachment-actions">
      <label class="image-picker">{{ hasImage ? 'Replace image' : 'Choose image' }}<input type="file" accept="image/jpeg,image/png,image/webp" @change="$emit('select', $event)" /></label>
      <button v-if="hasImage" type="button" class="remove" @click="$emit('remove')">Remove image</button>
    </div>
  </section>
</template>

<style scoped>
.campaign-attachment-panel{display:grid;grid-template-columns:minmax(240px,1fr) minmax(220px,340px) auto;align-items:center;gap:18px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);padding:14px;background:var(--ui-surface-raised)}.attachment-copy h3,.attachment-copy p{margin:0}.attachment-copy p{margin-top:5px;color:var(--ui-text-muted);font-size:.82rem}.attachment-copy .limit-note{color:var(--ui-text);font-weight:700}.attachment-copy .saved-note{color:var(--ui-success)}.character-row{display:flex;align-items:baseline;gap:8px;margin-top:12px;color:var(--ui-success)}.character-row strong{font-size:1rem}.character-row span{color:var(--ui-text-muted);font-size:.76rem}.character-row.warning{color:var(--ui-warning)}.character-row.invalid,.attachment-copy .limit-error{color:var(--ui-danger)}.attachment-copy .limit-error{font-weight:700}.image-card{display:grid;grid-template-columns:92px minmax(0,1fr);align-items:center;gap:10px;padding:8px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-muted)}.image-card img{width:92px;height:70px;object-fit:cover;border-radius:var(--ui-radius-xs);background:var(--ui-surface-muted)}.image-card strong,.image-card span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.image-card strong{font-size:.82rem}.image-card span{margin-top:4px;color:var(--ui-text-muted);font-size:.72rem}.attachment-actions{display:flex;gap:8px;flex-wrap:wrap}.image-picker,.remove{border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);padding:8px 12px;background:var(--ui-surface-raised);color:var(--ui-text);font:inherit;font-size:.78rem;font-weight:800;cursor:pointer}.image-picker input{display:none}.remove{color:var(--ui-danger);border-color:color-mix(in srgb,var(--ui-danger) 30%,white)}@media(max-width:900px){.campaign-attachment-panel{grid-template-columns:1fr}}
</style>
