<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { tenantAdminApi } from '@/api'
import { useAuthStore } from '@/stores/auth.js'

const auth = useAuthStore()

const loading = ref(false)
const error = ref('')
const companies = ref([])
const memberships = ref([])

const companyForm = ref({
  company_name: '',
  industry_type: 'general',
  email: '',
  username: '',
  password: '',
})
const userForm = ref({
  company_id: '',
  email: '',
  username: '',
  password: '',
  role: 'user',
})
const savingCompany = ref(false)
const savingUser = ref(false)
const companySuccess = ref('')
const userSuccess = ref('')
const companyFieldErrors = ref({})
const userFieldErrors = ref({})

const manageableCompanies = computed(() =>
  companies.value.filter(company => company.company_type !== 'control'),
)

function resetCompanyErrors() {
  companyFieldErrors.value = {}
}

function resetUserErrors() {
  userFieldErrors.value = {}
}

function setFieldError(target, field, message) {
  target.value = { ...target.value, [field]: message }
}

function validateCompanyForm() {
  resetCompanyErrors()
  let valid = true
  if (!companyForm.value.company_name.trim()) {
    setFieldError(companyFieldErrors, 'company_name', 'Company name is required.')
    valid = false
  }
  if (!companyForm.value.email.trim()) {
    setFieldError(companyFieldErrors, 'email', 'Admin email is required.')
    valid = false
  }
  if (!companyForm.value.username.trim()) {
    setFieldError(companyFieldErrors, 'username', 'Admin username is required.')
    valid = false
  }
  if (!companyForm.value.password) {
    setFieldError(companyFieldErrors, 'password', 'Admin password is required.')
    valid = false
  } else if (companyForm.value.password.length < 6) {
    setFieldError(companyFieldErrors, 'password', 'Use at least 6 characters for the password.')
    valid = false
  }
  return valid
}

function validateUserForm() {
  resetUserErrors()
  let valid = true
  if (!manageableCompanies.value.length) {
    setFieldError(userFieldErrors, 'company_id', 'Create a company first before adding users.')
    valid = false
  } else if (!userForm.value.company_id) {
    setFieldError(userFieldErrors, 'company_id', 'Select a company.')
    valid = false
  }
  if (!userForm.value.email.trim()) {
    setFieldError(userFieldErrors, 'email', 'Email is required.')
    valid = false
  }
  if (!userForm.value.username.trim()) {
    setFieldError(userFieldErrors, 'username', 'Username is required.')
    valid = false
  }
  if (!userForm.value.password) {
    setFieldError(userFieldErrors, 'password', 'Password is required.')
    valid = false
  } else if (userForm.value.password.length < 6) {
    setFieldError(userFieldErrors, 'password', 'Use at least 6 characters for the password.')
    valid = false
  }
  return valid
}

