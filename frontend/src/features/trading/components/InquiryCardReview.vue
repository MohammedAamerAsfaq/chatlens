<script setup>
defineProps({
  rating: { type: Number, default: 5 },
  incorrectOpen: { type: Boolean, default: false },
  incorrectReason: { type: String, default: '' },
})
defineEmits(['rate', 'update:incorrectReason', 'submit', 'cancel'])
</script>

<template>
  <div class="inquiry-review">
    <div class="rating"><span>Match quality:</span><button v-for="number in 5" :key="number" type="button" :class="{ active: number === rating, low: number <= 2, mid: number === 3 }" :title="`Rate ${number}/5 - ${number === 1 ? 'worst' : number === 5 ? 'exact' : ''}`" @click="$emit('rate', number)">{{ number }}</button></div>
    <div v-if="incorrectOpen" class="incorrect-form">
      <input :value="incorrectReason" placeholder="What's incorrect about this match?" @input="$emit('update:incorrectReason', $event.target.value)" @keydown.enter="$emit('submit')" />
      <button type="button" class="save" @click="$emit('submit')">Save</button><button type="button" @click="$emit('cancel')">Cancel</button>
    </div>
  </div>
</template>

<style scoped>
.rating{display:flex;align-items:center;gap:4px;margin-top:8px}.rating span{margin-right:3px;color:var(--ui-text-muted);font-size:.68rem}.rating button{width:22px;height:22px;padding:0;border:1px solid var(--ui-border-strong);border-radius:50%;background:var(--ui-surface);color:var(--ui-text-muted);font:700 .68rem var(--ui-font-sans);cursor:pointer}.rating button.active{border-color:var(--ui-success);background:var(--ui-success);color:var(--ui-on-primary)}.rating button.low.active{border-color:var(--ui-danger);background:var(--ui-danger)}.rating button.mid.active{border-color:var(--ui-warning);background:var(--ui-warning)}.incorrect-form{display:flex;align-items:center;gap:6px;margin-top:6px}.incorrect-form input{min-width:0;flex:1;padding:4px 8px;border:1px solid color-mix(in srgb,var(--ui-danger) 40%,white);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text);font:500 .78rem var(--ui-font-sans)}.incorrect-form button{padding:4px 10px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text);cursor:pointer}.incorrect-form .save{border-color:var(--ui-primary);background:var(--ui-primary);color:var(--ui-on-primary)}
</style>
