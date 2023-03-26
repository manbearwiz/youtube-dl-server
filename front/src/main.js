import { createApp } from 'vue'
import App from './App.vue'
import { createRouter, createWebHashHistory } from 'vue-router';

// import 'bootstrap-vue/dist/bootstrap-vue.css';
import 'bootstrap/dist/css/bootstrap.css';

import './assets/style.css'
import Logs from './components/Logs.vue'
import Home from './components/Home.vue'
import Finished from './components/Finished.vue'

const routes = [
  { path: '/', component: Home },
  { path: '/logs', component: Logs },
  { path: '/finished', component: Finished },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})
const app = createApp(App);
app.use(router);
app.mount('#app');