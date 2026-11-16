<script setup>
import { computed, ref } from 'vue'

// A password input that advises a strong password as you type and can generate one.
// The server's own rules (Django password validators) are the authority and are
// listed below the checklist; this only helps people pick something that will pass.
const props = defineProps({
  modelValue: { type: String, default: '' },
  username: { type: String, default: '' },
  email: { type: String, default: '' },
  rules: { type: Array, default: () => [] },
  required: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const RECOMMENDED_LENGTH = 12
const visible = ref(false)

const value = computed({
  get: () => props.modelValue,
  set: (next) => emit('update:modelValue', next),
})

const checks = computed(() => {
  const pw = value.value
  const lower = pw.toLowerCase()
  const names = [props.username, props.email.split('@')[0]]
    .map(name => (name || '').trim().toLowerCase())
    .filter(name => name.length >= 3)
  return [
    { label: `At least ${RECOMMENDED_LENGTH} characters`, ok: pw.length >= RECOMMENDED_LENGTH },
    { label: 'Upper and lower case letters', ok: /[a-z]/.test(pw) && /[A-Z]/.test(pw) },
    { label: 'At least one number', ok: /\d/.test(pw) },
    { label: 'At least one symbol', ok: /[^A-Za-z0-9]/.test(pw) },
    { label: 'Does not contain the username or email', ok: pw.length > 0 && !names.some(name => lower.includes(name)) },
  ]
})

function passwordStrength(checksList) {
  const passed = checksList.filter(check => check.ok).length
  if (passed === checksList.length) return 'strong'
  if (passed >= 3) return 'fair'
  return 'weak'
}

const strength = computed(() => (value.value ? passwordStrength(checks.value) : ''))
const strengthLabel = computed(() => ({ strong: 'Strong', fair: 'Fair', weak: 'Weak' }[strength.value] || ''))

function generate() {
  const groups = ['ABCDEFGHJKLMNPQRSTUVWXYZ', 'abcdefghijkmnopqrstuvwxyz', '23456789', '!@#$%^&*-_=+?']
  const all = groups.join('')
  const random = (n) => crypto.getRandomValues(new Uint32Array(1))[0] % n
  const chars = groups.map(group => group[random(group.length)])
  while (chars.length < 16) chars.push(all[random(all.length)])
  for (let i = chars.length - 1; i > 0; i -= 1) {
    const j = random(i + 1)
    ;[chars[i], chars[j]] = [chars[j], chars[i]]
  }
  value.value = chars.join('')
  visible.value = true
}
</script>

<template>
  <div class="password-field">
    <div class="password-input">
      <input v-model="value" :type="visible ? 'text' : 'password'" :required="required" autocomplete="new-password" />
      <button type="button" class="link" @click="visible = !visible">{{ visible ? 'Hide' : 'Show' }}</button>
      <button type="button" class="link" @click="generate">Generate</button>
    </div>
    <div v-if="strength" :class="['strength', strength]">
      <span class="bar"><span /></span>{{ strengthLabel }}
    </div>
    <ul class="checks">
      <li v-for="check in checks" :key="check.label" :class="{ ok: check.ok }">{{ check.ok ? '✓' : '•' }} {{ check.label }}</li>
    </ul>
    <p v-if="visible && value" class="copy-note">Copy this password now and give it to the user privately; it is not shown again.</p>
    <details v-if="rules.length" class="rules">
      <summary>Rules the server enforces</summary>
      <ul><li v-for="rule in rules" :key="rule">{{ rule }}</li></ul>
    </details>
  </div>
</template>

<style scoped>
.password-field{display:grid;gap:6px}.password-input{display:flex;align-items:center;gap:6px}.password-input input{flex:1;min-width:0}.link{padding:2px 4px;border:0;background:none;color:var(--ui-primary,#126c3e);font-size:.74rem;font-weight:700;cursor:pointer}.strength{display:flex;align-items:center;gap:8px;font-size:.74rem;font-weight:700}.bar{position:relative;width:90px;height:5px;border-radius:3px;background:#e5e7eb;overflow:hidden}.bar span{position:absolute;inset:0 auto 0 0}.weak{color:#b42318}.weak .bar span{width:33%;background:#b42318}.fair{color:#b54708}.fair .bar span{width:66%;background:#f79009}.strong{color:#126c3e}.strong .bar span{width:100%;background:#12b76a}.checks{display:grid;gap:2px;margin:0;padding:0;list-style:none;color:#667085;font-size:.72rem}.checks li.ok{color:#126c3e}.copy-note{margin:0;color:#b54708;font-size:.72rem}.rules{color:#667085;font-size:.72rem}.rules summary{cursor:pointer}.rules ul{margin:4px 0 0;padding-left:16px}
</style>
