<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="h-screen bg-gray-50 flex flex-col overflow-hidden">
    <nav class="bg-gray-900 text-white px-6 py-3 flex items-center gap-6 shadow shrink-0">
      <span class="text-green-400 font-bold text-lg mr-4">ChatLens</span>
      <RouterLink
        to="/"
        class="text-sm text-gray-300 hover:text-white transition-colors"
        active-class="text-white font-medium"
      >
        Sessions
      </RouterLink>
      <RouterLink
        to="/conversations"
        class="text-sm text-gray-300 hover:text-white transition-colors"
        active-class="text-white font-medium"
      >
        Conversations
      </RouterLink>
      <RouterLink
        to="/activity"
        class="text-sm text-gray-300 hover:text-white transition-colors"
        active-class="text-white font-medium"
      >
        Activity
      </RouterLink>
    </nav>
    <div class="flex-1 flex flex-col overflow-hidden min-h-0">
      <RouterView class="h-full" />
    </div>
  </div>
</template>
