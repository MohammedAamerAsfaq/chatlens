<script setup>
import { onMounted, reactive, ref } from 'vue'
import { companyAccessApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'

const users = ref([])
const roles = ref([])
const roleDrafts = reactive({})
const loading = ref(true)
const busy = ref('')
const error = ref('')
const success = ref('')
const form = reactive({ username: '', email: '', password: '', role_ids: [] })

function message(exc, fallback) {
  return exc.response?.data?.detail || fallback
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [usersResponse, rolesResponse] = await Promise.all([
      companyAccessApi.users(), companyAccessApi.roles(),
    ])
    users.value = usersResponse.data
    roles.value = rolesResponse.data.filter(role => role.is_active)
    users.value.forEach(user => { roleDrafts[user.id] = user.roles.map(role => role.id) })
  } catch (exc) {
    error.value = message(exc, 'Unable to load company users.')
  } finally {
    loading.value = false
  }
}

function toggleRole(membershipId, roleId) {
  const selected = new Set(roleDrafts[membershipId] || [])
  selected.has(roleId) ? selected.delete(roleId) : selected.add(roleId)
  roleDrafts[membershipId] = [...selected]
}

async function createUser() {
  busy.value = 'create'
  error.value = ''; success.value = ''
  try {
    await companyAccessApi.createUser({ ...form })
    Object.assign(form, { username: '', email: '', password: '', role_ids: [] })
    success.value = 'Company user created.'
    await load()
  } catch (exc) {
    error.value = message(exc, 'Unable to create company user.')
  } finally { busy.value = '' }
}

async function saveUser(user) {
  busy.value = `save-${user.id}`
  error.value = ''; success.value = ''
  try {
    const { data } = await companyAccessApi.updateUser(user.id, { role_ids: roleDrafts[user.id] })
    const index = users.value.findIndex(item => item.id === user.id)
    users.value[index] = data
    roleDrafts[user.id] = data.roles.map(role => role.id)
    success.value = `Access updated for ${user.user.username}.`
  } catch (exc) {
    error.value = message(exc, 'Unable to update user access.')
  } finally { busy.value = '' }
}

async function setActive(user, active) {
  busy.value = `active-${user.id}`
  error.value = ''; success.value = ''
  try {
    const { data } = await companyAccessApi.updateUser(user.id, { is_active: active })
    const index = users.value.findIndex(item => item.id === user.id)
    users.value[index] = data
    success.value = `${user.user.username} ${active ? 'reactivated' : 'suspended'}.`
  } catch (exc) {
    error.value = message(exc, 'Unable to change membership status.')
  } finally { busy.value = '' }
}

onMounted(load)
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="Company access" title="Users" description="Create company users, assign multiple roles, and suspend access without deleting business records." />
    <UiNotice tone="warning">RBAC is active for user and role administration. Existing application areas will move from legacy role checks to permission codes route by route.</UiNotice>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-if="success" tone="success">{{ success }}</UiNotice>

    <UiCard title="Add user" subtitle="A temporary password is required in this implementation phase." class="create-card">
      <form class="create-form" @submit.prevent="createUser">
        <UiFormField label="Username"><input v-model.trim="form.username" required /></UiFormField>
        <UiFormField label="Email"><input v-model.trim="form.email" type="email" required /></UiFormField>
        <UiFormField label="Temporary password"><input v-model="form.password" type="password" required /></UiFormField>
        <UiFormField label="Initial role"><select v-model="form.role_ids" multiple required><option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option></select></UiFormField>
        <UiButton variant="primary" type="submit" :disabled="busy === 'create'">{{ busy === 'create' ? 'Creating...' : 'Create user' }}</UiButton>
      </form>
    </UiCard>

    <UiCard title="Company users" :subtitle="`${users.length} memberships in this company`" class="users-card">
      <template #actions><UiButton size="small" @click="load">Refresh</UiButton></template>
      <UiEmptyState v-if="loading" title="Loading users..." busy />
      <UiEmptyState v-else-if="users.length === 0" title="No company users" description="Create the first company user above." />
      <div v-else class="user-grid">
        <article v-for="user in users" :key="user.id" :class="['user-card', { inactive: !user.is_active }]">
          <div class="identity"><div class="avatar">{{ user.user.username.slice(0, 1).toUpperCase() }}</div><div><h3>{{ user.user.username }}</h3><p>{{ user.user.email }}</p></div><UiBadge :tone="user.is_active ? 'success' : 'neutral'">{{ user.is_active ? 'Active' : 'Suspended' }}</UiBadge></div>
          <div class="roles"><strong>Roles</strong><label v-for="role in roles" :key="role.id"><input type="checkbox" :checked="(roleDrafts[user.id] || []).includes(role.id)" @change="toggleRole(user.id, role.id)" />{{ role.name }}</label></div>
          <div class="actions"><UiButton variant="primary" size="small" :disabled="busy === `save-${user.id}` || !(roleDrafts[user.id] || []).length" @click="saveUser(user)">Save roles</UiButton><UiButton v-if="user.is_active" variant="danger" size="small" :disabled="busy === `active-${user.id}`" @click="setActive(user, false)">Suspend</UiButton><UiButton v-else size="small" :disabled="busy === `active-${user.id}`" @click="setActive(user, true)">Reactivate</UiButton></div>
        </article>
      </div>
    </UiCard>
  </UiPage>
</template>

<style scoped src="@/assets/company-users-view.css"></style>
