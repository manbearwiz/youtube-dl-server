<script setup>
import { inject } from 'vue'

const serverInfo = inject('serverInfo')
const endpoint = `${window.location.origin}/api/downloads`
const bookmarklet = window.location.protocol === 'https:'
  ? `javascript:fetch(${JSON.stringify(endpoint)},{body:JSON.stringify({url:window.location.href}),method:"POST",headers:{"Content-Type":"application/json"}});`
  : `javascript:(function(){document.body.innerHTML += '<form name="ydl_form" method="POST" action="${endpoint}"><input name="url" type="url" value="'+window.location.href+'"/></form>';document.ydl_form.submit()})();`
</script>

<template>
  <footer class="footer d-flex flex-wrap align-items-center justify-content-center column-gap-2 row-gap-1 px-2 pb-3 small text-muted">
    <a id="bookmarklet" class="footer-link" :href="bookmarklet" title="Drag to your bookmarks bar">Bookmarklet</a>
    <span v-if="serverInfo.ydl_module_name" class="d-inline-flex align-items-center gap-2 text-nowrap">
      <span aria-hidden="true">·</span>
      <a target="_blank" rel="noopener noreferrer" class="footer-link" :href="serverInfo.ydl_module_website">
        {{ serverInfo.ydl_module_name }} {{ serverInfo.ydl_module_version }}
      </a>
    </span>
    <span class="d-inline-flex align-items-center gap-2">
      <span aria-hidden="true">·</span>
      <a target="_blank" rel="noopener noreferrer" class="footer-link" href="https://github.com/nbr23/youtube-dl-server">GitHub</a>
    </span>
    <span v-if="serverInfo.ydls_version" class="d-inline-flex align-items-center gap-2">
      <span aria-hidden="true">·</span>
      <span>v{{ serverInfo.ydls_version }}</span>
    </span>
  </footer>
</template>
