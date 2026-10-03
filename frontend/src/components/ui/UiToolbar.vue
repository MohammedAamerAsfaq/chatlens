<template><div class="ui-toolbar"><div class="ui-toolbar__primary"><slot /></div><div v-if="$slots.actions" class="ui-toolbar__actions"><slot name="actions" /></div></div></template>
