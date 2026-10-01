<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { companyAccessApi } from '@/api'

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
  <main class="roles-page">
    <header><p class="eyebrow">Authorization control plane</p><h1>Roles &amp; Permissions</h1><p>Define reusable company roles using explicit capability grants and record scopes.</p></header>
    <p v-if="error" class="notice error">{{ error }}</p><p v-if="success" class="notice success">{{ success }}</p>
    <section class="create-role"><input v-model.trim="createForm.name" placeholder="New role name" /><input v-model.trim="createForm.key" placeholder="role-key" /><input v-model.trim="createForm.description" placeholder="Purpose of this role" /><button @click="createRole">Create custom role</button></section>
    <section v-if="!loading" class="workspace">
      <aside><p class="section-label">Company roles</p><button v-for="role in roles" :key="role.id" :class="{ selected: role.id === selectedId }" @click="selectRole(role)"><span><strong>{{ role.name }}</strong><small>{{ role.is_system_role ? 'System template' : 'Custom role' }}</small></span><b>{{ role.member_count }}</b></button></aside>
      <article v-if="selected" class="permission-editor">
        <div class="role-head"><div><p class="section-label">{{ selected.key }}</p><h2>{{ selected.name }}</h2><p>{{ selected.description || 'No description provided.' }}</p></div><div><span v-if="selected.is_owner_role" class="owner">Owner role</span><span>{{ Object.keys(grants).length }} grants</span></div></div>
        <div v-for="(items, area) in groupedPermissions" :key="area" class="permission-group">
          <h3>{{ area.replaceAll('_', ' ') }}</h3>
          <div v-for="permission in items" :key="permission.code" class="permission-row">
            <label><input type="checkbox" :checked="Boolean(grants[permission.code])" @change="togglePermission(permission)" /><span><strong>{{ permission.label }}</strong><small>{{ permission.code }}</small></span></label>
            <span v-if="permission.is_sensitive" class="sensitive">Sensitive</span>
            <select v-if="permission.supports_scope && grants[permission.code]" v-model="grants[permission.code]"><option value="own">Own</option><option value="assigned">Assigned</option><option value="all">All company</option></select>
          </div>
        </div>
        <footer><p>{{ selected.is_owner_role ? 'Owner permissions are immutable to prevent company lockout.' : 'Changes invalidate permissions for every user assigned to this role.' }}</p><button class="save" :disabled="saving || selected.is_owner_role" @click="saveRole">{{ saving ? 'Saving...' : 'Save permissions' }}</button></footer>
      </article>
    </section>
    <p v-else class="loading">Loading authorization data...</p>
  </main>
</template>

<style scoped>
.roles-page{height:100%;overflow:auto;padding:28px;background:radial-gradient(circle at 88% 2%,#dff7e9,transparent 32%),#f7f9f7;color:#172033}.roles-page>header,.notice,.create-role,.workspace,.loading{max-width:1450px;margin-left:auto;margin-right:auto}.eyebrow,.section-label{margin:0;color:#167446;text-transform:uppercase;letter-spacing:.15em;font-size:.7rem;font-weight:850}h1{font:700 2.4rem Georgia,serif;margin:5px 0}header>p:last-child,.role-head p,footer p{color:#667085}.notice{margin-top:14px;padding:11px 14px;border-radius:10px}.error{background:#fff0ee;color:#b42318}.success{background:#eaf8ef;color:#14753f}.create-role{display:grid;grid-template-columns:1fr 1fr 2fr auto;gap:9px;margin-top:18px;background:#fff;padding:14px;border:1px solid #dfe8e2;border-radius:14px}.create-role input,button,select{font:inherit;border:1px solid #cfddd4;border-radius:9px;padding:9px 11px;background:#fff}.create-role button,.save{background:#157a46;color:#fff;border-color:#157a46;font-weight:800;cursor:pointer}.workspace{display:grid;grid-template-columns:280px 1fr;gap:17px;margin-top:17px}aside,.permission-editor{background:#fff;border:1px solid #dfe8e2;border-radius:16px;padding:16px;box-shadow:0 14px 35px #1535250d}aside{align-self:start;position:sticky;top:16px}aside>button{width:100%;display:flex;justify-content:space-between;text-align:left;border:0;margin-top:6px}aside>button.selected{background:#e7f6ed;color:#126d3f}aside span,aside small{display:block}aside small{margin-top:3px;color:#7b8b83}.role-head{display:flex;justify-content:space-between;gap:15px;border-bottom:1px solid #e4ebe7;padding-bottom:14px}.role-head h2{margin:4px 0}.role-head>div:last-child{display:flex;align-items:center;gap:7px}.role-head>div:last-child span{padding:6px 9px;border-radius:20px;background:#f0f3f1;font-size:.72rem;font-weight:800}.role-head .owner{background:#fff2c7;color:#785b00}.permission-group{margin-top:19px}.permission-group h3{text-transform:capitalize}.permission-row{display:grid;grid-template-columns:1fr auto 130px;align-items:center;gap:10px;border-top:1px solid #edf1ee;padding:10px 0}.permission-row label{display:flex;align-items:center;gap:10px}.permission-row label span,.permission-row small{display:block}.permission-row small{color:#7b8b83;margin-top:2px}.sensitive{color:#a54716;background:#fff0dd;border-radius:20px;padding:4px 7px;font-size:.67rem;font-weight:850}footer{position:sticky;bottom:-28px;display:flex;align-items:center;justify-content:space-between;background:#fff;border-top:1px solid #dfe8e2;padding:14px 0;margin-top:16px}.loading{text-align:center;padding:60px}@media(max-width:900px){.roles-page{padding:15px}.create-role,.workspace{grid-template-columns:1fr}aside{position:static}.permission-row{grid-template-columns:1fr auto}.permission-row select{grid-column:1/-1}.role-head{display:block}}
</style>
