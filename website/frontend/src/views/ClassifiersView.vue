<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { SoftwareClassifier } from '@/types';
import Card from '@/components/ui/Card.vue';
import Input from '@/components/ui/Input.vue';
import Badge from '@/components/ui/Badge.vue';
import { FolderTree, Search, ExternalLink, BookOpen, Layers } from 'lucide-vue-next';

const classifiers = ref<SoftwareClassifier[]>([]);
const loading = ref(false);
const searchQuery = ref('');

onMounted(async () => {
  loading.value = true;
  try {
    classifiers.value = await api.getClassifiers();
  } finally {
    loading.value = false;
  }
});

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
            ru-ikt.ru / Минцифры
          </span>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Официальный справочник разделов и классов программного обеспечения для каталогизации и импортозамещения
        </p>
      </div>

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

    <!-- Поле поиска -->
    <div class="bg-white p-3 rounded-xl border border-slate-200 w-full sm:w-96">
      <Input
        v-model="searchQuery"
        placeholder="Поиск по коду или классу (например: 04.03, СУБД, IDE)..."
      />
    </div>

    <!-- Дерево разделов и классов -->
    <div class="space-y-4">
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
              Справочник Примера ПО
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
