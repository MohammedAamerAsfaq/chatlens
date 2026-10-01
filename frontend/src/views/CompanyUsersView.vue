<script setup>
import { onMounted, reactive, ref } from 'vue'
import { companyAccessApi } from '@/api'

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
  <main class="access-page">
    <header><p class="eyebrow">Company access</p><h1>Users</h1><p>Create company users, assign multiple roles, and suspend access without deleting business records.</p></header>
    <p class="rollout">RBAC is active for user and role administration. Existing application areas will move from legacy role checks to permission codes route by route.</p>
    <p v-if="error" class="notice error">{{ error }}</p><p v-if="success" class="notice success">{{ success }}</p>

    <section class="panel create-panel">
      <div><h2>Add user</h2><p>A temporary password is required in this implementation phase.</p></div>
      <form @submit.prevent="createUser">
        <label>Username<input v-model.trim="form.username" required /></label>
        <label>Email<input v-model.trim="form.email" type="email" required /></label>
        <label>Temporary password<input v-model="form.password" type="password" required /></label>
        <label>Initial role<select v-model="form.role_ids" multiple required><option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option></select></label>
        <button class="primary" :disabled="busy === 'create'">{{ busy === 'create' ? 'Creating...' : 'Create user' }}</button>
      </form>
    </section>

    <section class="panel">
      <div class="panel-title"><div><h2>Company users</h2><p>{{ users.length }} memberships in this company</p></div><button @click="load">Refresh</button></div>
      <p v-if="loading" class="empty">Loading users...</p>
      <div v-else class="user-grid">
        <article v-for="user in users" :key="user.id" :class="['user-card', { inactive: !user.is_active }]">
          <div class="identity"><div class="avatar">{{ user.user.username.slice(0, 1).toUpperCase() }}</div><div><h3>{{ user.user.username }}</h3><p>{{ user.user.email }}</p></div><span :class="user.is_active ? 'active' : 'suspended'">{{ user.is_active ? 'Active' : 'Suspended' }}</span></div>
          <div class="roles"><strong>Roles</strong><label v-for="role in roles" :key="role.id"><input type="checkbox" :checked="(roleDrafts[user.id] || []).includes(role.id)" @change="toggleRole(user.id, role.id)" />{{ role.name }}</label></div>
          <div class="actions"><button class="primary" :disabled="busy === `save-${user.id}` || !(roleDrafts[user.id] || []).length" @click="saveUser(user)">Save roles</button><button v-if="user.is_active" class="danger" :disabled="busy === `active-${user.id}`" @click="setActive(user, false)">Suspend</button><button v-else :disabled="busy === `active-${user.id}`" @click="setActive(user, true)">Reactivate</button></div>
        </article>
      </div>
    </section>
  </main>
</template>

<style scoped>
.access-page{height:100%;overflow-y:auto;padding:28px;background:radial-gradient(circle at 90% 0,#dff7e9,transparent 34%),#f7f9f7;color:#172033}.access-page>header,.panel,.notice,.rollout{max-width:1400px;margin-left:auto;margin-right:auto}.eyebrow{margin:0;color:#167446;text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;font-weight:800}h1{font:700 2.4rem Georgia,serif;margin:5px 0}header>p:last-child,.panel p{color:#667085}.rollout,.notice{padding:12px 15px;border-radius:11px;margin-top:16px}.rollout{background:#fff7d6;color:#795d08;border:1px solid #eadb99}.notice.error{background:#fff0ee;color:#b42318}.notice.success{background:#eaf8ef;color:#14753f}.panel{margin-top:18px;background:#fff;border:1px solid #dfe8e2;border-radius:17px;padding:20px;box-shadow:0 14px 35px #1535250d}.create-panel{display:grid;grid-template-columns:240px 1fr;gap:22px}.create-panel form{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr)) auto;gap:12px;align-items:end}label{display:grid;gap:6px;font-size:.76rem;font-weight:800;color:#52625a}input,select,button{font:inherit;border:1px solid #cfddd4;border-radius:9px;padding:9px 11px;background:#fff}select[multiple]{min-height:78px}button{cursor:pointer;font-weight:750}.primary{background:#157a46;color:#fff;border-color:#157a46}.danger{color:#b42318;border-color:#f1c2bd}.panel-title,.identity,.actions{display:flex;align-items:center;justify-content:space-between;gap:12px}.panel-title h2,.identity h3,.identity p{margin:0}.user-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px;margin-top:16px}.user-card{border:1px solid #dfe8e2;border-radius:13px;padding:15px}.user-card.inactive{opacity:.68}.avatar{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;background:#dff4e8;color:#126c3e;font-weight:900}.identity>span{margin-left:auto;padding:5px 9px;border-radius:20px;font-size:.7rem;font-weight:850}.active{background:#dcf7e5;color:#11723d}.suspended{background:#f2f4f7;color:#667085}.roles{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.roles>strong{width:100%}.roles label{display:flex;align-items:center;gap:5px;background:#f4f8f5;padding:6px 9px;border-radius:8px}.actions{justify-content:flex-end}.empty{padding:30px;text-align:center}@media(max-width:900px){.access-page{padding:16px}.create-panel{grid-template-columns:1fr}.create-panel form{grid-template-columns:1fr}.user-grid{grid-template-columns:1fr}}
</style>
