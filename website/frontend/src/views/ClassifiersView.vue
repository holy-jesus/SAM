<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { SoftwareClassifier } from '@/types';
import Card from '@/components/ui/Card.vue';
import Input from '@/components/ui/Input.vue';
import Badge from '@/components/ui/Badge.vue';
import { FolderTree, Search, ExternalLink, BookOpen, Layers, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-vue-next';

const classifiers = ref<SoftwareClassifier[]>([]);
const loading = ref(false);
const syncing = ref(false);
const syncMessage = ref('');
const syncError = ref('');
const searchQuery = ref('');

const loadClassifiers = async () => {
  loading.value = true;
  try {
    classifiers.value = await api.getClassifiers();
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadClassifiers();
});

const handleSyncClassifiers = async () => {
  syncing.value = true;
  syncMessage.value = '';
  syncError.value = '';
  try {
    const res = await api.syncClassifiers();
    syncMessage.value = res.message || 'Классификаторы успешно синхронизированы';
    await loadClassifiers();
    setTimeout(() => {
      syncMessage.value = '';
    }, 6000);
  } catch (err: any) {
    syncError.value = err?.response?.data?.detail || 'Не удалось синхронизировать классификаторы';
    setTimeout(() => {
      syncError.value = '';
    }, 6000);
  } finally {
    syncing.value = false;
  }
};

const filteredClassifiers = computed(() => {
  if (!searchQuery.value.trim()) return classifiers.value;
  const q = searchQuery.value.toLowerCase();
  return classifiers.value.filter(
    (c) =>
      c.code.toLowerCase().includes(q) ||
      c.class_name.toLowerCase().includes(q) ||
      c.section_name.toLowerCase().includes(q)
  );
});

// Группировка по разделам
const groupedSections = computed(() => {
  const groups: Record<string, SoftwareClassifier[]> = {};
  for (const item of filteredClassifiers.value) {
    if (!groups[item.section_name]) {
      groups[item.section_name] = [];
    }
    groups[item.section_name].push(item);
  }
  return groups;
});
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Классификатор программного обеспечения РФ</h1>
          <span class="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs font-bold border border-blue-200">
            ru-ikt.ru / Минцифры № 486
          </span>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Официальный справочник 12 разделов и 159+ классов программного обеспечения для каталогизации и импортозамещения
        </p>
      </div>

      <div class="flex items-center gap-2">
        <button
          @click="handleSyncClassifiers"
          :disabled="syncing"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg shadow-2xs transition-colors disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': syncing }" />
          <span>{{ syncing ? 'Синхронизация...' : 'Синхронизировать из Реестра ПО' }}</span>
        </button>

        <a
          href="https://ru-ikt.ru/reestrpo"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-lg shadow-2xs transition-colors"
        >
          <span>Открыть ru-ikt.ru/reestrpo</span>
          <ExternalLink class="w-3.5 h-3.5 text-slate-400" />
        </a>
      </div>
    </div>

    <!-- Уведомления об операции -->
    <div
      v-if="syncMessage"
      class="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center gap-2"
    >
      <CheckCircle2 class="w-4 h-4 text-emerald-600 shrink-0" />
      <span>{{ syncMessage }}</span>
    </div>

    <div
      v-if="syncError"
      class="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center gap-2"
    >
      <AlertCircle class="w-4 h-4 text-rose-600 shrink-0" />
      <span>{{ syncError }}</span>
    </div>

    <!-- Поле поиска и сводка -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div class="bg-white p-3 rounded-xl border border-slate-200 w-full sm:w-96">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по коду или классу (например: 04.03, СУБД, IDE)..."
        />
      </div>

      <div class="flex items-center gap-2 text-xs text-slate-500">
        <span class="font-medium text-slate-700">Всего классов:</span>
        <span class="px-2 py-0.5 rounded-full bg-slate-100 font-bold text-slate-800">{{ classifiers.length }}</span>
        <span>в</span>
        <span class="font-medium text-slate-700">{{ Object.keys(groupedSections).length }} разделах</span>
      </div>
    </div>

    <!-- Загрузка -->
    <div v-if="loading" class="text-center py-12 text-slate-400 text-sm">
      <RefreshCw class="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
      Загрузка классификатора ПО...
    </div>

    <!-- Дерево разделов и классов -->
    <div v-else class="space-y-4">
      <div
        v-for="(items, sectionTitle) in groupedSections"
        :key="sectionTitle"
        class="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs"
      >
        <!-- Заголовок раздела -->
        <div class="px-5 py-3.5 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <FolderTree class="w-4 h-4 text-blue-600" />
            <h3 class="font-bold text-slate-900 text-sm">{{ sectionTitle }}</h3>
          </div>
          <Badge variant="secondary" size="sm">
            {{ items.length }} {{ items.length === 1 ? 'класс' : 'класса' }}
          </Badge>
        </div>

        <!-- Список классов внутри раздела -->
        <div class="divide-y divide-slate-100">
          <div
            v-for="item in items"
            :key="item.id"
            class="px-5 py-3 flex items-center justify-between hover:bg-slate-50/50 transition-colors text-xs"
          >
            <div class="flex items-center gap-3">
              <span class="font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 text-[11px]">
                {{ item.code }}
              </span>
              <span class="font-medium text-slate-800">{{ item.class_name }}</span>
            </div>

            <div class="text-[11px] text-slate-400 font-mono">
              Минцифры РФ / Реестр ПО
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
