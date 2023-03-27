<script setup>
import { get } from 'lodash'
import { Modal } from 'bootstrap'
</script>

<script>
export default {
  data: () => ({
    extractors: [],
    formats: [],
    extractorsModal: null,
    urlBox: null,
    selectedFormat: null,
    metadata: null,
    VITE_YOUTUBE_DL_SERVER_API_URL: '',
  }),
  mounted() {
    this.VITE_YOUTUBE_DL_SERVER_API_URL = get(import.meta.env, 'VITE_YOUTUBE_DL_SERVER_API_URL', ''); this.extractorsModal = new Modal('#extractorsModal');
    this.metadataModal = new Modal('#metadataModal');
    this.urlBox = document.getElementById('url');
    this.selectedFormat = document.getElementById('format');
    this.messageList = document.getElementById('message_list');
    this.fetchExtractors();
    this.fetchAvailableFormats();
  },

  methods: {
    prettySize(size_b) {
      if (size_b == null) {
        return "NaN";
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
      const url = `${this.VITE_YOUTUBE_DL_SERVER_API_URL}/api/extractors`
      this.extractors = await (await fetch(url)).json()
    },
    async fetchAvailableFormats() {
      const url = `${this.VITE_YOUTUBE_DL_SERVER_API_URL}/api/formats`
      this.formats = await (await fetch(url)).json()
    },
    async submitVideo() {
      if (this.selectedFormat.value != 'metadata') {
        fetch(`${this.VITE_YOUTUBE_DL_SERVER_API_URL}/api/downloads`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            url: this.urlBox.value,
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
            console.log(data);
            this.setDismissibleMessage(data.success, data.success ? (this.escapeHtml(this.urlBox.value) + " added to the list.") : data.error);
            this.urlBox.value = '';
          })
          .catch((error) => {
            console.error(error);
            this.setDismissibleMessage(false, 'Could not add the url to the queue.');
          });
      }
      else {
        fetch(`${this.VITE_YOUTUBE_DL_SERVER_API_URL}/api/metadata`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            url: this.urlBox.value,
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
            this.metadata = data;
            this.showMetadataModal();
          })
          .catch((error) => {
            console.error(error);
            this.setDismissibleMessage(false, 'Could not gather metadata for this video.');
          });
      }
    }
  }
}
</script>
<template>
  <div class="content">
    <div class="container d-flex flex-column text-light text-center">
      <div class="flex-grow-1"></div>
      <div class="jumbotron bg-transparent flex-grow-1">
        <h1 class="display-4">youtube-dl</h1>
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
            <div class="input-group-append">
              <button class="btn btn-primary" id="button-submit" @click="submitVideo">Submit</button>
            </div>
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
                <p>
                  <span id="extractors_items">
                    <span v-for="extractor in extractors">
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
          aria-labelledby="metadata_title">
          <div class="modal-dialog" id='md_dialog' role="document">
            <div class="modal-content bg-light">
              <div class="modal-header">
                <h5 class="modal-title" id="metadata_title">{{ get(metadata, 'title') }}</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close">
                </button>
              </div>
              <div class="modal-body text-left" id="metadata_body">
                <p>
                  Title: <b><span id="md_title">{{ get(metadata, 'title') }}</span></b><br />
                  Uploader: <b><span id="md_uploader">{{ get(metadata, 'uploader') }}</span></b><br />
                  Url: <b>
                    <a :href="get(metadata, 'webpage_url')" id="md_webpage_url" target="_blank">{{ get(metadata,
                      'webpage_url')
                    }}</a>
                  </b><br />
                  <br />
                  <span v-if="get(metadata, '_type', '') === 'playlist'">Playlist</span>
                  <span v-else>Available formats:</span>
                  <br />
                  <span v-if="get(metadata, '_type', '') === 'playlist'">
                    <span v-for="entry in get(metadata, 'entries', [])">
                      <a target="_blank" :href=entry.url>{{ entry.title }}</a>
                      <br />
                    </span>
                  </span>
                  <span v-else>
                    <span v-for="format in get(metadata, 'formats', [])">
                      <a target="_blank" :href=format.url>{{ format.ext }} {{ format.format }} - {{
                        prettySize(format.filesize) }}</a>
                      <br />
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