async function load() {
  if (!auth.canManageTenants) return
  loading.value = true
  error.value = ''
  try {
    const [companiesRes, usersRes] = await Promise.all([
      tenantAdminApi.listCompanies(),
      tenantAdminApi.listUsers(),
    ])
    companies.value = companiesRes.data
    memberships.value = usersRes.data
    if (!userForm.value.company_id && manageableCompanies.value.length) {
      userForm.value.company_id = manageableCompanies.value[0].id
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to load tenant admin data'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => auth.canManageTenants, () => load())

async function submitCompany() {
  if (!validateCompanyForm()) return
  savingCompany.value = true
  companySuccess.value = ''
  error.value = ''
  try {
    const { data } = await tenantAdminApi.enrollCompany(companyForm.value)
    companySuccess.value = `Created ${data.company.name} with admin ${data.membership.user.username}.`
    companyForm.value = {
      company_name: '',
      industry_type: 'general',
      email: '',
      username: '',
      password: '',
    }
    resetCompanyErrors()
    await load()
    userForm.value.company_id = data.company.id
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to create company'
  } finally {
    savingCompany.value = false
  }
}

async function submitUser() {
  if (!validateUserForm()) return
  savingUser.value = true
  userSuccess.value = ''
  error.value = ''
  try {
    const { data } = await tenantAdminApi.createUser({
      ...userForm.value,
      company_id: Number(userForm.value.company_id),
    })
    userSuccess.value = `Created ${data.user.username} in ${data.company.name} as ${data.role.replaceAll('_', ' ')}.`
    userForm.value = {
      company_id: userForm.value.company_id,
      email: '',
      username: '',
      password: '',
      role: 'user',
    }
    resetUserErrors()
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to create user'
  } finally {
    savingUser.value = false
  }
}
</script>

<template>
  <div class="tenant-admin-view">
    <div class="header">
      <div>
        <h1>Tenant Admin</h1>
        <p>Enroll companies and create company users from the control workspace.</p>
      </div>
    </div>

    <div v-if="!auth.canManageTenants" class="locked-card">
      <h2>Control workspace required</h2>
      <p>Switch to the control company workspace with an admin or super user role to manage companies and users.</p>
    </div>

    <template v-else>
      <div v-if="error" class="message error">{{ error }}</div>
      <div v-if="companySuccess" class="message success">{{ companySuccess }}</div>
      <div v-if="userSuccess" class="message success">{{ userSuccess }}</div>

      <div class="grid">
        <section class="card">
          <h2>Enroll Company</h2>
          <p class="card-copy">Creates a company and its initial super user.</p>
          <form class="form" @submit.prevent="submitCompany">
            <label>
              <span>Company name</span>
              <input v-model="companyForm.company_name" required />
              <small v-if="companyFieldErrors.company_name" class="field-error">{{ companyFieldErrors.company_name }}</small>
            </label>
            <label>
              <span>Industry</span>
              <select v-model="companyForm.industry_type">
                <option value="general">General</option>
                <option value="trading">Trading</option>
                <option value="real_estate">Real Estate</option>
              </select>
            </label>
            <label>
              <span>Admin email</span>
              <input v-model="companyForm.email" type="email" required />
              <small v-if="companyFieldErrors.email" class="field-error">{{ companyFieldErrors.email }}</small>
            </label>
            <label>
              <span>Admin username</span>
              <input v-model="companyForm.username" required />
              <small v-if="companyFieldErrors.username" class="field-error">{{ companyFieldErrors.username }}</small>
            </label>
            <label>
              <span>Admin password</span>
              <input v-model="companyForm.password" type="password" required />
              <small v-if="companyFieldErrors.password" class="field-error">{{ companyFieldErrors.password }}</small>
            </label>
            <button class="btn-primary" :disabled="savingCompany">
              {{ savingCompany ? 'Creating…' : 'Create Company' }}
            </button>
          </form>
        </section>

        <section class="card">
          <h2>Create Company User</h2>
          <p class="card-copy">Adds a new user directly into an existing company.</p>
          <div v-if="!manageableCompanies.length" class="inline-empty-state">
            No customer companies exist yet. Create a company on the left first, then you can add more users here.
          </div>
          <form class="form" @submit.prevent="submitUser">
            <label>
              <span>Company</span>
              <select v-model="userForm.company_id" required>
                <option disabled value="">Select company…</option>
                <option v-for="company in manageableCompanies" :key="company.id" :value="company.id">
                  {{ company.name }}
                </option>
              </select>
              <small v-if="userFieldErrors.company_id" class="field-error">{{ userFieldErrors.company_id }}</small>
            </label>
            <label>
              <span>Role</span>
              <select v-model="userForm.role">
                <option value="super_user">Super User</option>
                <option value="admin">Admin</option>
                <option value="manager">Manager</option>
                <option value="user">User</option>
                <option value="viewer">Viewer</option>
              </select>
            </label>
            <label>
              <span>Email</span>
              <input v-model="userForm.email" type="email" required />
              <small v-if="userFieldErrors.email" class="field-error">{{ userFieldErrors.email }}</small>
            </label>
            <label>
              <span>Username</span>
              <input v-model="userForm.username" required />
              <small v-if="userFieldErrors.username" class="field-error">{{ userFieldErrors.username }}</small>
            </label>
            <label>
              <span>Password</span>
              <input v-model="userForm.password" type="password" required />
              <small v-if="userFieldErrors.password" class="field-error">{{ userFieldErrors.password }}</small>
            </label>
            <button class="btn-primary" :disabled="savingUser || !manageableCompanies.length">
              {{ savingUser ? 'Creating…' : 'Create User' }}
            </button>
          </form>
        </section>
      </div>

      <div class="grid lower">
        <section class="card">
          <div class="section-head">
            <h2>Companies</h2>
            <span>{{ companies.length }} total</span>
          </div>
          <div v-if="loading" class="empty">Loading…</div>
          <div v-else class="table-scroll">
            <table class="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Industry</th>
                  <th>Users</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="company in companies" :key="company.id">
                  <td>{{ company.name }}</td>
                  <td>{{ company.company_type }}</td>
                  <td>{{ company.industry_type }}</td>
                  <td>{{ company.membership_count }}</td>
                  <td>{{ company.is_active ? 'Active' : 'Inactive' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card">
          <div class="section-head">
            <h2>Company Users</h2>
            <span>{{ memberships.length }} memberships</span>
          </div>
          <div v-if="loading" class="empty">Loading…</div>
          <div v-else class="table-scroll">
            <table class="table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Company</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="membership in memberships" :key="membership.id">
                  <td>{{ membership.user.username }}</td>
                  <td>{{ membership.user.email }}</td>
                  <td>{{ membership.company.name }}</td>
                  <td>{{ membership.role.replaceAll('_', ' ') }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tenant-admin-view { display: flex; flex-direction: column; gap: 20px; padding: 24px; height: 100%; overflow-y: auto; box-sizing: border-box; }
.header h1 { margin: 0; font-size: 1.5rem; color: #111827; }
.header p { margin: 6px 0 0; color: #6b7280; }
.locked-card, .card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 20px;
}
.locked-card h2, .card h2 { margin: 0; font-size: 1.1rem; color: #111827; }
.locked-card p, .card-copy { margin: 8px 0 0; color: #6b7280; }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.grid.lower { align-items: start; }
.form { display: flex; flex-direction: column; gap: 14px; margin-top: 18px; }
.form label { display: flex; flex-direction: column; gap: 6px; font-size: 0.88rem; color: #374151; }
.form input, .form select {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 0.92rem;
}
.field-error {
  color: #b91c1c;
  font-size: 0.78rem;
  line-height: 1.35;
}
.inline-empty-state {
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  color: #475569;
  font-size: 0.88rem;
}
.btn-primary {
  align-self: flex-start;
  padding: 10px 16px;
  background: #2563eb;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.message {
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 0.9rem;
}
.message.error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.message.success { background: #ecfdf5; color: #166534; border: 1px solid #bbf7d0; }
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 14px;
}
.section-head span { font-size: 0.82rem; color: #6b7280; }
.table-scroll {
  max-height: 320px;
  overflow: auto;
  border-top: 1px solid #f3f4f6;
}
.table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.table th, .table td { text-align: left; padding: 10px 0; border-bottom: 1px solid #f3f4f6; }
.table thead th {
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 1;
}
.table th { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7280; }
.empty { color: #9ca3af; font-size: 0.9rem; padding: 12px 0; }
@media (max-width: 960px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
