<script setup>
import { getAPIUrl } from '../utils';
</script>
<script>
export default {
  data: () => ({
    server_info: {},
  }),
  mounted() {
    this.fetchServerInfo();
    this.setBookmarklet();
  },

  methods: {
    async fetchServerInfo() {
      const url = getAPIUrl('api/info', import.meta.env);
      this.server_info = await (await fetch(url)).json();
    },
    setBookmarklet() {
      let url = window.location.protocol + '//' + window.location.hostname
      if (window.location.port != '') {
        url = url + ':' + window.location.port;
      }
      if (window.location.protocol == 'https:') {
        document.getElementById('bookmarklet').href = "javascript:fetch(\"" + url
          + "/api/downloads\",{body:JSON.stringify({'url':window.location.href}),method:\"POST\",headers:{'Content-Type':'application/json'}});";
      }
      else {
        document.getElementById('bookmarklet').href = "javascript:(function(){document.body.innerHTML += '<form name=\"ydl_form\" method=\"POST\" action=\""
          + url
          + "/api/downloads\"><input name=\"url\" type=\"url\" value=\"'+window.location.href+'\"/></form>';document.ydl_form.submit()})();";
      }
    }
  }
}
</script>
<template>
  <footer class="footer text-light text-center">
    <p class="text-muted">
      Drag and Drop the Bookmarklet to your bookmark bar for easy access: <a id="bookmarklet" class="badge text-bg-dark"
        href="">{{ server_info.ydl_module_name }}</a>
      <br />
      Powered by
      <a target="_blank" rel="noopener noreferrer" class="text-light" :href="server_info.ydl_module_website">{{
        server_info.ydl_module_name
      }}</a> version {{ server_info.ydl_module_version }}.
      Code &amp; issues on <a target="_blank" rel="noopener noreferrer" class="text-light"
        href="https://github.com/nbr23/youtube-dl-server">GitHub</a>.
      <span v-if="server_info.ydls_version != ''" data-toggle="tooltip" data-placement="top"
        :title="server_info.ydls_release_date">Rev <a target="_blank"
          :href="'https://github.com/nbr23/youtube-dl-server/commit/' + server_info.ydls_version"
          class="badge text-bg-dark">{{
            server_info.ydls_version }}</a>
      </span>
    </p>
  </footer>
</template>
