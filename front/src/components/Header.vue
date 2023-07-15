<script setup>
import { getAPIUrl } from '../utils';
</script>
<script>
export default {
  data: () => ({
    stats: {},
    server_info: {},
  }),
  mounted() {
    this.fetchStats();
    this.fetchServerInfo();
  },

  methods: {
    async fetchServerInfo() {
      const url = getAPIUrl('api/info', import.meta.env);
      this.server_info = await (await fetch(url)).json();
    },
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
        <router-link to="/" class="navbar-brand">YoutubeDL</router-link>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsingNavbar"
          aria-controls="collapsingNavbar" aria-expanded="false" aria-label="Toggle navigation">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="collapsingNavbar">
          <ul class="navbar-nav me-auto mb-2 mb-md-0">
            <li class="nav-item">
              <router-link to="/logs" class="nav-link">Logs</router-link>
            </li>
            <li class="nav-item">
              <router-link to="/finished" class="nav-link">Finished</router-link>
            </li>
          </ul>
          <div class="d-flex">
            <ul class="navbar-nav ml-auto">
              <li class="nav-item">
                <router-link to="/logs" class="navbar-text nav-link">
                  Stats:
                  <span v-if="stats.queue === stats.pending" data-toggle="tooltip" data-placement="bottom" title="Pending"
                    id='queue_pending_size' class="badge bg-secondary">{{ stats.queue }}</span>
                  <span v-else data-toggle="tooltip" data-placement="bottom" title="Pending" id='queue_pending_size'
                    class="badge bg-secondary">{{ stats.queue }} | {{ stats.pending }}</span>
                  <span data-toggle="tooltip" data-placement="bottom" title="Running / Total Workers" id='running_size'
                    class="badge bg-info">{{ stats.running }}/{{ server_info.download_workers_count }}</span>
                  <span data-toggle="tooltip" data-placement="bottom" title="Completed" id='completed_size'
                    class="badge bg-success">{{ stats.completed }}</span>
                  <span data-toggle="tooltip" data-placement="bottom" title="Failed" id='failed_size'
                    class="badge bg-danger">{{ stats.failed }}</span>
                </router-link>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </nav>
  </header>
</template>
