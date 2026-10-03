<script setup>
defineProps({
  title: { type: String, required: true },
  setting: { type: String, required: true },
  values: { type: Array, default: () => [] },
  selected: { type: [String, Boolean], default: '' },
  compact: Boolean,
  busy: Boolean,
})
defineEmits(['select'])
const previewBase = `${import.meta.env.BASE_URL}inspinia-previews/`
const previewPrefixes = {
  skin: 'skin',
  color_scheme: 'theme',
  topbar_color: 'topbar-color',
  sidenav_color: 'sidenav-color',
  sidenav_size: 'sidenav-size',
  layout_width: 'width',
  direction: 'dir',
}
function label(value) {
  if (typeof value === 'boolean') return value ? 'Shown' : 'Hidden'
  return String(value).replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())
}
function previewUrl(setting, value) {
  const prefix = previewPrefixes[setting]
  if (!prefix) return ''
  const filename = `${prefix}-${String(value).replaceAll('_', '-')}.png`
  return `${previewBase}${filename}`
}
</script>

<template>
  <section class="choice-group">
    <h3>{{ title }}</h3>
    <div class="choice-grid" :class="{ compact }">
      <button v-for="value in values" :key="String(value)" :class="{ selected: selected === value }" :disabled="busy" @click="$emit('select', setting, value)">
        <img v-if="previewUrl(setting, value)" class="choice-preview actual-preview" :src="previewUrl(setting, value)" :alt="`${label(value)} ${title} preview`">
        <span v-else class="choice-preview" :data-setting="setting" :data-value="String(value).replaceAll('_', '-')"><i></i><b></b><em></em></span>
        <strong>{{ label(value) }}</strong><span v-if="selected === value" class="check">&#10003;</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.choice-group{padding:20px 22px;border-bottom:1px dashed #dfe4e8}.choice-group h3{margin:0 0 13px;color:#3f4b57;font-size:.82rem}.choice-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.choice-grid.compact{grid-template-columns:repeat(3,minmax(0,1fr))}button{position:relative;min-width:0;padding:7px;border:1px solid #dfe4e8;border-radius:6px;background:#fff;color:#66727e;cursor:pointer}button:hover,button.selected{border-color:#1ab394;background:#f2faf8}button>strong{display:block;margin-top:6px;overflow:hidden;font-size:.69rem;text-overflow:ellipsis;white-space:nowrap}.check{position:absolute;right:9px;top:9px;display:grid;place-items:center;width:18px;height:18px;border-radius:50%;background:#1ab394;color:#fff;font-size:.65rem}.choice-grid:not(.compact) .choice-preview{height:96px}
.choice-preview{position:relative;display:block;width:100%;height:62px;box-sizing:border-box;border:1px solid #e2e6e9;border-radius:3px;background:#f1f2f7;overflow:hidden}.actual-preview{object-fit:cover;object-position:top}.choice-preview i{position:absolute;inset:0 auto 0 0;width:27%;background:#23303c}.choice-preview b{position:absolute;inset:0 0 auto 27%;height:20%;background:#fff}.choice-preview em{position:absolute;inset:30% 7% 10% 34%;border-radius:2px;background:#fff}
[data-setting="skin"][data-value="minimal"] i{width:15%}[data-setting="skin"][data-value="modern"]{background:#edf4ff}[data-setting="skin"][data-value="material"] b{background:#4c84ff}[data-setting="skin"][data-value="saas"]{background:#f2f0ff}[data-setting="skin"][data-value="flat"] em{box-shadow:none}[data-setting="skin"][data-value="galaxy"]{background:#14172b}[data-setting="skin"][data-value="luxe"]{background:#f5f0e8}[data-setting="skin"][data-value="retro"]{background:#f7ecd0}[data-setting="skin"][data-value="neon"]{background:#111827}[data-setting="skin"][data-value="neon"] em{background:#16f2a4}[data-setting="skin"][data-value="pixel"]{image-rendering:pixelated;background:#dfe6ee}
[data-setting="color_scheme"][data-value="dark"]{background:#202934}[data-setting="color_scheme"][data-value="dark"] b,[data-setting="color_scheme"][data-value="dark"] em{background:#313d49}[data-setting="color_scheme"][data-value="system"]{background:linear-gradient(135deg,#f1f2f7 50%,#202934 50%)}
[data-setting="topbar_color"][data-value="dark"] b{background:#23303c}[data-setting="topbar_color"][data-value="gray"] b{background:#d9dde2}[data-setting="topbar_color"][data-value="gradient"] b{background:linear-gradient(90deg,#1ab394,#3f7ee8)}
[data-setting="sidenav_color"][data-value="light"] i{background:#fff}[data-setting="sidenav_color"][data-value="gray"] i{background:#4b5563}[data-setting="sidenav_color"][data-value="gradient"] i{background:linear-gradient(#164e63,#312e81)}[data-setting="sidenav_color"][data-value="image"] i{background:linear-gradient(#172554bb,#172554bb),repeating-linear-gradient(45deg,#1ab394 0 3px,#23303c 3px 7px)}
[data-setting="sidenav_size"][data-value="compact"] i{width:20%}[data-setting="sidenav_size"][data-value="condensed"] i,[data-setting="sidenav_size"][data-value="on-hover"] i,[data-setting="sidenav_size"][data-value="on-hover-active"] i{width:11%}[data-setting="sidenav_size"][data-value="offcanvas"] i{width:0}
[data-setting="layout_width"][data-value="boxed"] em{left:40%;right:13%}[data-setting="direction"][data-value="rtl"] i{inset:0 0 0 auto}[data-setting="direction"][data-value="rtl"] b{inset:0 27% auto 0}[data-setting="direction"][data-value="rtl"] em{inset:30% 34% 10% 7%}[data-setting="orientation"][data-value="horizontal"] i{display:none}[data-setting="orientation"][data-value="horizontal"] b{inset:0 0 auto;height:28%}[data-setting="orientation"][data-value="horizontal"] em{inset:38% 7% 10%}
[data-setting="sidebar_user"][data-value="false"]:after{content:"";position:absolute;left:4%;top:10%;width:19%;height:12%;background:#ed5565}button:disabled{opacity:.55;cursor:not-allowed}@media(max-width:520px){.choice-grid.compact{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
