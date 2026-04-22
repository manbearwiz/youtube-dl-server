<script setup>
import { getAPIUrl } from '../utils';
import { map, capitalize } from 'lodash'
import { inject } from 'vue'
import QuickDownloadModal from './QuickDownloadModal.vue'

const theme = inject('theme')
const toggleTheme = inject('toggleTheme')
</script>
<script>
export default {
  data: () => ({
    stats: {},
    server_info: {},
  }),
  mounted() {
    this.fetchStats();
    this.server_info = inject('serverInfo');
  },
  computed: {
    prettyModule: function () {
      if (!this.server_info.ydl_module_name) {
        return ''
      }
      const parts = this.server_info.ydl_module_name.split('-')
      return [capitalize(parts[0]), ...map(parts.slice(1), s => s.toUpperCase())].join('')
    }
  },
  methods: {
    async fetchStats() {
      const url = getAPIUrl('api/downloads/stats', import.meta.env);
      this.stats = (await (await fetch(url)).json()).stats || {};
      setTimeout(() => {
        this.fetchStats()
      }, 5000)
    },
  }
}
</script>
<template>
  <header>
    <nav class="navbar navbar-expand-md navbar-dark">
      <div class="container-fluid">
        <router-link to="/" class="navbar-brand">{{ prettyModule }}</router-link>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsingNavbar"
          aria-controls="collapsingNavbar" aria-expanded="false" aria-label="Toggle navigation">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="collapsingNavbar">
          <ul class="navbar-nav me-auto mb-2 mb-md-0">
            <li class="nav-item">
              <router-link to="/" class="nav-link" exact-active-class="router-link-active">Home</router-link>
            </li>
            <li class="nav-item">
              <router-link to="/logs" class="nav-link">Logs</router-link>
            </li>
            <li class="nav-item">
              <router-link to="/finished" class="nav-link">Finished</router-link>
            </li>
          </ul>
          <div class="stats-bar d-flex align-items-center gap-2 flex-wrap">
            <router-link to="/logs?status=PENDING">
              <span v-if="stats.queue === stats.pending" title="Pending"
                id='queue_pending_size' class="badge bg-secondary">{{ stats.queue }}</span>
              <span v-else title="Pending" id='queue_pending_size'
                class="badge bg-secondary">{{ stats.queue }} | {{ stats.pending }}</span>
            </router-link>
            <router-link to="/logs?status=RUNNING">
              <span title="Running / Total Workers" id='running_size'
                class="badge bg-info">{{ stats.running }}/{{ server_info.download_workers_count }}</span>
            </router-link>
            <router-link to="/logs?status=COMPLETED">
              <span title="Completed" id='completed_size'
                class="badge bg-success">{{ stats.completed }}</span>
            </router-link>
            <router-link to="/logs?status=ABORTED">
              <span title="Aborted" id='aborted_size'
                class="badge bg-warning">{{ stats.aborted }}</span>
            </router-link>
            <router-link to="/logs?status=FAILED">
              <span title="Failed" id='failed_size'
                class="badge bg-danger">{{ stats.failed }}</span>
            </router-link>
          </div>
          <QuickDownloadModal />
          <button class="btn-theme-toggle ms-2" @click="toggleTheme" :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'">
            <svg v-if="theme === 'dark'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6m0 1a4 4 0 1 0 0-8 4 4 0 0 0 0 8M8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0m0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13m8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5M3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8m10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0m-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0m9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707M3.757 4.464a.5.5 0 0 1-.707 0L1.636 3.05a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707"/>
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M6 .278a.77.77 0 0 1 .08.858 7.2 7.2 0 0 0-.878 3.46c0 4.021 3.278 7.277 7.318 7.277q.792-.001 1.533-.16a.79.79 0 0 1 .81.316.73.73 0 0 1-.031.893A8.35 8.35 0 0 1 8.344 16C3.734 16 0 12.286 0 7.71 0 4.266 2.114 1.312 5.124.06A.75.75 0 0 1 6 .278"/>
            </svg>
          </button>
        </div>
      </div>
    </nav>
  </header>
</template>
