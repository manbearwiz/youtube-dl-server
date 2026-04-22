<script>
import { Modal } from 'bootstrap'
import DownloadForm from './DownloadForm.vue'

export default {
  components: { DownloadForm },
  data: () => ({
    modal: null,
  }),
  mounted() {
    this.modal = new Modal(this.$refs.modalEl);
    this.$refs.modalEl.addEventListener('shown.bs.modal', () => {
      this.$refs.form.focus();
    });
    this._onKeydown = (e) => {
      const tag = document.activeElement?.tagName;
      if (e.key === 'd' && tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
        this.open();
      }
    };
    window.addEventListener('keydown', this._onKeydown);
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this._onKeydown);
  },
  methods: {
    open() {
      this.modal.show();
    }
  }
}
</script>

<template>
  <button class="btn-theme-toggle ms-2" @click="open" title="Quick Download">
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
      <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
      <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
    </svg>
  </button>

  <div class="modal fade" ref="modalEl" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Quick Download</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <DownloadForm :syncRouteFormat="false" :autofocus="false" ref="form" />
        </div>
      </div>
    </div>
  </div>
</template>
