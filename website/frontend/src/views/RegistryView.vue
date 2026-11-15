<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { RuSoftwareRegistryItem } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import {
  Landmark,
  RefreshCw,
  Search,
  CheckCircle2,
  ExternalLink,
  Sparkles,
  Calendar,
  Layers,
} from 'lucide-vue-next';

// Реактивное состояние реестра
const registryItems = ref<RuSoftwareRegistryItem[]>([]);
const lastUpdated = ref<string | null>(null);
const totalRecords = ref<number | null>(null);
const loading = ref(false);
const syncing = ref(false);
const syncSuccess = ref(false);
const searchQuery = ref('');

onMounted(async () => {
  await Promise.all([loadRegistry(), loadStatus()]);
});

// Загрузка записей реестра
async function loadRegistry() {
  loading.value = true;
  try {
    registryItems.value = await api.getRegistry();
  } finally {
    loading.value = false;
  }
}

// Загрузка метаданных статуса реестра из бэкенда
async function loadStatus() {
  try {
    const status = await api.getRegistryStatus();
    lastUpdated.value = status.last_updated_at;
    totalRecords.value = status.total_records;
  } catch (e) {
    totalRecords.value = registryItems.value.length;
  }
}

// Ручной запуск синхронизации с Минцифры РФ
async function runSync() {
  syncing.value = true;
  syncSuccess.value = false;
  try {
    const res = await api.syncRegistry();
    lastUpdated.value = new Date().toISOString();
    totalRecords.value = res.updated_count;
    syncSuccess.value = true;
    await loadRegistry();
    setTimeout(() => {
      syncSuccess.value = false;
    }, 3000);
  } finally {
    syncing.value = false;
  }
}

// Запуск батч-генерации векторных эмбеддингов для семантического поиска
const generatingEmbeddings = ref(false);
const embeddingSuccessMessage = ref<string | null>(null);

async function runGenerateEmbeddings() {
  generatingEmbeddings.value = true;
  embeddingSuccessMessage.value = null;
  try {
    const res = await api.generateRegistryEmbeddings(200);
    embeddingSuccessMessage.value = res.message;
    setTimeout(() => {
      embeddingSuccessMessage.value = null;
    }, 4000);
  } finally {
    generatingEmbeddings.value = false;
  }
}

