<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { companyAccessApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'

const roles = ref([])
const permissions = ref([])
const selectedId = ref(null)
const grants = reactive({})
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const success = ref('')
const createForm = reactive({ name: '', key: '', description: '' })
const selected = computed(() => roles.value.find(role => role.id === selectedId.value) || null)
const groupedPermissions = computed(() => permissions.value.reduce((groups, item) => {
  ;(groups[item.area] ||= []).push(item)
  return groups
}, {}))

function apiMessage(exc, fallback) { return exc.response?.data?.detail || fallback }
function selectRole(role) {
  if (!role) {
    selectedId.value = null
    return
  }
  selectedId.value = role.id
  Object.keys(grants).forEach(key => delete grants[key])
  role.permissions.forEach(item => { grants[item.code] = item.scope })
}

async function load(preferredId = null) {
  loading.value = true; error.value = ''
  try {
    const [rolesResponse, permissionsResponse] = await Promise.all([
      companyAccessApi.roles(), companyAccessApi.permissions(),
    ])
    roles.value = rolesResponse.data
    permissions.value = permissionsResponse.data
    selectRole(roles.value.find(role => role.id === (preferredId || selectedId.value)) || roles.value[0])
  } catch (exc) { error.value = apiMessage(exc, 'Unable to load roles.') }
  finally { loading.value = false }
}

function togglePermission(permission) {
  if (grants[permission.code]) delete grants[permission.code]
  else grants[permission.code] = 'all'
}

async function saveRole() {
  if (!selected.value) return
  saving.value = true; error.value = ''; success.value = ''
  try {
    const payload = {
      permissions: permissions.value.filter(item => grants[item.code]).map(item => ({
        code: item.code,
        scope: item.supports_scope ? grants[item.code] : 'all',
      })),
    }
    const { data } = await companyAccessApi.updateRole(selected.value.id, payload)
    const index = roles.value.findIndex(role => role.id === data.id)
    roles.value[index] = data
    selectRole(data)
    success.value = `${data.name} permissions saved.`
  } catch (exc) { error.value = apiMessage(exc, 'Unable to save role.') }
  finally { saving.value = false }
}

async function createRole() {
  error.value = ''; success.value = ''
  try {
    const { data } = await companyAccessApi.createRole(createForm)
    Object.assign(createForm, { name: '', key: '', description: '' })
    await load(data.id)
    success.value = 'Custom role created. Select permissions before assigning it.'
  } catch (exc) { error.value = apiMessage(exc, 'Unable to create role.') }
}

onMounted(load)
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="Authorization control plane" title="Roles & Permissions" description="Define reusable company roles using explicit capability grants and record scopes." />
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice><UiNotice v-if="success" tone="success">{{ success }}</UiNotice>
    <UiCard class="create-role" title="Create custom role" subtitle="Add a reusable role, then select its explicit permission grants.">
      <div class="create-role-form"><UiFormField label="Role name"><input v-model.trim="createForm.name" placeholder="Sales manager" /></UiFormField><UiFormField label="Role key"><input v-model.trim="createForm.key" placeholder="sales-manager" /></UiFormField><UiFormField label="Purpose"><input v-model.trim="createForm.description" placeholder="Purpose of this role" /></UiFormField><UiButton variant="primary" @click="createRole">Create role</UiButton></div>
    </UiCard>
    <section v-if="!loading" class="workspace">
      <aside><p class="section-label">Company roles</p><button v-for="role in roles" :key="role.id" :class="{ selected: role.id === selectedId }" @click="selectRole(role)"><span><strong>{{ role.name }}</strong><small>{{ role.is_system_role ? 'System template' : 'Custom role' }}</small></span><UiBadge>{{ role.member_count }}</UiBadge></button></aside>
      <article v-if="selected" class="permission-editor">
        <div class="role-head"><div><p class="section-label">{{ selected.key }}</p><h2>{{ selected.name }}</h2><p>{{ selected.description || 'No description provided.' }}</p></div><div><UiBadge v-if="selected.is_owner_role" tone="warning">Owner role</UiBadge><UiBadge tone="info">{{ Object.keys(grants).length }} grants</UiBadge></div></div>
        <div v-for="(items, area) in groupedPermissions" :key="area" class="permission-group">
          <h3>{{ area.replaceAll('_', ' ') }}</h3>
          <div v-for="permission in items" :key="permission.code" class="permission-row">
            <label><input type="checkbox" :checked="Boolean(grants[permission.code])" @change="togglePermission(permission)" /><span><strong>{{ permission.label }}</strong><small>{{ permission.code }}</small></span></label>
            <UiBadge v-if="permission.is_sensitive" tone="warning">Sensitive</UiBadge>
            <select v-if="permission.supports_scope && grants[permission.code]" v-model="grants[permission.code]"><option value="own">Own</option><option value="assigned">Assigned</option><option value="all">All company</option></select>
          </div>
        </div>
        <footer><p>{{ selected.is_owner_role ? 'Owner permissions are immutable to prevent company lockout.' : 'Changes invalidate permissions for every user assigned to this role.' }}</p><UiButton variant="primary" :disabled="saving || selected.is_owner_role" @click="saveRole">{{ saving ? 'Saving...' : 'Save permissions' }}</UiButton></footer>
      </article>
      <UiEmptyState v-else title="No roles configured" description="Create a custom role to begin assigning permissions." />
    </section>
    <UiEmptyState v-else title="Loading authorization data..." busy />
  </UiPage>
</template>

<style scoped src="@/assets/company-roles-view.css"></style>
