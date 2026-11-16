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
import UiModal from '@/components/ui/UiModal.vue'
import PasswordField from '@/components/PasswordField.vue'
import { useAuthStore } from '@/stores/auth'

const users = ref([])
const roles = ref([])
const communicationAccounts = ref([])
const roleDrafts = reactive({})
const accountDrafts = reactive({})
const loading = ref(true)
const busy = ref('')
const error = ref('')
const success = ref('')
const form = reactive({ username: '', email: '', password: '', role_ids: [] })
const passwordRules = ref([])
const auth = useAuthStore()

// One dialog at a time: { kind: 'username' | 'password' | 'remove', user, value }
const dialog = ref(null)
const dialogError = ref('')

function message(exc, fallback) {
  return exc.response?.data?.detail || fallback
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [usersResponse, rolesResponse, accountsResponse] = await Promise.all([
      companyAccessApi.users(), companyAccessApi.roles(), companyAccessApi.communicationAccounts(),
    ])
    companyAccessApi.passwordRules()
      .then(({ data }) => { passwordRules.value = data.rules })
      .catch(exc => { error.value = message(exc, 'Unable to load the password rules.') })
    users.value = usersResponse.data
    roles.value = rolesResponse.data.filter(role => role.is_active)
    communicationAccounts.value = accountsResponse.data
    users.value.forEach(user => {
      roleDrafts[user.id] = user.roles.map(role => role.id)
      accountDrafts[user.id] = [...user.communication_account_ids]
    })
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

function toggleAccount(membershipId, accountId) {
  const selected = new Set(accountDrafts[membershipId] || [])
  selected.has(accountId) ? selected.delete(accountId) : selected.add(accountId)
  accountDrafts[membershipId] = [...selected]
}

function ownsAccount(user, account) {
  return account.owner_user_id === user.user.id
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
    await companyAccessApi.updateUser(user.id, { role_ids: roleDrafts[user.id] })
    const { data } = await companyAccessApi.updateUserCommunicationAccounts(user.id, {
      communication_account_ids: accountDrafts[user.id] || [],
    })
    const index = users.value.findIndex(item => item.id === user.id)
    users.value[index] = data
    roleDrafts[user.id] = data.roles.map(role => role.id)
    accountDrafts[user.id] = [...data.communication_account_ids]
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

function openDialog(kind, user) {
  dialogError.value = ''
  dialog.value = { kind, user, value: kind === 'username' ? user.user.username : '' }
}

function isSelf(user) {
  return user.user.id === auth.user?.id
}

function replaceUser(data) {
  const index = users.value.findIndex(item => item.id === data.id)
  if (index >= 0) users.value[index] = data
}

async function submitDialog() {
  const { kind, user, value } = dialog.value
  busy.value = `${kind}-${user.id}`
  dialogError.value = ''; error.value = ''; success.value = ''
  try {
    if (kind === 'username') {
      const { data } = await companyAccessApi.updateUser(user.id, { username: value.trim() })
      replaceUser(data)
      if (isSelf(user) && auth.user) auth.user.username = data.user.username
      success.value = `${user.user.username} is now ${data.user.username}.`
    } else if (kind === 'password') {
      await companyAccessApi.setUserPassword(user.id, value)
      success.value = isSelf(user)
        ? 'Your password was changed. Your other sessions are signed out.'
        : `Password changed for ${user.user.username}. They are signed out everywhere and must use the new password.`
    } else {
      await companyAccessApi.removeUser(user.id)
      users.value = users.value.filter(item => item.id !== user.id)
      success.value = `${user.user.username} was removed. Their records are kept and the username is free to reuse.`
    }
    dialog.value = null
  } catch (exc) {
    dialogError.value = message(exc, 'The change was not saved.')
  } finally { busy.value = '' }
}

const DIALOG_TITLES = { username: 'Change username', password: 'Set a new password', remove: 'Remove user' }

onMounted(load)
</script>

<template>
  <UiPage width="wide" class="company-users-page">
    <UiPageHeader eyebrow="Company access" title="Users" description="Create company users, assign multiple roles, and suspend access without deleting business records." />
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-if="success" tone="success">{{ success }}</UiNotice>

    <UiCard title="Add user" subtitle="Give them a strong temporary password and share it privately." class="create-card">
      <form class="create-form" @submit.prevent="createUser">
        <UiFormField label="Username"><input v-model.trim="form.username" required /></UiFormField>
        <UiFormField label="Email"><input v-model.trim="form.email" type="email" required /></UiFormField>
        <UiFormField label="Temporary password"><PasswordField v-model="form.password" :username="form.username" :email="form.email" :rules="passwordRules" required /></UiFormField>
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
          <div class="accounts">
            <strong>Communication accounts</strong>
            <p v-if="user.has_all_account_access" class="all-access">All company accounts through assigned role.</p>
            <template v-else-if="communicationAccounts.length">
              <label v-for="account in communicationAccounts" :key="account.id">
                <input
                  type="checkbox"
                  :checked="(accountDrafts[user.id] || []).includes(account.id)"
                  :disabled="ownsAccount(user, account)"
                  @change="toggleAccount(user.id, account.id)"
                />
                <span>{{ account.display_name || account.name }}</span>
                <small>{{ account.phone_number || account.channel }}{{ ownsAccount(user, account) ? ' · owner' : '' }}</small>
              </label>
            </template>
            <p v-else class="empty-accounts">No communication accounts are configured.</p>
          </div>
          <div class="actions"><UiButton variant="primary" size="small" :disabled="busy === `save-${user.id}` || !(roleDrafts[user.id] || []).length" @click="saveUser(user)">Save access</UiButton><UiButton v-if="user.is_active" variant="danger" size="small" :disabled="busy === `active-${user.id}`" @click="setActive(user, false)">Suspend</UiButton><UiButton v-else size="small" :disabled="busy === `active-${user.id}`" @click="setActive(user, true)">Reactivate</UiButton></div>
          <div class="login-actions">
            <UiButton v-if="user.is_active" size="small" @click="openDialog('username', user)">Change username</UiButton>
            <UiButton size="small" @click="openDialog('password', user)">Set password</UiButton>
            <UiButton v-if="!isSelf(user)" variant="danger" size="small" @click="openDialog('remove', user)">Remove</UiButton>
          </div>
        </article>
      </div>
    </UiCard>

    <UiModal
      :open="Boolean(dialog)"
      :title="dialog ? DIALOG_TITLES[dialog.kind] : 'User'"
      :subtitle="dialog ? dialog.user.user.username : ''"
      size="small"
      @close="dialog = null"
    >
      <form v-if="dialog" class="dialog-form" @submit.prevent="submitDialog">
        <UiNotice v-if="dialogError" tone="danger">{{ dialogError }}</UiNotice>
        <UiFormField v-if="dialog.kind === 'username'" label="New username">
          <input v-model="dialog.value" required maxlength="150" />
        </UiFormField>
        <template v-else-if="dialog.kind === 'password'">
          <UiFormField label="New password">
            <PasswordField v-model="dialog.value" :username="dialog.user.user.username" :email="dialog.user.user.email" :rules="passwordRules" required />
          </UiFormField>
          <p class="dialog-note">{{ isSelf(dialog.user) ? 'You stay signed in here; your other sessions are signed out.' : 'They will be signed out everywhere and must sign in with this password.' }}</p>
        </template>
        <div v-else class="dialog-note">
          <p>{{ dialog.user.user.username }} will no longer be able to sign in and will disappear from this list. This cannot be undone.</p>
          <p>Nothing they worked on is deleted: their WhatsApp accounts, chats, inquiries and history stay, shown under <strong>{{ dialog.user.user.username }}-deleted-…</strong>. The username and email become free for a new user. Inquiry sharing they were part of ends.</p>
        </div>
        <div class="dialog-actions">
          <UiButton @click="dialog = null">Cancel</UiButton>
          <UiButton :variant="dialog.kind === 'remove' ? 'danger' : 'primary'" type="submit" :disabled="busy === `${dialog.kind}-${dialog.user.id}`">
            {{ dialog.kind === 'remove' ? 'Remove user' : 'Save' }}
          </UiButton>
        </div>
      </form>
    </UiModal>
  </UiPage>
</template>

<style scoped src="@/assets/company-users-view.css"></style>
