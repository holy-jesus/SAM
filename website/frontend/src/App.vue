<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import AppLayout from '@/components/layout/AppLayout.vue';

const route = useRoute();
const isPublicPage = computed(() => !!route.meta.public);
</script>

<template>
  <div v-if="isPublicPage">
    <RouterView />
  </div>
  <AppLayout v-else>
    <RouterView />
  </AppLayout>
</template>
