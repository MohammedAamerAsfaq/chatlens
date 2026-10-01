<script setup>
import { onMounted, reactive, ref } from 'vue'
import { clientPulseApi } from '@/api'
import '@/assets/clientpulse.css'

const form=reactive({consent_mode:'observational',reminders_enabled:true,default_timezone:'Asia/Dubai',default_language:'',automated_follow_up_enabled:false})
const loading=ref(true),busy=ref(false),error=ref(''),success=ref('')
async function load(){try{Object.assign(form,(await clientPulseApi.settings()).data)}catch(exc){error.value=exc.response?.data?.detail||'Unable to load settings.'}finally{loading.value=false}}
async function save(){busy.value=true;error.value='';success.value='';try{Object.assign(form,(await clientPulseApi.updateSettings(form)).data);success.value='ClientPulse settings updated.'}catch(exc){error.value=exc.response?.data?.detail||'Unable to save settings.'}finally{busy.value=false}}
onMounted(load)
</script>
<template><main class="cp-page"><div class="cp-shell"><p class="cp-eyebrow">Company settings</p><h1 class="cp-title">ClientPulse</h1><p class="cp-muted">Configure safe CRM defaults. Automated follow-up remains locked off until its implementation phase.</p><p v-if="error" class="cp-notice error">{{error}}</p><p v-if="success" class="cp-notice success">{{success}}</p><section class="cp-panel cp-card" style="margin-top:18px"><div v-if="loading" class="cp-empty">Loading settings...</div><form v-else class="cp-form-grid" @submit.prevent="save"><label>Consent policy<select v-model="form.consent_mode" class="cp-select"><option value="observational">Observational</option><option value="enforced">Enforced</option></select></label><label>Default timezone<input v-model="form.default_timezone" class="cp-input" required /></label><label>Default language<input v-model="form.default_language" class="cp-input" placeholder="e.g. en" /></label><label><span><input v-model="form.reminders_enabled" type="checkbox" /> Reminders enabled</span></label><label><span><input :checked="form.automated_follow_up_enabled" type="checkbox" disabled /> Automated follow-up (not available)</span></label><div class="cp-actions wide"><button class="cp-button cp-primary" :disabled="busy">{{busy?'Saving...':'Save settings'}}</button></div></form></section></div></main></template>
