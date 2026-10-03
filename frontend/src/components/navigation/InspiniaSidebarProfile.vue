<script setup>
defineProps({ username: { type: String, default: '' }, role: { type: String, default: '' }, collapsed: Boolean })
defineEmits(['open-settings'])
</script>

<template>
  <section class="sidebar-profile" :class="{ compact: collapsed }">
    <div class="sidebar-avatar">{{ username.slice(0, 1).toUpperCase() || '?' }}</div>
    <div class="sidebar-profile-copy"><strong>{{ username }}</strong><span>{{ role }}</span></div>
    <button title="Open settings" aria-label="Open settings" @click="$emit('open-settings')">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19 14.5 21 16l-2 3-2.4-1a8 8 0 0 1-2.1 1.2L14 22h-4l-.5-2.8A8 8 0 0 1 7.4 18L5 19l-2-3 2-1.5a8 8 0 0 1 0-5L3 8l2-3 2.4 1a8 8 0 0 1 2.1-1.2L10 2h4l.5 2.8A8 8 0 0 1 16.6 6L19 5l2 3-2 1.5a8 8 0 0 1 0 5Z"/></svg>
    </button>
  </section>
</template>

<style scoped>
.sidebar-profile{position:relative;display:grid;grid-template-columns:42px 1fr auto;align-items:center;gap:10px;margin:12px 10px 7px;padding:14px 10px;border:1px solid #ffffff12;border-radius:8px;background:linear-gradient(135deg,#ffffff0d,#1ab3940d);overflow:hidden}
.sidebar-profile:after{content:"";position:absolute;inset:auto -28px -36px auto;width:105px;height:105px;border:1px solid #ffffff0a;border-radius:50%}
.sidebar-avatar{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;background:#1ab394;color:#fff;font-weight:800}
.sidebar-profile-copy{display:flex;min-width:0;flex-direction:column}.sidebar-profile-copy strong{overflow:hidden;color:#fff;font-size:.82rem;text-overflow:ellipsis;white-space:nowrap}.sidebar-profile-copy span{margin-top:3px;color:#8495ab;font-size:.69rem;text-transform:capitalize}
button{position:relative;z-index:1;display:grid;place-items:center;width:28px;height:28px;border:0;border-radius:5px;background:transparent;color:#8495ab;cursor:pointer}button:hover{background:#ffffff12;color:#fff}svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.compact{grid-template-columns:1fr;margin:10px 8px;padding:8px}.compact .sidebar-avatar{width:38px;height:38px}.compact .sidebar-profile-copy,.compact button{display:none}
</style>
