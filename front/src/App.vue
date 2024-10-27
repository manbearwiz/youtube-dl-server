<script setup>
import { ref, provide, onMounted } from 'vue'
import { getAPIUrl } from './utils';

import Header from './components/Header.vue'
import Footer from './components/Footer.vue'

const serverInfo = ref({})

const fetchServerInfo = async () => {
  const url = getAPIUrl('api/info', import.meta.env);
  serverInfo.value = await (await fetch(url)).json();
};

provide('serverInfo', serverInfo);

onMounted(() => {
  fetchServerInfo()
});
</script>

<template>
  <Header />
  <router-view></router-view>
  <Footer />
</template>

<style scoped></style>
