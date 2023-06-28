<script setup>
import { orderBy } from 'lodash'
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
    sortBy: 'last_update',
    sortOrder: 'desc',
  }),
  mounted() {
    this.mounted = true;
    this.fetchLogs();
  },
  unmounted() {
    this.mounted = false;
  },
  computed: {
    orderedLogs: function () {
      if (this.sortBy === 'last_update') {
        return orderBy(this.logs, e => {
          return new Date(e.last_update)
        }, this.sortOrder)
      }
      return orderBy(this.logs, this.sortBy, this.sortOrder)
    }
  },
  methods: {
    abortDownload(job_id) {
      const url = getAPIUrl(`api/jobs/${job_id}/stop`, import.meta.env);
      fetch(url, {
        method: 'POST'
      })
      this.fetchLogs(true)
    },
    retryDownload(job_id) {
      console.log(job_id)
      const apiurl = getAPIUrl(`api/jobs/${job_id}/retry`, import.meta.env);
      fetch(apiurl, {
        method: 'POST'
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
        <div class="table-responsive">
          <table class="col-md-16 table table-stripped table-md table-dark">
            <thead>
              <tr>
                <th class="col-md-1">Last update
                  <a :class="sortOrder === 'asc' && sortBy === 'last_update' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'last_update'; sortOrder = 'asc'">&uarr;</a>
                  <a :class="sortOrder === 'desc' && sortBy === 'last_update' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'last_update'; sortOrder = 'desc'">&darr;</a>
                </th>
                <th class="col-md-3">Name
                  <a :class="sortOrder === 'asc' && sortBy === 'name' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#" @click.prevent="sortBy = 'name'; sortOrder = 'asc'">&uarr;</a>
                  <a :class="sortOrder === 'desc' && sortBy === 'name' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'name'; sortOrder = 'desc'">&darr;</a>
                </th>
                <th class="col-md-1">Format
                  <a :class="sortOrder === 'asc' && sortBy === 'format' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'format'; sortOrder = 'asc'">&uarr;</a>
                  <a :class="sortOrder === 'desc' && sortBy === 'format' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'format'; sortOrder = 'desc'">&darr;</a>
                </th>
                <th class="col-md-1">Status
                  <a :class="sortOrder === 'asc' && sortBy === 'status' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'status'; sortOrder = 'asc'">&uarr;</a>
                  <a :class="sortOrder === 'desc' && sortBy === 'status' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'status'; sortOrder = 'desc'">&darr;</a>
                </th>
                <th v-if="showLogDetails" class="col-md-6">Log</th>
              </tr>
            </thead>
            <tbody id="job_logs">
              <tr v-for="log in orderedLogs" :key="log.id">
                <td>{{ log.last_update }}</td>
                <td>{{ log.name }}</td>
                <td>{{ log.format }}</td>
                <td v-if="log.status == 'Failed' || log.status == 'Aborted'">
                  <span :class=statusToTrClass[log.status]>
                    <a role="button" aria-label="Retry" @click.prevent="retryDownload(log.id)">{{
                      log.status }} / Retry</a>
                  </span>
                </td>
                <td v-else-if="log.status == 'Running' || log.status == 'Pending'">
                  <span :class=statusToTrClass[log.status]>
                    {{ log.status }} <a role="button" aria-label="Abort"
                      @click.prevent="abortDownload(log.id)">&times;</a>
                  </span>
                </td>
                <td v-else>
                  <span :class=statusToTrClass[log.status]>
                    {{ log.status }}
                  </span>
                </td>
                <td style="text-align: left;" v-if="showLogDetails">{{ log.log }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div></template>
