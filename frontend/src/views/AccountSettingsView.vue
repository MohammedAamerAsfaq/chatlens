<script setup>
import { reactive, ref } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const emailForm = reactive({ email: auth.user?.email || '', current_password: '' })
const passwordForm = reactive({ current_password: '', new_password: '', confirm_password: '' })
const emailBusy = ref(false)
const emailError = ref('')
const emailSuccess = ref('')
const passwordBusy = ref(false)
const passwordError = ref('')
const passwordSuccess = ref('')

function message(exc, fallback) {
  return exc.response?.data?.detail || fallback
}

async function saveEmail() {
  emailBusy.value = true
  emailError.value = ''; emailSuccess.value = ''
  try {
    await auth.updateAccount({ email: emailForm.email, current_password: emailForm.current_password })
    emailForm.current_password = ''
    emailSuccess.value = 'Email address updated.'
  } catch (exc) {
    emailError.value = message(exc, 'Unable to update email address.')
  } finally {
    emailBusy.value = false
  }
}

async function savePassword() {
  passwordError.value = ''; passwordSuccess.value = ''
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    passwordError.value = 'New password and confirmation do not match.'
    return
  }
  passwordBusy.value = true
  try {
    await auth.updateAccount({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    Object.assign(passwordForm, { current_password: '', new_password: '', confirm_password: '' })
    passwordSuccess.value = 'Password updated.'
  } catch (exc) {
    passwordError.value = message(exc, 'Unable to update password.')
  } finally {
    passwordBusy.value = false
  }
}
</script>

<template>
  <UiPage class="account-settings-page">
    <UiPageHeader eyebrow="Account" title="My Account" description="Manage the email address and password for your own account." />

    <UiCard title="Email address">
      <form class="account-form" @submit.prevent="saveEmail">
        <UiNotice v-if="emailError" tone="danger">{{ emailError }}</UiNotice>
        <UiNotice v-if="emailSuccess" tone="success">{{ emailSuccess }}</UiNotice>
        <UiFormField label="Email"><input v-model.trim="emailForm.email" type="email" required /></UiFormField>
        <UiFormField label="Current password"><input v-model="emailForm.current_password" type="password" required /></UiFormField>
        <UiButton variant="primary" type="submit" :disabled="emailBusy">{{ emailBusy ? 'Saving...' : 'Save email' }}</UiButton>
      </form>
    </UiCard>

    <UiCard title="Password">
      <form class="account-form" @submit.prevent="savePassword">
        <UiNotice v-if="passwordError" tone="danger">{{ passwordError }}</UiNotice>
        <UiNotice v-if="passwordSuccess" tone="success">{{ passwordSuccess }}</UiNotice>
        <UiFormField label="Current password"><input v-model="passwordForm.current_password" type="password" required /></UiFormField>
        <UiFormField label="New password"><input v-model="passwordForm.new_password" type="password" required /></UiFormField>
        <UiFormField label="Confirm new password"><input v-model="passwordForm.confirm_password" type="password" required /></UiFormField>
        <UiButton variant="primary" type="submit" :disabled="passwordBusy">{{ passwordBusy ? 'Saving...' : 'Save password' }}</UiButton>
      </form>
    </UiCard>
  </UiPage>
</template>

<style scoped>
.account-settings-page{display:grid;gap:16px}
.account-form{display:grid;gap:12px;max-width:380px}
</style>
