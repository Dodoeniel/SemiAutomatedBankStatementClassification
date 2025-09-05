import { createApp } from 'vue'
import App from './App.vue'


import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import '@mdi/font/css/materialdesignicons.css' // Icons optional aber empfohlen


const vuetify = createVuetify({
  components,
  directives,
})

createApp(App).use(vuetify).mount('#app')