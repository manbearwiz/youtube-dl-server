<script setup>
import { getAPIUrl } from '../utils';
</script>
<script>
export default {
  data: () => ({
    logs: [],
    showLogDetails: true,
    mounted: false,
    statusToTrClass: {
      Pending: 'badge',
      Failed: 'badge bg-danger',
      Aborted: 'badge bg-warning',
      Running: 'badge bg-info',
      Completed: 'badge bg-success'
    },
  }),
  mounted() {
    this.mounted = true;
    this.fetchLogs();
  },
  unmounted() {
    this.mounted = false;
  },

  methods: {
    abortDownload(job_id) {
      const url = getAPIUrl(`api/jobs/${job_id}/stop`, import.meta.env);
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      this.fetchLogs(true)
    },
    retryDownload(url, format) {
      console.log(url, format)
      const apiurl = getAPIUrl(`api/downloads`, import.meta.env);
      fetch(apiurl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url,
          format
        })
      })
      this.fetchLogs(true)
    },
    purgeLogs() {
      const url = getAPIUrl(`api/downloads`, import.meta.env);
      fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      this.fetchLogs(true)
    },
    async fetchLogs(once = false) {
      const url = getAPIUrl(`api/downloads`, import.meta.env);
      this.logs = await (await fetch(url)).json()
      if (!once && this.mounted) {
        setTimeout(() => {
          this.fetchLogs()
        }, 5000)
      }
    },
  }
}
</script>
<template>
  <div class="content">
    <div class="container-fluid d-flex flex-column text-light text-center">
      <div class="container-fluid flex-grow-1">
        <h1 class="display-4">Jobs History</h1>
        <button v-if="showLogDetails" class="btn btn-dark" @click="showLogDetails = false">Hide logs</button>
        <button v-else class="btn btn-dark" @click="showLogDetails = true">Show logs</button>
        <button class="btn btn-dark" @click="fetchLogs">Refresh</button>
        <button class="btn btn-dark" @click="purgeLogs">Purge logs</button>
        <br />
        <table class="col-md-16 table table-stripped table-md table-dark">
          <thead>
            <tr>
              <th>Last update</th>
              <th>Name</th>
              <th>Format</th>
              <th>Status</th>
              <th v-if="showLogDetails">Log</th>
            </tr>
          </thead>
          <tbody id="job_logs">
            <tr v-for="log in logs" :key="log.id">
              <td>{{ log.last_update }}</td>
              <td>{{ log.name }}</td>
              <td>{{ log.format }}</td>
              <td v-if="log.status == 'Failed' || log.status == 'Aborted'">
                <span :class=statusToTrClass[log.status]>
                  <a role="button" aria-label="Retry" @click.prevent="retryDownload(log.url, log.format)">{{
                    log.status }} / Retry</a>
                </span>
              </td>
              <td v-else-if="log.status == 'Running' || log.status == 'Pending'">
                <span :class=statusToTrClass[log.status]>
                  {{ log.status }} <a role="button" aria-label="Abort" @click.prevent="abortDownload(log.id)">&times;</a>
                </span>
              </td>
              <td v-else>
                <span :class=statusToTrClass[log.status]>
                  {{ log.status }}
                </span>
              </td>
              <td style="white-space: pre; text-align: left;" v-if="showLogDetails">{{ log.log }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
