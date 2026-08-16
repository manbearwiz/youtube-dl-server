<script setup>
import { orderBy, capitalize } from 'lodash'
import { Modal } from 'bootstrap'
import { getAPIUrl, formatCountdown, saveConfig, getConfig } from '../utils';
</script>
<script>
export default {
  data: () => ({
    logs: [],
    showLogDetails: true,
    mounted: false,
    statusToTrClass: {
      Pending: 'badge bg-secondary',
      Failed: 'badge bg-danger',
      Aborted: 'badge bg-warning',
      Running: 'badge bg-info',
      Completed: 'badge bg-success',
      Scheduled: 'badge bg-primary'
    },
    sortBy: 'last_update',
    sortOrder: 'desc',
    currentLogDetailsModal: null,
    currentLogDetailId: null,
    status: null,
    commandCopied: false,
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
    if (this.$route.query.job) {
      this.showCurrentLogDetails(Number(this.$route.query.job));
    }
  },
  unmounted() {
    this.mounted = false;
  },
  computed: {
    getLogById: function () {
      return this.logs.find(log => log.id === this.currentLogDetailId);
    },
    currentCommand: function () {
      const line = this.getLogById?.log?.split('\n').find(l => l.startsWith('[cmd] '));
      return line?.slice(6);
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
    toggleSort(field) {
      if (this.sortBy === field) {
        this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
      } else {
        this.sortBy = field;
        this.sortOrder = 'desc';
      }
    },
    getFormatBadgeClass(format) {
      return format?.startsWith('profile/') ? 'badge bg-warning me-1' : 'badge bg-success me-1'
    },
    showCurrentLogDetails(logId) {
      this.currentLogDetailId = logId
      this.commandCopied = false;
      this.currentLogDetailsModal.show();
    },
    copyCommand() {
      const text = this.currentCommand;
      if (!text) return;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      this.commandCopied = true;
      setTimeout(() => { this.commandCopied = false }, 1500);
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
    <div class="container-fluid d-flex flex-column text-center">
      <div class="container-fluid flex-grow-1">
        <h1 class="display-4">Jobs History</h1>
        <div class="d-flex justify-content-center gap-2 flex-wrap mb-3">
          <div class="btn-group" role="toolbar">
            <button v-if="showLogDetails" class="btn btn-outline-secondary col-hide-mobile"
              @click="showLogDetails = false; saveConfig('showLogDetails', false)">Hide logs</button>
            <button v-else class="btn btn-outline-secondary col-hide-mobile"
              @click="showLogDetails = true; saveConfig('showLogDetails', true)">Show logs</button>
            <button class="btn btn-outline-secondary" @click="fetchLogs">Refresh</button>
            <button class="btn btn-outline-danger" @click="purgeLogs">Purge</button>
          </div>
          <div class="dropdown">
            <a class="btn btn-outline-secondary dropdown-toggle" href="#" role="button" id="statusFilterDropDown" data-bs-toggle="dropdown" aria-expanded="false">
              Status {{ ['COMPLETED', 'FAILED', 'PENDING', 'RUNNING', 'ABORTED', 'SCHEDULED'].includes(status) ? `(${capitalize(status)})` : '(All)' }}
            </a>
            <ul class="dropdown-menu" aria-labelledby="statusFilterDropDown">
              <li><router-link class="dropdown-item" to="/logs">All</router-link></li>
              <li><router-link class="dropdown-item" to="/logs?status=COMPLETED">Completed</router-link></li>
              <li><router-link class="dropdown-item" to="/logs?status=FAILED">Failed</router-link></li>
              <li><router-link class="dropdown-item" to="/logs?status=PENDING">Pending</router-link></li>
              <li><router-link class="dropdown-item" to="/logs?status=RUNNING">Running</router-link></li>
              <li><router-link class="dropdown-item" to="/logs?status=ABORTED">Aborted</router-link></li>
              <li><router-link class="dropdown-item" to="/logs?status=SCHEDULED">Scheduled</router-link></li>
            </ul>
          </div>
        </div>
        <div class="table-responsive">
          <table class="table table-striped table-hover">
            <thead>
              <tr>
                <th class="sortable-header col-hide-mobile" @click="toggleSort('last_update')">
                  Last update
                  <svg v-if="sortBy === 'last_update'" class="sort-chevron" :class="{ flipped: sortOrder === 'asc' }" xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z"/>
                  </svg>
                </th>
                <th class="sortable-header" @click="toggleSort('name')">
                  Name
                  <svg v-if="sortBy === 'name'" class="sort-chevron" :class="{ flipped: sortOrder === 'asc' }" xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z"/>
                  </svg>
                </th>
                <th class="sortable-header" @click="toggleSort('format')">
                  Format
                  <svg v-if="sortBy === 'format'" class="sort-chevron" :class="{ flipped: sortOrder === 'asc' }" xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z"/>
                  </svg>
                </th>
                <th class="sortable-header" @click="toggleSort('status')">
                  Status
                  <svg v-if="sortBy === 'status'" class="sort-chevron" :class="{ flipped: sortOrder === 'asc' }" xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z"/>
                  </svg>
                </th>
                <th class="col-hide-mobile" v-if="showLogDetails">Log</th>
              </tr>
            </thead>
            <tbody id="job_logs">
              <tr v-if="logs.length === 0">
                <td :colspan="showLogDetails ? 5 : 4">No {{ status == null ? '' : status.toLowerCase() + ' ' }}jobs found</td>
              </tr>
              <tr @click="showCurrentLogDetails(log.id)" v-for="log in orderedLogs" :key="log.id" style="cursor: pointer;">
                <td class="col-hide-mobile">{{ log.last_update }}</td>
                <td class="col-name">{{ log.name }}</td>
                <td><span v-for='fmt in log.format?.split(",")' :class=getFormatBadgeClass(fmt)>{{ fmt }}</span></td>
                <td v-if="log.status == 'Failed' || log.status == 'Aborted'">
                  <span :class=statusToTrClass[log.status] class="status-action" @click.stop="retryDownload(log.id)">
                    {{ log.status }} / Retry
                  </span>
                </td>
                <td v-else-if="log.status == 'Running' || log.status == 'Pending'">
                  <span :class=statusToTrClass[log.status] class="status-action" @click.stop="abortDownload(log.id)">
                    {{ log.status }} &times;
                  </span>
                </td>
                <td v-else-if="log.status == 'Scheduled'">
                  <span :class=statusToTrClass[log.status] class="status-action" @click.stop="abortDownload(log.id)">
                    {{ log.status }} {{ formatCountdown(log.scheduled_at) }} &times;
                  </span>
                </td>
                <td v-else>
                  <span :class=statusToTrClass[log.status]>
                    {{ log.status }}
                  </span>
                </td>
                <td class="text-start col-hide-mobile" v-if="showLogDetails">{{ log.log }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="modal fade" id="currentLogDetailsModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog modal-xl" id='currentLogDetailDialog' style="text-align: left">
            <div class="modal-content">
              <div class="modal-header">
                <span :class=statusToTrClass[getLogById?.status]>{{ getLogById?.status }}</span>&nbsp;
                <h1 class="modal-title fs-5" id="currentLogDetailId">{{ getLogById?.name || '' }}</h1>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body" id="currentLogDetailContent">
                <div v-if="currentCommand" class="mb-3">
                  <div class="d-flex align-items-center justify-content-between mb-1">
                    <span class="text-secondary small">Command</span>
                    <button type="button" class="btn btn-sm btn-outline-secondary" @click="copyCommand">
                      {{ commandCopied ? 'Copied' : 'Copy' }}
                    </button>
                  </div>
                  <code class="command-output">{{ currentCommand }}</code>
                </div>
                <pre v-if="currentLogDetailId" class="log-output">{{ getLogById?.log }}</pre>
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
                <div v-else-if="getLogById?.status == 'Scheduled'" class="d-flex gap-2">
                  <button class="btn btn-primary" role="button" aria-label="Download now" data-bs-dismiss="modal"
                    @click="retryDownload(getLogById?.id)">Download now</button>
                  <button class="btn btn-outline-primary" role="button" aria-label="Abort" data-bs-dismiss="modal"
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
