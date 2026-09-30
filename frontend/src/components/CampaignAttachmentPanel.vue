<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  file: { type: Object, default: null },
  message: { type: String, default: '' },
  description: { type: String, default: 'The image and message are queued together by ChatLens.' },
})
defineEmits(['remove', 'select'])

const previewUrl = ref('')
const characterCount = computed(() => [...props.message].length)
const characterLimit = computed(() => props.file ? 1024 : 10000)
const isOverLimit = computed(() => characterCount.value > characterLimit.value)
const isNearLimit = computed(() => characterCount.value >= characterLimit.value * 0.9)
const fileSize = computed(() => {
  if (!props.file?.size) return ''
  return props.file.size >= 1024 * 1024
    ? `${(props.file.size / 1024 / 1024).toFixed(1)} MB`
    : `${Math.ceil(props.file.size / 1024)} KB`
})

function releasePreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}

watch(() => props.file, file => {
  releasePreview()
  if (file) previewUrl.value = URL.createObjectURL(file)
}, { immediate: true })
onBeforeUnmount(releasePreview)
</script>

<template>
  <section class="attachment-panel">
    <div class="attachment-copy">
      <h3>Optional image</h3>
      <p>{{ description }}</p>
      <div class="character-row" :class="{ warning: isNearLimit, invalid: isOverLimit }">
        <strong>{{ characterCount.toLocaleString() }} / {{ characterLimit.toLocaleString() }}</strong>
        <span>{{ file ? 'image caption characters' : 'text message characters' }}</span>
      </div>
      <p v-if="isOverLimit" class="limit-error">
        Reduce the message by {{ (characterCount - characterLimit).toLocaleString() }} characters before sending.
      </p>
    </div>

    <div v-if="file" class="image-card">
      <img :src="previewUrl" :alt="file.name" />
      <div><strong>{{ file.name }}</strong><span>{{ fileSize }} · {{ file.type }}</span></div>
    </div>

    <div class="attachment-actions">
      <label class="image-picker">
        {{ file ? 'Replace image' : 'Choose image' }}
        <input type="file" accept="image/jpeg,image/png,image/webp" @change="$emit('select', $event)" />
      </label>
      <button v-if="file" type="button" class="remove" @click="$emit('remove')">Remove image</button>
    </div>
  </section>
</template>

<style scoped>
.attachment-panel{display:grid;grid-template-columns:minmax(240px,1fr) minmax(220px,340px) auto;align-items:center;gap:18px;border:1px solid #dbe4ee;border-radius:14px;padding:14px;background:#fff}.attachment-copy h3,.attachment-copy p{margin:0}.attachment-copy p{margin-top:5px;color:#64748b;font-size:.82rem}.character-row{display:flex;align-items:baseline;gap:8px;margin-top:12px;color:#166534}.character-row strong{font-size:1rem}.character-row span{color:#64748b;font-size:.76rem}.character-row.warning{color:#a16207}.character-row.invalid{color:#b91c1c}.attachment-copy .limit-error{color:#b91c1c;font-weight:700}.image-card{display:grid;grid-template-columns:92px minmax(0,1fr);align-items:center;gap:10px;padding:8px;border:1px solid #dbe4ee;border-radius:11px;background:#f8fafc}.image-card img{width:92px;height:70px;object-fit:cover;border-radius:8px;background:#e2e8f0}.image-card strong,.image-card span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.image-card strong{font-size:.82rem}.image-card span{margin-top:4px;color:#64748b;font-size:.72rem}.attachment-actions{display:flex;gap:8px;flex-wrap:wrap}.image-picker,.remove{border:1px solid #cbd5e1;border-radius:9px;padding:8px 12px;background:#fff;font:inherit;font-size:.78rem;font-weight:800;cursor:pointer}.image-picker input{display:none}.remove{color:#b42318;border-color:#f3c7c3}@media(max-width:900px){.attachment-panel{grid-template-columns:1fr}.attachment-actions{justify-content:flex-start}}
</style>
