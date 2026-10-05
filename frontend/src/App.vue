<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import AppNavigation from '@/components/AppNavigation.vue'
import InspiniaNavigation from '@/components/InspiniaNavigation.vue'
import { inspiniaClasses, inspiniaClassNames } from '@/themes/inspinia.js'

const auth = useAuthStore()
const rootClasses = computed(() => [
  'app-root h-screen bg-gray-50 flex flex-col overflow-hidden',
  `theme-${auth.uiTheme}`,
  ...(auth.uiTheme === 'inspinia' ? inspiniaClasses(auth.inspiniaConfig) : []),
])
const bodyThemeClasses = computed(() => [
  `theme-${auth.uiTheme}`,
  ...(auth.uiTheme === 'inspinia' ? inspiniaClassNames(auth.inspiniaConfig) : []),
])
let appliedBodyClasses = []

watch(bodyThemeClasses, classes => {
  document.body.classList.remove(...appliedBodyClasses)
  document.body.classList.add(...classes)
  document.body.dir = auth.uiTheme === 'inspinia' ? auth.inspiniaConfig.direction : 'ltr'
  appliedBodyClasses = classes
}, { immediate: true })

onBeforeUnmount(() => {
  document.body.classList.remove(...appliedBodyClasses)
  document.body.dir = 'ltr'
})
</script>

<template>
  <div :class="rootClasses" :dir="auth.uiTheme === 'inspinia' ? auth.inspiniaConfig.direction : 'ltr'">
    <AppNavigation v-if="auth.user && auth.uiTheme === 'chatlens'" />
    <InspiniaNavigation v-else-if="auth.user" />
    <div class="app-view flex-1 flex flex-col overflow-hidden min-h-0">
      <RouterView class="h-full" />
    </div>
  </div>
</template>
