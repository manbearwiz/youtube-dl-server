<template>
    <tr class="d-flex" :class="{ 'directory': item.directory }" @click="toggleDirectory" v-if="item.directory">
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
        <a href="#" @click.stop.prevent="$emit('delete', item.name)" style="text-decoration: none;">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-red)"
            class="bi bi-trash" viewBox="0 0 16 16">
            <path
              d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z" />
            <path fill-rule="evenodd"
              d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z" />
          </svg>
        </a>
      </td>
      <td class="col-7"><b>{{ '&nbsp;'.repeat(depth*2) }}{{ depth > 0 ? '↳ ' : ''}}{{ item.name }}</b></td>
      <td class="col-2">{{ item.modified }}</td>
      <td class="col-2">{{ item.created }}</td>
    </tr>
    <template v-if="item.directory && isOpen">
      <FileTreeItem
        v-for="child in item.children"
        :key="child.name"
        :item="child"
        :depth="depth + 1"
        :parent-path="parentPath ? `${parentPath}/${item.name}` : item.name"
        @delete="$emit('delete', `${parentPath}/${item.name}/${$event}`)"
      />
    </template>
    <tr class="d-flex" v-else-if="!item.directory">
      <td class="col-1">
        <a :href="`api/finished/${encodeURIComponent(fullPath)}`" style="text-decoration: none;" download>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-teal)"
            class="bi bi-download" viewBox="0 0 16 16">
            <path
              d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
            <path
              d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z" />
          </svg>
        </a>
        <a @click.prevent="$emit('delete', item.name)" style="text-decoration: none; cursor: pointer;">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="var(--bs-red)"
            class="bi bi-trash" viewBox="0 0 16 16">
            <path
              d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z" />
            <path fill-rule="evenodd"
              d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z" />
          </svg>
        </a>
      </td>
      <td class="col-6">{{ '&nbsp;'.repeat(depth*2) }}{{ depth > 0 ? '↳ ' : ''}}<a :href="`api/finished/${encodeURIComponent(fullPath)}`">{{ item.name }}</a></td>
      <td class="col-1">{{ prettySize(item.size) }}</td>
      <td class="col-2">{{ item.modified }}</td>
      <td class="col-2">{{ item.created }}</td>
    </tr>
</template>

<script>
export default {
  name: 'FileTreeItem',
  props: {
    item: Object,
    parentPath: String,
    depth: Number
  },
  data() {
    return {
      isOpen: false
    }
  },
  computed: {
    fullPath() {
      return this.parentPath ? `${this.parentPath}/${this.item.name}` : this.item.name
    }
  },
  methods: {
    toggleDirectory() {
      if (this.item.directory) {
        this.isOpen = !this.isOpen
      }
    },
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
  }
}
</script>
