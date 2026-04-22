<script setup>
import { inject } from 'vue'
import DownloadForm from './DownloadForm.vue'
</script>

<script>
export default {
  data: () => ({
    server_info: {},
  }),
  mounted() {
    this.server_info = inject('serverInfo');
  },
  methods: {
    showExtractorsModal() {
      this.$refs.form.showExtractorsModal();
    }
  }
}
</script>

<template>
  <div class="content">
    <div class="container text-center" style="padding-top: 4rem;">
      <h1 class="display-4">{{ server_info.ydl_module_name }}</h1>
      <p class="lead">Enter a video URL to download the video to the server. URL can be to YouTube or <a
          href="#" @click.prevent="showExtractorsModal">any
          other supported site</a>. The server will automatically download the highest quality version available.</p>
      <DownloadForm ref="form" />
    </div>
  </div>
</template>
