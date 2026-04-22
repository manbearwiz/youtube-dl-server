<script setup>
import { get, isEmpty } from 'lodash'
import { Modal, Collapse } from 'bootstrap'
import { getAPIUrl, saveConfig, getConfig } from '../utils';
</script>

<script>
export default {
  props: {
    syncRouteFormat: {
      type: Boolean,
      default: true,
    },
    autofocus: {
      type: Boolean,
      default: true,
    },
  },
  data: () => ({
    extractors: [],
    formats: [],
    extractorsModal: null,
    metadataModal: null,
    default_format: null,
    metadata_list: null,
    loading: false,
    extractorsFilter: '',
    extractorsPageSize: 200,
    intersectionObserver: null,
    forceGenericExtractor: false,
    downloadName: '',
    showAdvancedOptions: false,
    toasts: [],
    advancedCollapse: null,
  }),
  mounted() {
    this.extractorsModal = new Modal(this.$refs.extractorsModalEl);
    this.metadataModal = new Modal(this.$refs.metadataModalEl);
    this.advancedCollapse = new Collapse(this.$refs.advancedCollapseEl, { toggle: false });
    this.fetchExtractors();
    this.fetchAvailableFormats();
    this.showAdvancedOptions = getConfig('showAdvancedOptions', 'false') === 'true';
    if (this.showAdvancedOptions) {
      this.$nextTick(() => this.advancedCollapse.show());
    }
    if (this.autofocus) {
      this.$refs.urlBox.focus();
    }
  },
  beforeUnmount() {
    if (this.intersectionObserver) this.intersectionObserver.disconnect();
  },
  computed: {
    uid() {
      return this.$.uid;
    },
    filteredExtractors() {
      return this.extractorsFilter
        ? this.extractors.filter(e => e.toLowerCase().includes(this.extractorsFilter.toLowerCase()))
        : this.extractors;
    },
    visibleExtractors() {
      if (this.extractorsFilter) return this.filteredExtractors;
      return this.filteredExtractors.slice(0, this.extractorsPageSize);
    }
  },
  watch: {
    '$route.query': {
      handler: 'loadUrlParams',
      immediate: true
    },
    extractorsFilter() {
      this.extractorsPageSize = 200;
    },
    extractorsPageSize() {
      this.$nextTick(() => this.setupScrollObserver());
    },
  },
  methods: {
    focus() {
      this.$refs.urlBox.focus();
    },
    prettySize(size_b) {
      if (size_b == null) return undefined;
      var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
      var i = 0;
      for (i = 0; i < sizes.length; i++) {
        if (size_b < 1024) { i++; break; }
        size_b = size_b / 1024;
      }
      return Number((size_b).toFixed(2)) + ' ' + sizes[i - 1];
    },
    loadUrlParams() {
      if (this.syncRouteFormat && this.$route && this.$route.query.format) {
        this.default_format = this.$route.query.format;
      }
    },
    updateUrlParameterFormat(format) {
      if (!this.syncRouteFormat) return;
      const currentQuery = { ...this.$route.query };
      currentQuery.format = format;
      this.$router.push({ path: this.$route.path, query: currentQuery });
    },
    showToast(message, success) {
      const id = Date.now() + Math.random();
      this.toasts.push({ id, message, success });
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id);
      }, 5000);
    },
    showExtractorsModal() {
      this.extractorsModal.show();
      this.$nextTick(() => this.setupScrollObserver());
    },
    showMetadataModal() {
      this.metadataModal.show();
    },
    async fetchExtractors() {
      const url = getAPIUrl('api/extractors', import.meta.env);
      this.extractors = await (await fetch(url)).json();
    },
    async fetchAvailableFormats() {
      const url = getAPIUrl('api/formats', import.meta.env);
      this.formats = await (await fetch(url)).json();
      this.loadUrlParams();
      if (!this.default_format) {
        this.default_format = this.formats.ydl_default_format;
      }
    },
    async inspectVideo() {
      this.loading = true;
      const url = getAPIUrl('api/metadata', import.meta.env);
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          urls: this.$refs.urlBox.value.trim().split('\n').join(' ').split(' '),
          force_generic_extractor: this.forceGenericExtractor,
          ...(this.downloadName && { output: this.downloadName })
        })
      })
        .then(response => {
          if (response.status == 200) return response.json();
          throw new Error(response.statusText);
        })
        .then(data => {
          this.metadata_list = data;
          this.showMetadataModal();
        })
        .catch((error) => {
          console.error(error);
          this.showToast('Could not gather metadata for this video.', false);
        })
        .finally(() => { this.loading = false; });
    },
    getParamsFromSelection(format) {
      return {
        format: format.resolution == "audio only" ? this.$refs.selectedFormat.value : format.format_id,
        audio_format: format.resolution == "audio only" ? format.format_id : null
      };
    },
    async queueVideo(videoUrl, params) {
      const url = getAPIUrl('api/downloads', import.meta.env);
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls: [videoUrl], ...params })
      })
        .then(response => {
          if (response.status == 200) return response.json();
          throw new Error(response.statusText);
        })
        .then(data => {
          this.showToast(data.success ? (videoUrl + " added to the queue.") : data.error, data.success);
          this.$refs.urlBox.value = '';
        })
        .catch((error) => {
          console.error(error);
          this.showToast('Could not add the url to the queue.', false);
        });
    },
    async submitVideo() {
      const url = getAPIUrl('api/downloads', import.meta.env);
      const extra_params = {};
      if (this.downloadName) extra_params.title = this.downloadName;
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          urls: this.$refs.urlBox.value.trim().split('\n').join(' ').split(' '),
          format: this.$refs.selectedFormat.value,
          force_generic_extractor: this.forceGenericExtractor,
          extra_params: extra_params,
        })
      })
        .then(response => {
          if (response.status == 200) return response.json();
          throw new Error(response.statusText);
        })
        .then(data => {
          this.showToast(data.success ? (this.$refs.urlBox.value + " added to the list.") : data.error, data.success);
          this.$refs.urlBox.value = '';
          this.downloadName = '';
        })
        .catch((error) => {
          console.error(error);
          this.showToast('Could not add the url to the queue.', false);
        });
    },
    setupScrollObserver() {
      if (this.intersectionObserver) {
        this.intersectionObserver.disconnect();
        this.intersectionObserver = null;
      }
      const sentinel = this.$refs.scrollSentinel;
      if (!sentinel) return;
      this.intersectionObserver = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) this.extractorsPageSize += 200; },
        { root: this.$refs.extractorsBody, threshold: 0 }
      );
      this.intersectionObserver.observe(sentinel);
    },
    highlightMatch(text, query) {
      if (!query) return text;
      const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>');
    },
    toggleAdvancedOptions() {
      this.showAdvancedOptions = !this.showAdvancedOptions;
      saveConfig('showAdvancedOptions', this.showAdvancedOptions.toString());
      if (this.showAdvancedOptions) {
        this.advancedCollapse.show();
      } else {
        this.advancedCollapse.hide();
      }
    }
  }
}
</script>

