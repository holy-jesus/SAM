<script setup lang="ts">
import Navbar from './Navbar.vue';
import Sidebar from './Sidebar.vue';
import SmartMatchModal from '@/components/ai/SmartMatchModal.vue';
import EulaAnalyzerModal from '@/components/ai/EulaAnalyzerModal.vue';
import AIChatWidget from '@/components/ai/AIChatWidget.vue';
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex flex-col font-sans">
    <!-- Navbar -->
    <Navbar />

    <!-- Main Container -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Sidebar -->
      <Sidebar />

      <!-- Page Content -->
      <main class="flex-1 overflow-y-auto p-6 md:p-8 space-y-6">
        <slot />
      </main>
    </div>

    <!-- Global AI Modals & Floating Chat Widget -->
    <SmartMatchModal />
    <EulaAnalyzerModal />
    <AIChatWidget />
  </div>
</template>
