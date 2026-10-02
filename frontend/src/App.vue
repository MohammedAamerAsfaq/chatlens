<script setup>
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import AppNavigation from '@/components/AppNavigation.vue'

const auth = useAuthStore()
</script>

<template>
  <div class="h-screen bg-gray-50 flex flex-col overflow-hidden">
    <AppNavigation v-if="auth.user" />
    <div class="flex-1 flex flex-col overflow-hidden min-h-0">
      <RouterView class="h-full" />
    </div>
  </div>
</template>
