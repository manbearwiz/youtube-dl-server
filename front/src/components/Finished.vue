<script setup>
import { get, orderBy } from 'lodash'
</script>
<script>
export default {
  data: () => ({
    finished: [],
    mounted: false,
    VITE_YOUTUBE_DL_SERVER_API_URL: '',
    sortBy: 'created',
    sortOrder: 'desc',
  }),
  mounted() {
    this.VITE_YOUTUBE_DL_SERVER_API_URL = get(import.meta.env, 'VITE_YOUTUBE_DL_SERVER_API_URL', '');
    this.fetchFinished();
    this.mounted = true;
  },
  unmounted() {
    this.mounted = false;
  },
  computed: {
    orderedFinished: function () {
      if (this.sortBy === 'modified') {
        return orderBy(this.finished, e => {
          return new Date(e.modified)
        }, this.sortOrder)
      }
      if (this.sortBy === 'created') {
        return orderBy(this.finished, e => {
          return new Date(e.created)
        }, this.sortOrder)
      }
      return orderBy(this.finished, this.sortBy, this.sortOrder)
    }
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
    async deleteFinishedFile(file_name) {
      const url = `${this.VITE_YOUTUBE_DL_SERVER_API_URL}/api/finished/${file_name}`
      fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      this.fetchFinished(true)
    },
    async fetchFinished(once = false) {
      const url = `${this.VITE_YOUTUBE_DL_SERVER_API_URL}/api/finished`
      this.finished = await (await fetch(url)).json()
      if (!once && this.mounted) {
        setTimeout(() => {
          this.fetchFinished()
        }, 5000)
      }
    },
  }
}
</script>
<template>
  <div class="content">
    <div class="container text-light">
      <div class="row">
        <h1 class="display-4 text-center">Finished Files</h1>
      </div>
      <div class="row">
        <table class="col-md-16 table table-stripped table-md table-dark text-left">
          <thead>
            <tr class="d-flex">
              <th class="col-1">Action</th>
              <th class="col-6">Name
                <a :class="sortOrder === 'asc' && sortBy === 'name' ? 'text-light' : 'text-muted'"
                  style="text-decoration: none;" href="#" @click.prevent="sortBy = 'name'; sortOrder = 'asc'">&uarr;</a>
                <a :class="sortOrder === 'desc' && sortBy === 'name' ? 'text-light' : 'text-muted'"
                  style="text-decoration: none;" href="#" @click.prevent="sortBy = 'name'; sortOrder = 'desc'">&darr;</a>
              </th>
              <th class="col-1">Size
                <a :class="sortOrder === 'asc' && sortBy === 'size' ? 'text-light' : 'text-muted'"
                  style="text-decoration: none;" href="#" @click.prevent="sortBy = 'size'; sortOrder = 'asc'">&uarr;</a>
                <a :class="sortOrder === 'desc' && sortBy === 'size' ? 'text-light' : 'text-muted'"
                  style="text-decoration: none;" href="#" @click.prevent="sortBy = 'size'; sortOrder = 'desc'">&darr;</a>
              </th>
              <th class="col-2">Upload Date
                <a :class="sortOrder === 'asc' && sortBy === 'modified' ? 'text-light' : 'text-muted'"
                  style="text-decoration: none;" href="#"
                  @click.prevent="sortBy = 'modified'; sortOrder = 'asc'">&uarr;</a>
                <a :class="sortOrder === 'desc' && sortBy === 'modified' ? 'text-light' : 'text-muted'"
                  style="text-decoration: none;" href="#"
                  @click.prevent="sortBy = 'modified'; sortOrder = 'desc'">&darr;</a>
              </th>
              <th class="col-2">Fetch Date
                <a :class="sortOrder === 'asc' && sortBy === 'created' ? 'text-light' : 'text-muted'"
                  style="text-decoration: none;" href="#"
                  @click.prevent="sortBy = 'created'; sortOrder = 'asc'">&uarr;</a>
                <a :class="sortOrder === 'desc' && sortBy === 'created' ? 'text-light' : 'text-muted'"
                  style="text-decoration: none;" href="#"
                  @click.prevent="sortBy = 'created'; sortOrder = 'desc'">&darr;</a>
              </th>
            </tr>
          </thead>
          <template v-for="(f, i) in orderedFinished">
            <template v-if="f.directory">
              <tbody>
                <tr class="d-flex" href="#" data-bs-toggle="collapse" :data-bs-target="'#directory-' + i"
                  aria-expanded="false" :aria-controls="'directory-' + i">
                  <td class="col-1">
                    <a type="button" style="text-decoration: none;">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-teal)"
                        class="bi bi-folder-plus" viewBox="0 0 16 16">
                        <path
                          d="m.5 3 .04.87a1.99 1.99 0 0 0-.342 1.311l.637 7A2 2 0 0 0 2.826 14H9v-1H2.826a1 1 0 0 1-.995-.91l-.637-7A1 1 0 0 1 2.19 4h11.62a1 1 0 0 1 .996 1.09L14.54 8h1.005l.256-2.819A2 2 0 0 0 13.81 3H9.828a2 2 0 0 1-1.414-.586l-.828-.828A2 2 0 0 0 6.172 1H2.5a2 2 0 0 0-2 2zm5.672-1a1 1 0 0 1 .707.293L7.586 3H2.19c-.24 0-.47.042-.683.12L1.5 2.98a1 1 0 0 1 1-.98h3.672z" />
                        <path
                          d="M13.5 10a.5.5 0 0 1 .5.5V12h1.5a.5.5 0 1 1 0 1H14v1.5a.5.5 0 1 1-1 0V13h-1.5a.5.5 0 0 1 0-1H13v-1.5a.5.5 0 0 1 .5-.5z" />
                      </svg>
                    </a>
                    <a href="#" @click.prevent="deleteFinishedFile(encodeURIComponent(f.name))"
                      style="text-decoration: none;">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-red)"
                        class="bi bi-trash" viewBox="0 0 16 16">
                        <path
                          d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z" />
                        <path fill-rule="evenodd"
                          d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z" />
                      </svg>
                    </a>
                  </td>
                  <td class="col-7"><b>{{ f.name }}</b></td>
                  <td class="col-2">{{ f.modified }}</td>
                  <td class="col-2">{{ f.created }}</td>
                </tr>
              </tbody>
              <tbody v-for="c in f.children" class="collapse" :id="'directory-' + i">
                <tr class="d-flex">
                  <td class="col-1">
                    <a :href="VITE_YOUTUBE_DL_SERVER_API_URL + '/api/finished/' + encodeURIComponent(f.name) + '/' + encodeURIComponent(c.name)"
                      style="text-decoration: none;" download>
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-teal)"
                        class="bi bi-download" viewBox="0 0 16 16">
                        <path
                          d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
                        <path
                          d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z" />
                      </svg>
                    </a>
                    <a href="#"
                      @click.prevent="deleteFinishedFile(`${encodeURIComponent(f.name)}/${encodeURIComponent(c.name)}`)"
                      style="text-decoration: none;">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-red)"
                        class="bi bi-trash" viewBox="0 0 16 16">
                        <path
                          d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z" />
                        <path fill-rule="evenodd"
                          d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z" />
                      </svg>
                    </a>
                  </td>
                  <td class="col-6">&#x21B3;&emsp;<a
                      :href="VITE_YOUTUBE_DL_SERVER_API_URL + '/api/finished/' + encodeURIComponent(f.name) + '/' + encodeURIComponent(c.name)">{{
                        c.name
                      }}</a></td>
                  <td class="col-1">{{ prettySize(c.size) }}</td>
                  <td class="col-2">{{ c.modified }}</td>
                  <td class="col-2">{{ c.created }}</td>
                </tr>
              </tbody>
            </template>
            <tbody v-else>
              <tr class="d-flex">
                <td class="col-1">
                  <a :href="VITE_YOUTUBE_DL_SERVER_API_URL + '/api/finished/' + encodeURIComponent(f.name)"
                    style="text-decoration: none;" download>
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-teal)"
                      class="bi bi-download" viewBox="0 0 16 16">
                      <path
                        d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
                      <path
                        d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z" />
                    </svg>
                  </a>
                  <a @click.prevent="deleteFinishedFile(encodeURIComponent(f.name))"
                    style="text-decoration: none; cursor: pointer;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-red)"
                      class="bi bi-trash" viewBox="0 0 16 16">
                      <path
                        d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z" />
                      <path fill-rule="evenodd"
                        d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z" />
                    </svg>
                  </a>
                </td>
                <td class="col-6"><a
                    :href="VITE_YOUTUBE_DL_SERVER_API_URL + '/api/finished/' + encodeURIComponent(f.name)">{{
                      f.name
                    }}</a></td>
                <td class="col-1">{{ prettySize(f.size) }}</td>
                <td class="col-2">{{ f.modified }}</td>
                <td class="col-2">{{ f.created }}</td>
              </tr>
            </tbody>
          </template>
        </table>
      </div>
    </div>
  </div>
</template>