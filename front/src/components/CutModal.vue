<script>
import { Modal } from 'bootstrap'
import { getAPIUrl } from '../utils'

const AUDIO_EXTS = ['mp3', 'm4a', 'aac', 'ogg', 'opus', 'flac', 'wav'];

export default {
  emits: ['queued'],
  data: () => ({
    modal: null,
    filePath: null,
    start: '',
    end: '',
    mode: 'fast',
    output: '',
    error: null,
    previewFailed: false,
    submitting: false,
    previewEndTime: null,
    buffering: false,
  }),
  mounted() {
    this.modal = new Modal(this.$refs.modalEl);
    this.$refs.modalEl.addEventListener('hidden.bs.modal', () => {
      this.filePath = null;
    });
  },
  computed: {
    fileName() {
      return this.filePath ? this.filePath.split('/').pop() : '';
    },
    isAudio() {
      return AUDIO_EXTS.includes(this.fileName.split('.').pop().toLowerCase());
    },
    mediaUrl() {
      return this.filePath ? getAPIUrl(`api/finished/${encodeURIComponent(this.filePath)}`) : '';
    },
  },
  methods: {
    open(filePath) {
      this.filePath = filePath;
      this.start = '';
      this.end = '';
      this.mode = 'fast';
      this.error = null;
      this.previewFailed = false;
      this.submitting = false;
      this.previewEndTime = null;
      this.buffering = false;
      const name = filePath.split('/').pop();
      const dot = name.lastIndexOf('.');
      this.output = dot > 0 ? `${name.slice(0, dot)}_cut${name.slice(dot)}` : `${name}_cut`;
      this.modal.show();
    },
    onLoadedMetadata() {
      const duration = this.$refs.player?.duration;
      if (isFinite(duration)) {
        this.start = this.start || this.formatTime(0);
        this.end = this.end || this.formatTime(duration);
      }
    },
    setFromPlayhead(field) {
      const t = this.$refs.player?.currentTime;
      if (t != null) {
        this[field] = this.formatTime(t);
      }
    },
    seekTo(value) {
      const secs = this.parseTime(value);
      if (secs != null && this.$refs.player) {
        this.$refs.player.currentTime = secs;
      }
    },
    jumpToStart() {
      this.seekTo(this.start || '0');
    },
    previewClip() {
      const player = this.$refs.player;
      if (!player) return;
      const startSecs = this.parseTime(this.start || '0') ?? 0;
      this.previewEndTime = this.end ? this.parseTime(this.end) : null;
      player.currentTime = startSecs;
      player.play();
    },
    onTimeUpdate() {
      const player = this.$refs.player;
      if (this.previewEndTime != null && player && player.currentTime >= this.previewEndTime) {
        player.pause();
        this.previewEndTime = null;
      }
    },
    formatTime(secs) {
      if (secs == null || !isFinite(secs)) return '';
      const total = Math.round(secs * 10) / 10;
      const h = Math.floor(total / 3600);
      const m = Math.floor((total % 3600) / 60);
      const s = Math.round((total - h * 3600 - m * 60) * 10) / 10;
      const pad = (n) => String(n).padStart(2, '0');
      const sStr = s.toFixed(1).replace(/\.0$/, '');
      return `${pad(h)}:${pad(m)}:${s < 10 ? '0' + sStr : sStr}`;
    },
    parseTime(str) {
      if (!str) return null;
      const parts = String(str).trim().split(':');
      if (parts.length > 3 || parts.some((p) => p === '' || isNaN(Number(p)))) {
        return null;
      }
      return parts.reduce((acc, p) => acc * 60 + Number(p), 0);
    },
    async submit() {
      this.error = null;
      const startSecs = this.parseTime(this.start || '0');
      const endSecs = this.end ? this.parseTime(this.end) : null;
      if (startSecs == null || (this.end && endSecs == null)) {
        this.error = 'Times must be in HH:MM:SS or seconds format.';
        return;
      }
      if (endSecs != null && endSecs <= startSecs) {
        this.error = 'End time must be after start time.';
        return;
      }
      const output = this.output.trim();
      if (!output || output.includes('/') || output.startsWith('.')) {
        this.error = 'Invalid output filename.';
        return;
      }
      this.submitting = true;
      try {
        const url = getAPIUrl(`api/finished/${encodeURIComponent(this.filePath)}/cut`);
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            start: this.start || '0',
            end: this.end || null,
            mode: this.mode,
            output,
          }),
        });
        const result = await response.json();
        if (result.success) {
          this.modal.hide();
          this.$emit('queued', result.output);
        } else {
          this.error = result.message || 'Could not queue the cut job.';
        }
      } catch (e) {
        this.error = e.message || 'Network error while queuing the cut job.';
      }
      this.submitting = false;
    },
  }
}
</script>

