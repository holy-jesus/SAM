<script setup lang="ts">
import Navbar from './Navbar.vue';
import Sidebar from './Sidebar.vue';
import SmartMatchModal from '@/components/ai/SmartMatchModal.vue';
import EulaAnalyzerModal from '@/components/ai/EulaAnalyzerModal.vue';
import AIChatWidget from '@/components/ai/AIChatWidget.vue';
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex flex-col font-sans">
    <!-- Верхняя панель навигации (Navbar) -->
    <Navbar />

    <!-- Основной контейнер рабочей области -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Боковое меню (Sidebar) -->
      <Sidebar />

      <!-- Область отображения текущей страницы -->
      <main class="flex-1 overflow-y-auto p-6 md:p-8 space-y-6">
        <slot />
      </main>
    </div>

    <!-- Глобальные модальные окна ИИ и плавающий чат-виджет -->
    <SmartMatchModal />
    <EulaAnalyzerModal />
    <AIChatWidget />
  </div>
</template>