<template>
  <div>
    <div class="toast-container">
      <div v-for="toast in toasts" :key="toast.id"
        class="toast show toast-item" :class="toast.success ? 'toast-success' : 'toast-error'">
        <span>{{ toast.success ? 'Success' : 'Error' }}: </span>{{ toast.message }}
      </div>
    </div>

    <div class="input-group mb-2">
      <input name="url" type="url" class="form-control" placeholder="URL" aria-label="URL"
        @keydown.enter.exact.prevent="submitVideo()" ref="urlBox" autocomplete="off" />
      <select class="custom-select" name="format" ref="selectedFormat" @change="updateUrlParameterFormat($event.target.value)">
        <optgroup v-for="category, category_name in formats.ydl_formats" :label="category_name">
          <option v-for="format_name, format in category" :value="format" :selected="default_format == format">
            {{ format_name }}
          </option>
        </optgroup>
      </select>
    </div>
    <div class="d-flex gap-2 justify-content-center mb-3">
      <button class="btn btn-primary" @click="submitVideo">Download</button>
      <button class="btn btn-secondary" @click="inspectVideo" :disabled="loading">
        <span v-if="!loading">Inspect</span>
        <span v-else>
          <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
          <span class="visually-hidden">Loading...</span>
        </span>
      </button>
    </div>
    <div class="mt-3 text-start">
      <button class="btn btn-link text-decoration-none p-0 advanced-toggle" type="button" @click="toggleAdvancedOptions">
        <span class="advanced-toggle-icon" :class="{ open: showAdvancedOptions }">&#9656;</span>
        Advanced Options
      </button>
      <div class="collapse mt-2" ref="advancedCollapseEl">
        <div class="p-3 border rounded advanced-options-panel">
          <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" :id="'forceGenericExtractor-' + uid" v-model="forceGenericExtractor">
            <label class="form-check-label" :for="'forceGenericExtractor-' + uid">
              Force generic extractor
            </label>
          </div>
          <div class="mb-2">
            <label :for="'downloadName-' + uid" class="form-label">Override video title:</label>
            <input type="text" class="form-control" :id="'downloadName-' + uid" v-model="downloadName" placeholder="Force a title for the video">
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div class="modal fade" ref="extractorsModalEl" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h1 class="modal-title fs-5">Available extractors</h1>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body text-left" ref="extractorsBody">
              <input type="text" v-model="extractorsFilter" class="form-control mb-1" placeholder="Search">
              <div class="text-muted small mb-2">
                <span v-if="extractorsFilter">{{ filteredExtractors.length }} of {{ extractors.length }}</span>
                <span v-else>{{ extractors.length }} extractors</span>
              </div>
              <span class="list-group">
                <span class="list-group-item list-group-item-action" v-for="extractor in visibleExtractors" :key="extractor">
                  <span v-html="highlightMatch(extractor, extractorsFilter)"></span>
                </span>
              </span>
              <div ref="scrollSentinel" v-if="!extractorsFilter && extractors.length > extractorsPageSize"></div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div class="modal fade" ref="metadataModalEl" role="dialog" aria-hidden="true" tabindex="-1" style="text-align: left">
        <div class="modal-dialog modal-lg" role="document">
          <div class="modal-content" v-if="metadata_list">
            <div class="modal-header">
              <h5 class="modal-title">{{ metadata_list && metadata_list.length === 1 ?
                get(metadata_list[0], 'title')
                :
                `Multiple Metadata sets (${metadata_list.length})` }}
              </h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body text-left">
              <p v-for="metadata in metadata_list">
                <span style="text-align: center">
                  <span>Title: <b>{{ get(metadata, 'title') }}</b><br /></span>
                  <span v-if="get(metadata, 'uploader')">Uploader: <b>{{ get(metadata, 'uploader') }}</b><br /></span>
                  Url: <b>
                    <a :href="get(metadata, 'webpage_url')" target="_blank">{{ get(metadata, 'webpage_url') }}</a>
                  </b>
                </span>
                <br /><br />
                <b v-if="get(metadata, '_type', '') === 'playlist'">Playlist</b>
                <b v-else>Available formats:</b>
                <br /><br />
                <span class="list-group" v-if="get(metadata, '_type', '') === 'playlist'">
                  <span v-for="entry in get(metadata, 'entries', [])" class="list-group-item list-group-item-action">
                    <span class="badge bg-success" role="button" @click="() => { queueVideo(entry.url, { format: $refs.selectedFormat.value }) }">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-white)" class="bi bi-download" viewBox="0 0 16 16">
                        <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
                        <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z" />
                      </svg> Queue</span>&nbsp;
                    <a target="_blank" :href="entry.url">{{ entry.title }}</a>
                  </span>
                  <br />
                </span>
                <span class="list-group" v-else>
                  <span v-for="format in get(metadata, 'formats', [])" class="list-group-item list-group-item-action">
                    <span class="badge bg-success" role="button" @click="() => { queueVideo(get(metadata, 'webpage_url'), getParamsFromSelection(format)) }">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-white)" class="bi bi-download" viewBox="0 0 16 16">
                        <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
                        <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z" />
                      </svg> Queue</span>&nbsp;
                    <a target="_blank" :href="format.url">{{ [format.ext, format.format, prettySize(format.filesize)].filter(x => !isEmpty(x)).join(' - ') }}</a>
                  </span>
                </span>
              </p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
