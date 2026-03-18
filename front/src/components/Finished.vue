<script setup>
import { orderBy } from 'lodash'
import { Modal } from 'bootstrap'
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
    toasts: [],
    pendingDeleteFile: null,
  }),
  mounted() {
    this.fetchFinished();
    this.mounted = true;
  },
  unmounted() {
    this.mounted = false;
  },
  computed: {
    fileTreeOrdered() {
      return this.buildFileTree(this.finished)
    },
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
    deleteFinishedFile(file_name) {
      this.pendingDeleteFile = file_name;
      new Modal('#deleteConfirmModal').show();
    },
    async confirmDelete() {
      const url = getAPIUrl(`api/finished/${encodeURIComponent(this.pendingDeleteFile)}`);
      this.pendingDeleteFile = null;
      try {
        const response = await fetch(url, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json'
          }
        });
        const result = await response.json();
        if (!result.success) {
          this.showToast(result.message || 'Could not delete the file.', false);
        } else {
          this.showToast(result.message || 'File deleted successfully.', true);
        }
      } catch (error) {
        this.showToast(error.message || 'Network error while deleting file.', false);
      }
      this.fetchFinished(true)
    },
    showToast(message, success = true) {
      const id = Date.now() + Math.random();
      this.toasts.push({ id, message, success });
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id);
      }, 5000);
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
    order(items) {
      if (this.sortBy === 'modified') {
        return orderBy(items, e => {
          return new Date(e.modified)
        }, this.sortOrder)
      }
      if (this.sortBy === 'created') {
        return orderBy(items, e => {
          return new Date(e.created)
        }, this.sortOrder)
      }
      return orderBy(items, this.sortBy, this.sortOrder)
    },
    buildFileTree(items, parentPath = '') {
      const sortedItems = this.order(items);
      return sortedItems.map(item => {
        if (item.directory) {
          return {
            ...item,
            children: this.buildFileTree(item.children, `${parentPath}${item.name}/`)
          }
        }
        return item
      });
    },
    sortClass(field, direction) {
      return ['sort-arrow', { active: this.sortBy === field && this.sortOrder === direction }];
    },
  }
}
</script>
<template>
  <div class="content">
    <div class="container-fluid">
      <div class="toast-container">
        <div v-for="toast in toasts" :key="toast.id"
          class="toast show toast-item" :class="toast.success ? 'toast-success' : 'toast-error'">
          <span>{{ toast.success ? 'Success' : 'Error' }}: </span>{{ toast.message }}
        </div>
      </div>

      <div class="row">
        <h1 class="display-4 text-center">Finished Files</h1>
      </div>
      <div class="table-responsive">
        <table class="table file-tree-table text-left">
          <thead>
            <tr>
              <th class="col-action">Action</th>
              <th>Name
                <a :class="sortClass('name', 'asc')" href="#" @click.prevent="sortBy = 'name'; sortOrder = 'asc'">&uarr;</a>
                <a :class="sortClass('name', 'desc')" href="#" @click.prevent="sortBy = 'name'; sortOrder = 'desc'">&darr;</a>
              </th>
              <th class="col-size">Size
                <a :class="sortClass('size', 'asc')" href="#" @click.prevent="sortBy = 'size'; sortOrder = 'asc'">&uarr;</a>
                <a :class="sortClass('size', 'desc')" href="#" @click.prevent="sortBy = 'size'; sortOrder = 'desc'">&darr;</a>
              </th>
              <th class="col-date">Upload Date
                <a :class="sortClass('modified', 'asc')" href="#" @click.prevent="sortBy = 'modified'; sortOrder = 'asc'">&uarr;</a>
                <a :class="sortClass('modified', 'desc')" href="#" @click.prevent="sortBy = 'modified'; sortOrder = 'desc'">&darr;</a>
              </th>
              <th class="col-date">Fetch Date
                <a :class="sortClass('created', 'asc')" href="#" @click.prevent="sortBy = 'created'; sortOrder = 'asc'">&uarr;</a>
                <a :class="sortClass('created', 'desc')" href="#" @click.prevent="sortBy = 'created'; sortOrder = 'desc'">&darr;</a>
              </th>
            </tr>
          </thead>

          <tbody>
            <FileTreeItem v-for="item in fileTreeOrdered" :key="item.name" :item="item" :depth="0"
              @delete="deleteFinishedFile" />
          </tbody>
        </table>
      </div>
      <div class="modal fade" id="deleteConfirmModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Delete file</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              Are you sure you want to delete <strong>{{ pendingDeleteFile }}</strong>?
            </div>
            <div class="modal-footer">
              <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
              <button class="btn btn-danger" data-bs-dismiss="modal" @click="confirmDelete">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
