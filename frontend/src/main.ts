import './assets/main.css'
import './assets/theme-tokens.css'
import './assets/ui-system.css'
import './assets/ui-controls.css'
import './assets/inspinia-legacy-bridge.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
