<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import NavigationChevron from './NavigationChevron.vue'

defineProps({ sections: { type: Array, default: () => [] }, apps: { type: Array, default: () => [] } })
const openMenu = ref('')
const root = ref(null)
function toggle(menu) { openMenu.value = openMenu.value === menu ? '' : menu }
function close() { openMenu.value = '' }
function closeFromOutside(event) {
  if (openMenu.value && !root.value?.contains(event.target)) close()
}
onMounted(() => document.addEventListener('pointerdown', closeFromOutside))
onUnmounted(() => document.removeEventListener('pointerdown', closeFromOutside))
</script>

<template>
  <div ref="root" class="topbar-menus" @keydown.esc="close">
    <div class="topbar-menu">
      <button type="button" aria-haspopup="menu" :aria-expanded="openMenu === 'mega'" @click="toggle('mega')">Mega Menu <NavigationChevron :open="openMenu === 'mega'" /></button>
      <div v-if="openMenu === 'mega'" class="mega-panel" role="menu">
        <section v-for="section in sections" :key="section.id">
          <RouterLink :to="section.to" class="menu-heading" @click="close">{{ section.label }}</RouterLink>
          <RouterLink v-for="child in section.children || []" :key="child.route" :to="child.to" @click="close">{{ child.label }}</RouterLink>
        </section>
      </div>
    </div>
    <div class="topbar-menu">
      <button type="button" aria-haspopup="menu" :aria-expanded="openMenu === 'apps'" @click="toggle('apps')">Apps <NavigationChevron :open="openMenu === 'apps'" /></button>
      <div v-if="openMenu === 'apps'" class="apps-panel" role="menu">
        <RouterLink v-for="item in apps" :key="item.route" :to="item.to" @click="close">{{ item.label }}</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.topbar-menus{display:flex;align-self:stretch}.topbar-menu{position:relative;display:flex}.topbar-menu>button{display:flex;align-items:center;gap:5px;padding:0 13px;border:0;background:transparent;color:var(--ui-text-muted);font-family:"Open Sans","Segoe UI",sans-serif;font-size:.76rem;font-weight:600;line-height:1.2;cursor:pointer}.topbar-menu>button:hover{color:var(--ui-primary);background:var(--ui-surface-muted)}
.mega-panel,.apps-panel{position:absolute;top:100%;z-index:100;padding:12px;border:1px solid var(--ui-border);border-radius:7px;background:var(--ui-surface);box-shadow:var(--ui-shadow-popover)}.mega-panel{left:0;display:grid;grid-template-columns:repeat(3,minmax(145px,1fr));gap:12px;width:min(600px,70vw)}.apps-panel{left:0;display:grid;width:210px}
.mega-panel section{display:flex;flex-direction:column}.mega-panel a,.apps-panel a{padding:7px 9px;border-radius:5px;color:var(--ui-text-muted);font-size:.75rem;text-decoration:none}.mega-panel a:hover,.apps-panel a:hover,.mega-panel a.router-link-active,.apps-panel a.router-link-active{background:var(--ui-primary-soft);color:var(--ui-primary)}.mega-panel .menu-heading{color:var(--ui-text-strong);font-weight:800}
@media(max-width:1100px){.topbar-menus{display:none}}
</style>
