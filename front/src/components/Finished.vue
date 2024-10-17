<script setup>
import { orderBy } from 'lodash'
import { getAPIUrl } from '../utils'
import FileTreeItem from './FileTreeItem.vue'
</script>
<script>
export default {
  data: () => ({
    finished: [],
    mounted: false,
    sortBy: 'created',
    sortOrder: 'desc',
    fileTree: [],
  }),
  mounted() {
    this.fetchFinished().then(() => {
      this.fileTree = this.buildFileTree(this.orderedFinished)
    });
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
      const url = getAPIUrl(`api/finished/${file_name}`);
      fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      this.fetchFinished(true)
    },
    async fetchFinished(once = false) {
      const url = getAPIUrl(`api/finished`);
      this.finished = await (await fetch(url)).json()
      if (!once && this.mounted) {
        setTimeout(() => {
          this.fetchFinished()
        }, 5000)
      }
    },
    buildFileTree(items, parentPath = '') {
      return items.map(item => {
        if (item.directory) {
          return {
            ...item,
            children: this.buildFileTree(item.children, `${parentPath}${item.name}/`)
          }
        }
        return item
      })
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

          <tbody>
            <FileTreeItem
              v-for="item in fileTree"
              :key="item.name"
              :item="item"
              :depth="0"
              @delete="deleteFinishedFile"
            />
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
