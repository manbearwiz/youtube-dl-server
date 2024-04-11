<script setup>
import { orderBy, capitalize } from 'lodash'
import { Modal } from 'bootstrap'
import { getAPIUrl, saveConfig, getConfig } from '../utils';
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
    currentLogDetailsModal: null,
    currentLogDetailId: null,
    status: null,
  }),
  watch: {
    '$route'() {
      this.status = this.$route.query.status;
      this.fetchLogs(true);
    }
  },
  mounted() {
    this.currentLogDetailsModal = new Modal('#currentLogDetailsModal');
    this.showLogDetails = getConfig('showLogDetails', 'true') === 'true';
    this.mounted = true;
    this.status = this.$route.query.status;
    this.fetchLogs();
  },
  unmounted() {
    this.mounted = false;
  },
  computed: {
    getLogById: function () {
      return this.logs.find(log => log.id === this.currentLogDetailId);
    },
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
    getFormatBadgeClass(format) {
      return format.startsWith('profile/') ? 'badge bg-warning me-1' : 'badge bg-success me-1'
    },
    showCurrentLogDetails(logId) {
      this.currentLogDetailId = logId
      this.currentLogDetailsModal.show();
    },
    abortDownload(job_id) {
      const url = getAPIUrl(`api/jobs/${job_id}/stop`, import.meta.env);
      fetch(url, {
        method: 'POST'
      })
      this.fetchLogs(true)
    },
    retryDownload(job_id) {
      const apiurl = getAPIUrl(`api/jobs/${job_id}/retry`, import.meta.env);
      fetch(apiurl, {
        method: 'POST'
      }).then(() => {
        this.fetchLogs(true);
      })
    },
    deleteLog(job_id) {
      const apiurl = getAPIUrl(`api/jobs/${job_id}`, import.meta.env);
      fetch(apiurl, {
        method: 'DELETE'
      }).then(() => {
        this.fetchLogs(true);
      })
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
      const url = getAPIUrl(`api/downloads?${this.status ? 'status=' + this.status : ''}`, import.meta.env);
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
        <button v-if="showLogDetails" class="btn btn-dark"
          @click="showLogDetails = false; saveConfig('showLogDetails', false)">Hide logs</button>
        <button v-else class="btn btn-dark" @click="showLogDetails = true; saveConfig('showLogDetails', true)">Show
          logs</button>
        <button class="btn btn-dark" @click="fetchLogs">Refresh</button>
        <button class="btn btn-dark" @click="purgeLogs">Purge logs</button>
          <a class="btn btn-dark dropdown-toggle" href="#" role="button" id="statusFilterDropDown" data-bs-toggle="dropdown" aria-expanded="false">
            Status {{ ['COMPLETED', 'FAILED', 'PENDING', 'RUNNING', 'ABORTED'].includes(status) ? `(${capitalize(status)})` : '(All)' }}
          </a>
          <ul class="dropdown-menu" aria-labelledby="statusFilterDropDown">
            <li><router-link class="dropdown-item" to="/logs">All</router-link></li>
            <li><router-link class="dropdown-item" to="/logs?status=COMPLETED">Completed</router-link></li>
            <li><router-link class="dropdown-item" to="/logs?status=FAILED">Failed</router-link></li>
            <li><router-link class="dropdown-item" to="/logs?status=PENDING">Pending</router-link></li>
            <li><router-link class="dropdown-item" to="/logs?status=RUNNING">Running</router-link></li>
            <li><router-link class="dropdown-item" to="/logs?status=ABORTED">Aborted</router-link></li>
          </ul>
        <br />
        <div class="table-responsive">
          <table class="col-md-16 table table-stripped table-md table-dark">
            <thead>
              <tr>
                <th class="col-md-2">Last update
                  <a :class="sortOrder === 'asc' && sortBy === 'last_update' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'last_update'; sortOrder = 'asc'">&uarr;</a>
                  <a :class="sortOrder === 'desc' && sortBy === 'last_update' ? 'text-light' : 'text-muted'"
                    style="text-decoration: none;" href="#"
                    @click.prevent="sortBy = 'last_update'; sortOrder = 'desc'">&darr;</a>
                </th>
                <th class="col-md-2">Name
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
              <tr v-if="logs.length === 0">
                <td colspan="4">No {{ status == null ? '' : status.toLowerCase() + ' ' }}jobs found</td>
              </tr>
              <tr @click="showCurrentLogDetails(log.id)" v-for="log in orderedLogs" :key="log.id">
                <td >{{ log.last_update }}</td>
                <td>{{ log.name }}</td>
                <td><span v-for='fmt in log.format.split(",")' :class=getFormatBadgeClass(fmt)>{{ fmt }}</span></td>
                <td v-if="log.status == 'Failed' || log.status == 'Aborted'">
                  <span :class=statusToTrClass[log.status] @click.stop="retryDownload(log.id)">
                    <a role="button" aria-label="Retry">{{
                      log.status }} / Retry</a>
                  </span>
                </td>
                <td v-else-if="log.status == 'Running' || log.status == 'Pending'">
                  <span :class=statusToTrClass[log.status] @click.stop="abortDownload(log.id)">
                    {{ log.status }} <a role="button" aria-label="Abort"
                     >&times;</a>
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

        <div class="modal fade text-dark" id="currentLogDetailsModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog modal-xl" id='currentLogDetailDialog' style="text-align: left">
            <div class="modal-content">
              <div class="modal-header">
                <h1 class="modal-title fs-5" id="currentLogDetailId">{{ getLogById?.name || '' }}</h1>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body text-left" id="currentLogDetailContent">
                <p v-if="currentLogDetailId" style="white-space: pre-wrap">
                  {{ getLogById?.log }}
                </p>
                <div v-else class="spinner-border" role="status">
                  <span class="visually-hidden">Loading...</span>
                </div>
              </div>
              <div class="modal-footer">
                <div v-if="getLogById?.status == 'Failed' || getLogById?.status == 'Aborted'">
                  <button class="btn btn-primary" role="button" aria-label="Retry" data-bs-dismiss="modal"
                    @click="retryDownload(getLogById?.id)">Retry</button>
                </div>
                <div v-else-if="getLogById?.status == 'Running' || getLogById?.status == 'Pending'">
                  <button class="btn btn-primary" role="button" aria-label="Abort" data-bs-dismiss="modal"
                    @click="abortDownload(getLogById?.id)">Abort</button>
                </div>
                <button type="button" class="btn btn-danger" data-bs-dismiss="modal" @click="deleteLog(getLogById?.id)">Delete log</button>
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>