<template>
  <div class="modal fade" ref="modalEl" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title text-truncate">Cut {{ fileName }}</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <template v-if="filePath">
            <div class="position-relative mb-3">
              <audio v-if="isAudio" ref="player" :src="mediaUrl" controls preload="auto" class="w-100"
                @loadedmetadata="onLoadedMetadata" @error="previewFailed = true" @timeupdate="onTimeUpdate"
                @waiting="buffering = true" @playing="buffering = false" @pause="buffering = false"></audio>
              <video v-else ref="player" :src="mediaUrl" controls preload="auto" class="w-100"
                style="max-height: 320px; background: #000;"
                @loadedmetadata="onLoadedMetadata" @error="previewFailed = true" @timeupdate="onTimeUpdate"
                @waiting="buffering = true" @playing="buffering = false" @pause="buffering = false"></video>
              <div v-if="buffering" class="position-absolute top-50 start-50 translate-middle">
                <div class="spinner-border text-light" role="status">
                  <span class="visually-hidden">Buffering...</span>
                </div>
              </div>
            </div>
          </template>
          <div v-if="previewFailed" class="alert alert-warning">
            Preview is not supported for this file format in your browser — enter the times manually.
          </div>

          <div class="row g-2 align-items-center mb-2">
            <label class="col-2 col-form-label">Start</label>
            <div class="col">
              <input v-model="start" class="form-control" placeholder="00:00:00" @change="seekTo(start)">
            </div>
            <div class="col-auto">
              <button class="btn btn-outline-secondary" :disabled="previewFailed"
                @click="setFromPlayhead('start')">Set from playhead</button>
            </div>
            <div class="col-auto">
              <button class="btn btn-outline-secondary" :disabled="previewFailed"
                @click="jumpToStart">Jump to start</button>
            </div>
          </div>
          <div class="row g-2 align-items-center mb-3">
            <label class="col-2 col-form-label">End</label>
            <div class="col">
              <input v-model="end" class="form-control" placeholder="00:01:30" @change="seekTo(end)">
            </div>
            <div class="col-auto">
              <button class="btn btn-outline-secondary" :disabled="previewFailed"
                @click="setFromPlayhead('end')">Set from playhead</button>
            </div>
          </div>
          <div class="mb-3">
            <button class="btn btn-outline-primary" :disabled="previewFailed"
              @click="previewClip">Preview clip</button>
          </div>

          <div class="mb-3">
            <div class="form-check">
              <input class="form-check-input" type="radio" id="cutModeFast" value="fast" v-model="mode">
              <label class="form-check-label" for="cutModeFast">
                <b>Fast</b> — no re-encode, cut snaps to the nearest keyframe
              </label>
            </div>
            <div class="form-check">
              <input class="form-check-input" type="radio" id="cutModePrecise" value="precise" v-model="mode">
              <label class="form-check-label" for="cutModePrecise">
                <b>Precise</b> — re-encodes, frame-accurate but slower
              </label>
            </div>
          </div>

          <div class="row g-2 align-items-center">
            <label class="col-2 col-form-label">Save as</label>
            <div class="col">
              <input v-model="output" class="form-control">
            </div>
          </div>

          <div v-if="error" class="alert alert-danger mt-3 mb-0">{{ error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
          <button class="btn btn-primary" :disabled="submitting" @click="submit">Queue cut</button>
        </div>
      </div>
    </div>
  </div>
</template>
