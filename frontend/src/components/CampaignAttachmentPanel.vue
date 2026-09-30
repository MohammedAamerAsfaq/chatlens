<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  file: { type: Object, default: null },
  asset: { type: Object, default: null },
  message: { type: String, default: '' },
  description: { type: String, default: 'The image and message are queued together by ChatLens.' },
})
defineEmits(['remove', 'select'])

const previewUrl = ref('')
const hasImage = computed(() => Boolean(props.file || props.asset?.image_asset))
const characterCount = computed(() => [...props.message].length)
const characterLimit = computed(() => hasImage.value ? 1024 : 10000)
const isOverLimit = computed(() => characterCount.value > characterLimit.value)
const isNearLimit = computed(() => characterCount.value >= characterLimit.value * 0.9)
const fileName = computed(() => props.file?.name || props.asset?.image_filename || 'Campaign image')
const mimeType = computed(() => props.file?.type || props.asset?.image_mime_type || '')
const fileSize = computed(() => {
  const size = props.file?.size || props.asset?.image_size_bytes
  if (!size) return ''
  return size >= 1024 * 1024
    ? `${(size / 1024 / 1024).toFixed(1)} MB`
    : `${Math.ceil(size / 1024)} KB`
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
  <section class="attachment-panel">
    <div class="attachment-copy">
      <h3>Optional image</h3>
      <p>{{ description }}</p>
      <div class="character-row" :class="{ warning: isNearLimit, invalid: isOverLimit }">
        <strong>{{ characterCount.toLocaleString() }} / {{ characterLimit.toLocaleString() }}</strong>
        <span>{{ hasImage ? 'image caption characters' : 'text message characters' }}</span>
      </div>
      <p class="limit-note">
        {{ hasImage ? 'Image caption limit: 1,024 characters.' : 'Text message limit: 10,000 characters.' }}
      </p>
      <p v-if="hasImage" class="saved-note">Saved with this campaign and retained after refresh.</p>
      <p v-if="isOverLimit" class="limit-error">
        Reduce the message by {{ (characterCount - characterLimit).toLocaleString() }} characters before sending.
      </p>
    </div>

    <div v-if="hasImage" class="image-card">
      <img :src="previewUrl" :alt="fileName" />
      <div>
        <strong>{{ fileName }}</strong>
        <span>{{ fileSize }}<template v-if="fileSize && mimeType"> &middot; </template>{{ mimeType }}</span>
      </div>
    </div>

    <div class="attachment-actions">
      <label class="image-picker">
        {{ hasImage ? 'Replace image' : 'Choose image' }}
        <input type="file" accept="image/jpeg,image/png,image/webp" @change="$emit('select', $event)" />
      </label>
      <button v-if="hasImage" type="button" class="remove" @click="$emit('remove')">Remove image</button>
    </div>
  </section>
</template>

<style scoped>
.attachment-panel{display:grid;grid-template-columns:minmax(240px,1fr) minmax(220px,340px) auto;align-items:center;gap:18px;border:1px solid #dbe4ee;border-radius:14px;padding:14px;background:#fff}.attachment-copy h3,.attachment-copy p{margin:0}.attachment-copy p{margin-top:5px;color:#64748b;font-size:.82rem}.attachment-copy .limit-note{color:#334155;font-weight:700}.attachment-copy .saved-note{color:#15803d}.character-row{display:flex;align-items:baseline;gap:8px;margin-top:12px;color:#166534}.character-row strong{font-size:1rem}.character-row span{color:#64748b;font-size:.76rem}.character-row.warning{color:#a16207}.character-row.invalid{color:#b91c1c}.attachment-copy .limit-error{color:#b91c1c;font-weight:700}.image-card{display:grid;grid-template-columns:92px minmax(0,1fr);align-items:center;gap:10px;padding:8px;border:1px solid #dbe4ee;border-radius:11px;background:#f8fafc}.image-card img{width:92px;height:70px;object-fit:cover;border-radius:8px;background:#e2e8f0}.image-card strong,.image-card span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.image-card strong{font-size:.82rem}.image-card span{margin-top:4px;color:#64748b;font-size:.72rem}.attachment-actions{display:flex;gap:8px;flex-wrap:wrap}.image-picker,.remove{border:1px solid #cbd5e1;border-radius:9px;padding:8px 12px;background:#fff;font:inherit;font-size:.78rem;font-weight:800;cursor:pointer}.image-picker input{display:none}.remove{color:#b42318;border-color:#f3c7c3}@media(max-width:900px){.attachment-panel{grid-template-columns:1fr}.attachment-actions{justify-content:flex-start}}
</style>
