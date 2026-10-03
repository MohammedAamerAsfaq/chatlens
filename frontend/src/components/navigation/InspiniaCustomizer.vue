<script setup>
import CustomizerChoiceGroup from './CustomizerChoiceGroup.vue'

const props = defineProps({ config: { type: Object, required: true }, options: { type: Object, default: () => ({}) }, busy: Boolean })
const emit = defineEmits(['close', 'update', 'reset'])
const groups = [
  ['Select Skin', 'skin', false],
  ['Color Scheme', 'color_scheme', true],
  ['Topbar Color', 'topbar_color', true],
  ['Sidenav Color', 'sidenav_color', true],
  ['Sidebar Size', 'sidenav_size', true],
  ['Layout Width', 'layout_width', true],
  ['Layout Direction', 'direction', true],
  ['Layout Position', 'layout_position', true],
  ['Navigation Orientation', 'orientation', true],
  ['Sidebar User Info', 'sidebar_user', true],
]
function update(setting, value) { emit('update', { ...props.config, [setting]: value }) }
</script>

<template>
  <div class="customizer-layer" role="presentation" @click.self="$emit('close')">
    <aside class="customizer-drawer" role="dialog" aria-modal="true" aria-labelledby="customizer-title">
      <header><div><h2 id="customizer-title">Admin Customizer</h2><p>Configure the Inspinia layout, styles, and workspace preferences.</p></div><button aria-label="Close customizer" @click="$emit('close')">&times;</button></header>
      <div class="customizer-body">
        <CustomizerChoiceGroup v-for="group in groups" :key="group[1]" :title="group[0]" :setting="group[1]" :values="options[group[1]] || []" :selected="config[group[1]]" :compact="group[2]" :busy="busy" @select="update" />
        <section class="scope-note"><strong>Saved per workspace</strong><p>These choices apply to this user in the current company only.</p></section>
      </div>
      <footer><button class="reset" :disabled="busy" @click="$emit('reset')">Reset</button><button class="close" @click="$emit('close')">Close</button></footer>
    </aside>
  </div>
</template>

<style scoped>
.customizer-layer{position:fixed;inset:0;z-index:180;background:#17202b66;backdrop-filter:blur(1px)}.customizer-drawer{position:absolute;inset:0 0 0 auto;display:flex;width:min(455px,94vw);flex-direction:column;background:#fff;color:#313a46;box-shadow:-16px 0 45px #17202b2b;animation:drawer-in .2s ease-out}header{position:relative;display:flex;justify-content:space-between;padding:24px;background:linear-gradient(135deg,#1ab394,#3bc4aa);color:#fff;overflow:hidden}header:after{content:"";position:absolute;right:-45px;bottom:-70px;width:180px;height:180px;border:34px solid #ffffff0d;border-radius:50%}h2{margin:0 0 7px;font-size:1rem;text-transform:uppercase}header p{max-width:310px;margin:0;color:#e4fff8;font-size:.79rem;font-style:italic;line-height:1.45}header button{position:relative;z-index:1;width:34px;height:34px;border:0;border-radius:50%;background:#ffffff26;color:#fff;font-size:1.5rem;cursor:pointer}.customizer-body{flex:1;overflow-y:auto}.scope-note{margin:20px 22px;padding:14px;border:1px solid #dcece7;border-radius:7px;background:#f4faf8}.scope-note strong{font-size:.78rem;color:#27725e}.scope-note p{margin:5px 0 0;color:#718078;font-size:.72rem;line-height:1.45}footer{display:flex;gap:10px;padding:16px 22px;border-top:1px solid #e7e9eb;background:#fff}footer button{flex:1;padding:11px;border-radius:5px;font-weight:700;cursor:pointer}.reset{border:1px solid #ed5565;background:#ed5565;color:#fff}.close{border:1px solid #1ab394;background:#1ab394;color:#fff}button:disabled{opacity:.55;cursor:not-allowed}@keyframes drawer-in{from{transform:translateX(100%)}to{transform:translateX(0)}}
</style>
