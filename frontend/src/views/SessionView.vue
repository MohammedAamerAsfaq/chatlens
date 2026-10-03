<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useAccountsStore } from '@/stores/accounts'
import { useAuthStore } from '@/stores/auth.js'
import AccountCard from '@/components/AccountCard.vue'
import CreateAccountModal from '@/components/CreateAccountModal.vue'
import QRModal from '@/components/QRModal.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'

const store = useAccountsStore()
const auth = useAuthStore()
const showCreate = ref(false)
const qrAccountId = ref(null)
const switchingCompany = ref(false)
const togglingAiParsing = ref(false)
const aiParsingError = ref('')
const currentCompany = computed(() => auth.currentCompany)
const companyAiParsingEnabled = computed(() => currentCompany.value?.ai_parsing_enabled !== false)
const canToggleCompanyAiParsing = computed(() => {
  const role = auth.currentRole
  return ['super_user', 'admin'].includes(role)
})
let accountRefreshTimer = null

const workerStatus = computed(() => {
  const accounts = store.accounts || []
  const onlineCount = accounts.filter(a => a.worker_liveness_status === 'online').length
  const staleCount = accounts.filter(a => a.worker_liveness_status === 'stale').length
  const knownCount = onlineCount + staleCount
  const latestHeartbeat = accounts
    .map(a => a.last_worker_heartbeat_at)
    .filter(Boolean)
    .sort()
    .at(-1)

  if (onlineCount > 0) {
    return {
      label: 'Worker online',
      detail: `${onlineCount} active heartbeat${onlineCount === 1 ? '' : 's'}`,
      cls: 'worker-online',
      dot: 'dot-online',
      latestHeartbeat,
    }
  }
  if (staleCount > 0) {
    return {
      label: 'Worker stale',
      detail: `${staleCount} stale heartbeat${staleCount === 1 ? '' : 's'}`,
      cls: 'worker-stale',
      dot: 'dot-stale',
      latestHeartbeat,
    }
  }
  return {
    label: store.loading ? 'Checking worker' : 'Worker unknown',
    detail: knownCount ? 'No fresh heartbeat' : 'No heartbeat received',
    cls: 'worker-unknown',
    dot: 'dot-unknown',
    latestHeartbeat,
  }
})

function formatHeartbeat(dt) {
  if (!dt) return 'Never'
  return new Date(dt).toLocaleString()
}

onMounted(() => {
  store.fetchAccounts()
  accountRefreshTimer = setInterval(() => store.fetchAccounts(true), 30000)
})

onUnmounted(() => {
  clearInterval(accountRefreshTimer)
})

function onQRRequested(id) {
  qrAccountId.value = id
}

function onQRClose() {
  qrAccountId.value = null
  store.fetchAccounts()
}

async function switchCompany(companyId) {
  if (!companyId || companyId === currentCompany.value?.id) return
  switchingCompany.value = true
  try {
    await auth.selectCompany(companyId)
    window.location.assign('/')
  } finally {
    switchingCompany.value = false
  }
}

async function toggleCompanyAiParsing() {
  if (!currentCompany.value || !canToggleCompanyAiParsing.value || togglingAiParsing.value) return
  togglingAiParsing.value = true
  aiParsingError.value = ''
  try {
    await auth.updateCurrentCompanySettings({
      ai_parsing_enabled: !companyAiParsingEnabled.value,
    })
  } catch (err) {
    aiParsingError.value = err.response?.data?.detail || 'Failed to update company AI parsing.'
  } finally {
    togglingAiParsing.value = false
  }
}
</script>

<template>
  <UiPage width="standard">
    <UiCard class="workspace-panel">
      <div class="workspace-layout">
        <div>
          <p class="workspace-eyebrow">Active workspace</p>
          <h2 class="workspace-name">{{ currentCompany?.name || 'No company selected' }}</h2>
          <p class="workspace-copy">Session, trading, contacts, and reporting data are scoped to this company.</p>
        </div>
        <div v-if="auth.hasMultipleMemberships" class="workspace-memberships">
          <button v-for="membership in auth.memberships" :key="membership.company.id" type="button" class="workspace-pill" :class="{ 'workspace-pill-active': membership.company.id === currentCompany?.id }" :disabled="switchingCompany || membership.company.id === currentCompany?.id" @click="switchCompany(membership.company.id)">
            <span>{{ membership.company.name }}</span><span class="workspace-pill-role">{{ membership.role.replaceAll('_', ' ') }}</span>
          </button>
        </div>
      </div>
    </UiCard>

    <UiPageHeader eyebrow="Communication accounts" title="Session Manager" description="Manage WhatsApp linked-device sessions and account-level controls.">
      <template #actions><div class="session-actions">
        <div class="company-ai-toggle-wrap">
          <button
            type="button"
            class="company-ai-toggle"
            :class="companyAiParsingEnabled ? 'company-ai-on' : 'company-ai-off'"
            :disabled="!currentCompany || !canToggleCompanyAiParsing || togglingAiParsing"
            :title="canToggleCompanyAiParsing ? 'Toggle AI parsing for this company' : 'Company admin access required'"
            @click="toggleCompanyAiParsing"
          >
            <span class="company-ai-label">AI Parsing</span>
            <strong>{{ companyAiParsingEnabled ? 'ON' : 'OFF' }}</strong>
            <small>{{ togglingAiParsing ? 'Updating...' : 'Company level' }}</small>
          </button>
        </div>
        <div :class="['worker-status', workerStatus.cls]" :title="`Latest heartbeat: ${formatHeartbeat(workerStatus.latestHeartbeat)}`">
          <span :class="['worker-dot', workerStatus.dot]" />
          <span>
            <strong>{{ workerStatus.label }}</strong>
            <small>{{ workerStatus.detail }}</small>
          </span>
        </div>
        <UiButton variant="primary" @click="showCreate = true">+ Add Account</UiButton>
      </div></template>
    </UiPageHeader>

    <UiNotice v-if="aiParsingError" tone="danger">{{aiParsingError}}</UiNotice>

    <UiEmptyState v-if="store.loading" title="Loading accounts" description="Checking configured communication sessions." busy />

    <UiNotice v-else-if="store.error" tone="danger">{{store.error}}</UiNotice>

    <UiEmptyState v-else-if="store.accounts.length === 0" title="No accounts yet" description="Add an account to connect the first WhatsApp linked device."><UiButton variant="primary" size="small" @click="showCreate=true">Add Account</UiButton></UiEmptyState>

    <div v-else class="session-account-grid">
      <AccountCard
        v-for="account in store.accounts"
        :key="account.id"
        :account="account"
        @show-qr="onQRRequested"
        @refresh="store.fetchAccounts"
      />
    </div>

    <CreateAccountModal
      v-if="showCreate"
      @close="showCreate = false"
      @created="store.fetchAccounts"
    />

    <QRModal
      v-if="qrAccountId"
      :account-id="qrAccountId"
      @close="onQRClose"
    />
  </UiPage>
</template>

<style scoped src="@/assets/session-view.css"></style>
