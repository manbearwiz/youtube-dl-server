<script setup>
import { get, isEmpty } from 'lodash'
import { Modal } from 'bootstrap'
import { getAPIUrl } from '../utils';
</script>

<script>
export default {
  data: () => ({
    extractors: [],
    formats: [],
    extractorsModal: null,
    urlBox: null,
    selectedFormat: null,
    metadata_list: null,
    loading: false,
    extractorsFilter: '',
    server_info: {},
  }),
  mounted() {
    this.extractorsModal = new Modal('#extractorsModal');
    this.metadataModal = new Modal('#metadataModal');
    this.urlBox = document.getElementById('url');
    this.selectedFormat = document.getElementById('format');
    this.messageList = document.getElementById('message_list');
    this.fetchExtractors();
    this.fetchAvailableFormats();
    this.fetchServerInfo();
  },

  computed: {
    filteredExtractors() {
      return this.extractorsFilter ? this.extractors.filter(extractor => extractor.toLowerCase().includes(this.extractorsFilter.toLowerCase())) : this.extractors;
    }
  },

  methods: {
    async fetchServerInfo() {
      const url = getAPIUrl('api/info', import.meta.env);
      this.server_info = await (await fetch(url)).json();
    },
    prettySize(size_b) {
      if (size_b == null) {
        return undefined;
      }
      var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
      var i = 0;
      for (i = 0; i < sizes.length; i++) {
        if (size_b < 1024) {
          i++;
          break
        }
        size_b = size_b / 1024;
      }
      return Number((size_b).toFixed(2)) + ' ' + sizes[i - 1];
    },
    escapeHtml(string) {
      return String(string).replace(/[&<>"'`=\/]/g, function (s) {
        return {
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;',
          '/': '&#x2F;',
          '`': '&#x60;',
          '=': '&#x3D;'
        }[s];
      });
    },
    async setDismissibleMessage(success, message) {
      message_list = "<div class=\"alert alert-dismissible alert-" + (success ? "success" : "danger") + " alert-dismissible fade show\" role=\"alert\">";
      message_list += "<strong>" + (success ? "Success" : "Error") + "</strong>: " + message;
      message_list += "<button type=\"button\" class=\"btn-close\" data-dismiss=\"alert\" aria-label=\"Close\" data-bs-dismiss=\"alert\"></button>";
      message_list += "</div>";
      message_list += this.messageList.innerHTML;
      this.messageList.innerHTML = message_list;
    },
    showExtractorsModal() {
      this.extractorsModal.show();
    },
    showMetadataModal() {
      this.metadataModal.show();
    },
    async fetchExtractors() {
      const url = getAPIUrl('api/extractors', import.meta.env);
      this.extractors = await (await fetch(url)).json()
    },
    async fetchAvailableFormats() {
      const url = getAPIUrl('api/formats', import.meta.env);
      this.formats = await (await fetch(url)).json()
    },
    async inspectVideo() {
      this.loading = true;
      const url = getAPIUrl('api/metadata', import.meta.env);
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          urls: this.urlBox.value.trim().split('\n').join(' ').split(' '),
        })
      })
        .then(response => {
          if (response.status == 200) {
            return response.json();
          }
          else {
            throw new Error(response.statusText);
          }
        })
        .then(data => {
          this.metadata_list = data;
          this.showMetadataModal();
        })
        .catch((error) => {
          console.error(error);
          this.setDismissibleMessage(false, 'Could not gather metadata for this video.');
        })
        .finally(() => {
          this.loading = false;
        });
    },
    getParamsFromSelection(format) {
      return {
        format: format.resolution == "audio only" ? this.selectedFormat.value : format.format_id,
        audio_format: format.resolution == "audio only" ? format.format_id : null
      }
    },
    async queueVideo(videoUrl, params) {
      const url = getAPIUrl('api/downloads', import.meta.env);
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          urls: [videoUrl],
          ...params
        })
      })
        .then(response => {
          if (response.status == 200) {
            return response.json();
          }
          else {
            throw new Error(response.statusText);
          }
        })
        .then(data => {
          this.setDismissibleMessage(data.success, data.success ? (this.escapeHtml(videoUrl) + " added to the queue.") : data.error);
          this.urlBox.value = '';
        })
        .catch((error) => {
          console.error(error);
          this.setDismissibleMessage(false, 'Could not add the url to the queue.');
        });
    },
    async submitVideo() {
      const url = getAPIUrl('api/downloads', import.meta.env);
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          urls: this.urlBox.value.trim().split('\n').join(' ').split(' '),
          format: this.selectedFormat.value
        })
      })
        .then(response => {
          if (response.status == 200) {
            return response.json();
          }
          else {
            throw new Error(response.statusText);
          }
        })
        .then(data => {
          this.setDismissibleMessage(data.success, data.success ? (this.escapeHtml(this.urlBox.value) + " added to the list.") : data.error);
          this.urlBox.value = '';
        })
        .catch((error) => {
          console.error(error);
          this.setDismissibleMessage(false, 'Could not add the url to the queue.');
        });
    }
  }
}
</script>
<template>
  <div class="content">
    <div class="container d-flex flex-column text-light text-center">
      <div class="flex-grow-1"></div>
      <div class="jumbotron bg-transparent flex-grow-1">
        <h1 class="display-4">{{ server_info.ydl_module_name }}</h1>
        <p class="lead">Enter a video URL to download the video to the server. URL can be to YouTube or <a
            class="text-info" @click="showExtractorsModal">any
            other supported site</a>. The server will automatically download the highest quality version available.</p>
        <div>
          <div class="input-group">
            <input name="url" type="url" class="form-control" placeholder="URL" aria-label="URL"
              @keydown.enter.exact.prevent="submitVideo()" id="url" autocomplete="off" autofocus />
            <select class="custom-select" name="format" id="format">
              <optgroup v-for="category, category_name in formats.ydl_formats" :label="category_name">
                <option v-for="format_name, format in category" :value="format"
                  :selected="formats.ydl_default_format == format">
                  {{ format_name }}
                </option>
              </optgroup>
            </select>
              <button class="btn btn-primary" id="button-submit" @click="submitVideo">
                Download
              </button>
              <button class="btn btn-secondary" id="button-submit" @click="inspectVideo" :disabled="loading">
                <span v-if="!loading">Inspect</span>
                <span v-else>
                  <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                  <span class="visually-hidden">Loading...</span>
                </span>
              </button>
          </div>
        </div>
        <br />

        <div class="modal fade text-dark" id="extractorsModal" tabindex="-1" aria-labelledby="extractors_title"
          aria-hidden="true">
          <div class="modal-dialog" id='extractors_dialog'>
            <div class="modal-content bg-light">
              <div class="modal-header">
                <h1 class="modal-title fs-5">Available extractors</h1>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body text-left" id="extractors_body">
                <input type="text" v-model="extractorsFilter" class="form-control mb-2" placeholder="Search">
                <p>
                  <span id="extractors_items" class="list-group">
                    <span class="list-group-item list-group-item-action" v-for="extractor in filteredExtractors">
                      <b>{{ extractor }}</b><br />
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

        <div class="modal fade text-dark" id="metadataModal" role="dialog" aria-hidden="true" tabindex="-1"
          aria-labelledby="metadata_title" style="text-align: left">
          <div class="modal-dialog modal-lg" id='md_dialog' role="document">
            <div class="modal-content bg-light" v-if="metadata_list">
              <div class="modal-header">
                <h5 class="modal-title" id="metadata_title">{{ metadata_list && metadata_list.length === 1 ?
                  get(metadata_list[0], 'title')
                  :
                  `Multiple Metadata sets (${metadata_list.length})` }}
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close">
                </button>
              </div>
              <div class="modal-body text-left" id="metadata_body">
                <p v-for="metadata in metadata_list">
                  <span style="text-align: center">
                    <span>Title: <b>{{ get(metadata, 'title') }}</b><br /></span>
                    <span v-if="get(metadata, 'uploader')">Uploader: <b>{{ get(metadata, 'uploader')
                    }}</b><br /></span>
                    Url: <b>
                      <a :href="get(metadata, 'webpage_url')" id="md_webpage_url" target="_blank">{{ get(metadata,
                        'webpage_url')
                      }}</a>
                    </b>
                  </span>
                  <br />
                  <br />
                  <b v-if="get(metadata, '_type', '') === 'playlist'">Playlist</b>
                  <b v-else>Available formats:</b>
                  <br />
                  <br />
                  <span class="list-group" v-if="get(metadata, '_type', '') === 'playlist'">
                    <span v-for="entry in get(metadata, 'entries', [])" class="list-group-item list-group-item-action">
                      <span class="badge bg-success" role="button" @click="() => {queueVideo(entry.url, {format: selectedFormat.value})}">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-white)" class="bi bi-download" viewBox="0 0 16 16">
                          <path
                            d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
                          <path
                            d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z" />
                        </svg> Queue</span>&nbsp;
                      <a target="_blank" :href=entry.url>{{ entry.title }}</a>
                    </span>
                    <br />
                  </span>
                  <span class="list-group" v-else>
                    <span v-for="format in get(metadata, 'formats', [])" class="list-group-item list-group-item-action">
                      <span class="badge bg-success" role="button" @click="() => {queueVideo(get(metadata, 'webpage_url'),
                        getParamsFromSelection(format)
                        )}">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-white)" class="bi bi-download" viewBox="0 0 16 16">
                          <path
                            d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
                          <path
                            d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z" />
                        </svg> Queue</span>&nbsp;
                      <a target="_blank" :href=format.url>{{ [format.ext,format.format, prettySize(format.filesize)].filter(x => !isEmpty(x)).join(' - ') }}</a>
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
        <div id="message_list">
        </div>
      </div>
    </div>
  </div>
</template>
