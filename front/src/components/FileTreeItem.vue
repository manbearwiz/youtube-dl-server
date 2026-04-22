<template>
    <tr :class="{ 'directory': item.directory }" @click="toggleDirectory" v-if="item.directory" style="cursor: pointer;">
      <td class="col-action file-tree-actions">
        <a type="button">
          <SvgIcon :name="isOpen ? 'folder-open' : 'folder'" color="var(--bs-teal)" />
        </a>
        <a href="#" @click.stop.prevent="$emit('delete', item.name)">
          <SvgIcon name="trash" color="var(--bs-red)" />
        </a>
      </td>
      <td :style="{ paddingLeft: (depth * 1.5 + 0.75) + 'rem' }"><b>{{ depth > 0 ? '\u21b3 ' : ''}}{{ item.name }}</b></td>
      <td class="col-size"></td>
      <td class="col-date">{{ formatDate(item.modified) }}</td>
      <td class="col-date">{{ formatDate(item.created) }}</td>
    </tr>
    <template v-if="item.directory && isOpen">
      <FileTreeItem
        v-for="child in item.children"
        :key="child.name"
        :item="child"
        :depth="depth + 1"
        :parent-path="parentPath ? `${parentPath}/${item.name}` : item.name"
        @delete="$emit('delete', parentPath ? `${parentPath}/${item.name}/${$event}` : `${item.name}/${$event}`)"
      />
    </template>
    <tr v-else-if="!item.directory">
      <td class="col-action file-tree-actions">
        <a :href="`api/finished/${encodeURIComponent(fullPath)}`" download>
          <SvgIcon name="download" color="var(--bs-teal)" />
        </a>
        <a href="#" @click.prevent="$emit('delete', item.name)" style="cursor: pointer;">
          <SvgIcon name="trash" color="var(--bs-red)" />
        </a>
      </td>
      <td :style="{ paddingLeft: (depth * 1.5 + 0.75) + 'rem' }">{{ depth > 0 ? '\u21b3 ' : ''}}<a :href="`api/finished/${encodeURIComponent(fullPath)}`">{{ item.name }}</a></td>
      <td class="col-size">{{ prettySize(item.size) }}</td>
      <td class="col-date">{{ formatDate(item.modified) }}</td>
      <td class="col-date">{{ formatDate(item.created) }}</td>
    </tr>
</template>

<script>
import SvgIcon from './SvgIcon.vue'

export default {
  name: 'FileTreeItem',
  components: { SvgIcon },
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
    formatDate(ts) {
      if (ts == null) return '';
      const d = new Date(ts * 1000);
      const pad = n => String(n).padStart(2, '0');
      return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
    },
    prettySize(size_b) {
      if (size_b == null) {
        return '';
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
