import './assets/main.css'
import './assets/theme-tokens.css'
import './assets/ui-system.css'
import './assets/ui-controls.css'
import './assets/ui-datatable.css'
import './assets/inspinia-legacy-bridge.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { ensureTeleportHost } from './bootstrap/teleportHost'
import { installUiDataTableObserver, uiDataTable } from './directives/uiDataTable'
import router from './router'

ensureTeleportHost()

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.directive('ui-data-table', uiDataTable)

app.mount('#app')
installUiDataTableObserver()
