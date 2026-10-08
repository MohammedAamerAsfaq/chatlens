<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import AppNavigation from '@/components/AppNavigation.vue'
import InspiniaNavigation from '@/components/InspiniaNavigation.vue'
import ReminderNotificationCenter from '@/features/clientpulse/components/ReminderNotificationCenter.vue'
import { inspiniaClasses, inspiniaClassNames } from '@/themes/inspinia.js'

const auth = useAuthStore()
const rootClasses = computed(() => [
  'app-root h-screen bg-gray-50 flex flex-col overflow-hidden',
  `theme-${auth.uiTheme}`,
  ...(auth.uiTheme === 'inspinia' ? inspiniaClasses(auth.inspiniaConfig) : []),
])
const teleportHostClasses = computed(() => [
  'ui-teleport-host',
  `theme-${auth.uiTheme}`,
  ...(auth.uiTheme === 'inspinia' ? inspiniaClassNames(auth.inspiniaConfig) : []),
])
let appliedHostClasses = []

watch(teleportHostClasses, classes => {
  const host = document.getElementById('ui-teleport-host')
  if (!host) return
  host.classList.remove(...appliedHostClasses)
  host.classList.add(...classes)
  host.dir = auth.uiTheme === 'inspinia' ? auth.inspiniaConfig.direction : 'ltr'
  appliedHostClasses = classes
}, { immediate: true })

onBeforeUnmount(() => {
  const host = document.getElementById('ui-teleport-host')
  host?.classList.remove(...appliedHostClasses)
})
</script>

<template>
  <div :class="rootClasses" :dir="auth.uiTheme === 'inspinia' ? auth.inspiniaConfig.direction : 'ltr'">
    <AppNavigation v-if="auth.user && auth.uiTheme === 'chatlens'" />
    <InspiniaNavigation v-else-if="auth.user" />
    <div class="app-view flex-1 flex flex-col overflow-hidden min-h-0">
      <RouterView class="h-full" />
    </div>
    <ReminderNotificationCenter v-if="auth.user && auth.hasPermission('clientpulse.reminders.view')" />
  </div>
</template>