// Фильтрация записей реестра по строке поиска
const filteredItems = computed(() => {
  if (!searchQuery.value.trim()) return registryItems.value;
  const q = searchQuery.value.toLowerCase();
  return registryItems.value.filter(
    (item) =>
      item.name.toLowerCase().includes(q) ||
      item.reg_number.includes(q) ||
      item.vendor_name?.toLowerCase().includes(q) ||
      item.software_class?.toLowerCase().includes(q)
  );
});
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Единый реестр отечественного ПО</h1>
          <span class="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs font-bold border border-blue-200">
            Минцифры РФ
          </span>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Синхронизация с reestr.digital.gov.ru для проверки импортозамещения и нормализации ПО
        </p>
      </div>

      <div class="flex items-center gap-2">
        <a
          href="https://reestr.digital.gov.ru/reestr/?export=list"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-lg shadow-2xs transition-colors"
        >
          <span>reestr.digital.gov.ru</span>
          <ExternalLink class="w-3.5 h-3.5 text-slate-400" />
        </a>

        <Button
          variant="outline"
          size="sm"
          :loading="generatingEmbeddings"
          @click="runGenerateEmbeddings"
        >
          <Sparkles class="w-3.5 h-3.5 mr-1 text-purple-600" />
          Эмбеддинги (OpenAI)
        </Button>

        <Button
          variant="primary"
          size="sm"
          :loading="syncing"
          @click="runSync"
        >
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          Обновить реестр сейчас
        </Button>
      </div>
    </div>

    <!-- Уведомление о генерации эмбеддингов -->
    <div v-if="embeddingSuccessMessage" class="p-3 bg-purple-50 border border-purple-200 text-purple-800 rounded-lg text-xs flex items-center gap-2">
      <Sparkles class="w-4 h-4 text-purple-600 shrink-0" />
      <span>{{ embeddingSuccessMessage }}</span>
    </div>

    <!-- Информационная панель статуса базы реестра -->
    <div class="bg-white p-4.5 rounded-xl border border-slate-200 shadow-2xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
          <Landmark class="w-5 h-5" />
        </div>
        <div>
          <div class="text-xs text-slate-500 font-medium">Статус базы данных реестра:</div>
          <div class="text-sm font-bold text-slate-900 flex items-center gap-2 mt-0.5">
            <span>Всего записей в базе: {{ totalRecords !== null ? totalRecords.toLocaleString('ru-RU') : 'Синхронизация...' }}</span>
            <span class="text-slate-300">•</span>
            <span class="text-emerald-600 font-semibold flex items-center gap-1 text-xs">
              <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
              Актуально
            </span>
          </div>
        </div>
      </div>

      <div class="text-xs text-slate-500 flex items-center gap-1.5 bg-slate-50 px-3 py-2 rounded-lg border border-slate-200">
        <Calendar class="w-4 h-4 text-slate-400" />
        <span>Последнее обновление:</span>
        <span class="font-semibold text-slate-800 font-mono">
          {{ lastUpdated ? new Date(lastUpdated).toLocaleString('ru-RU') : 'Не синхронизировано' }}
        </span>
      </div>
    </div>

    <!-- Уведомление об успешной синхронизации -->
    <div v-if="syncSuccess" class="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center gap-2">
      <CheckCircle2 class="w-4 h-4 text-emerald-600 shrink-0" />
      <span>Реестр отечественного ПО успешно синхронизирован с Минцифры РФ! База обновлена.</span>
    </div>

    <!-- Поле поиска по реестру -->
    <div class="bg-white p-3 rounded-xl border border-slate-200 w-full sm:w-96">
      <Input
        v-model="searchQuery"
        placeholder="Поиск по названию ПО, номеру реестра, вендору..."
      />
    </div>

    <!-- Таблица записей реестра -->
    <Card noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Рег. номер</th>
              <th class="py-3 px-4">Наименование программного обеспечения</th>
              <th class="py-3 px-4">Класс ПО</th>
              <th class="py-3 px-4">Правообладатель (Вендор)</th>
              <th class="py-3 px-4 text-center">Относится к ИИ</th>
              <th class="py-3 px-4 text-right">Сайт</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="item in filteredItems" :key="item.id" class="hover:bg-slate-50/80 transition-colors">
              <td class="py-3 px-4 font-mono font-bold text-blue-600">
                № {{ item.reg_number }}
              </td>
              <td class="py-3 px-4 font-semibold text-slate-900">
                <div>{{ item.name }}</div>
                <div v-if="item.alternative_names" class="text-[10px] text-slate-400 font-normal">
                  Синонимы: {{ item.alternative_names }}
                </div>
              </td>
              <td class="py-3 px-4 text-slate-700">
                {{ item.software_class || '—' }}
              </td>
              <td class="py-3 px-4 text-slate-600">
                <div>{{ item.vendor_name || '—' }}</div>
                <div v-if="item.vendor_inn" class="text-[10px] text-slate-400 font-mono">
                  ИНН: {{ item.vendor_inn }}
                </div>
              </td>
              <td class="py-3 px-4 text-center">
                <Badge v-if="item.is_ai" variant="info" size="sm">
                  <Sparkles class="w-3 h-3 mr-1" />
                  ИИ-технология
                </Badge>
                <span v-else class="text-slate-400 text-[11px]">Базовое ПО</span>
              </td>
              <td class="py-3 px-4 text-right">
                <a
                  v-if="item.documentation_url"
                  :href="item.documentation_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-blue-600 hover:text-blue-800 inline-flex items-center gap-1 font-medium text-[11px]"
                >
                  <span>Сайт</span>
                  <ExternalLink class="w-3 h-3" />
                </a>
                <span v-else class="text-slate-400">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>
