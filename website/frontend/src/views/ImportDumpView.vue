<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '@/services/api';
import { ImportHistoryItem } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileText,
  Layers,
  Sparkles,
} from 'lucide-vue-next';

const fileInput = ref<HTMLInputElement | null>(null);
const history = ref<ImportHistoryItem[]>([]);
const uploading = ref(false);
const dragOver = ref(false);
const uploadResult = ref<any | null>(null);

onMounted(() => {
  loadHistory();
});

async function loadHistory() {
  history.value = await api.getImportHistory();
}

function handleFileSelect(e: Event) {
  const files = (e.target as HTMLInputElement).files;
  if (files && files[0]) {
    uploadFile(files[0]);
  }
}

function handleDrop(e: DragEvent) {
  dragOver.value = false;
  if (e.dataTransfer?.files && e.dataTransfer.files[0]) {
    uploadFile(e.dataTransfer.files[0]);
  }
}

async function uploadFile(file: File) {
  uploading.value = true;
  uploadResult.value = null;
  try {
    const res = await api.uploadDump(file);
    uploadResult.value = res;
    await loadHistory();
  } finally {
    uploading.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div>
      <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Импорт дампа с рабочих станций</h1>
      <p class="text-xs text-slate-500 mt-1">
        Загрузка инвентаризационных отчётов (XLSX, CSV, JSON) в формате эталонного дампа хостов
      </p>
    </div>

    <!-- Область загрузки Drag & Drop -->
    <div
      :class="[
        'border-2 border-dashed rounded-2xl p-8 text-center transition-all bg-white cursor-pointer relative',
        dragOver ? 'border-blue-500 bg-blue-50/50' : 'border-slate-300 hover:border-blue-400',
      ]"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="handleDrop"
      @click="fileInput?.click()"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".xlsx,.csv,.json"
        class="hidden"
        @change="handleFileSelect"
      />

      <div class="max-w-md mx-auto space-y-3">
        <div class="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto shadow-xs">
          <UploadCloud class="w-7 h-7" />
        </div>
        <h3 class="text-base font-bold text-slate-900">
          {{ uploading ? 'Загрузка и обработка файла...' : 'Перетащите файл дампа сюда или нажмите для выбора' }}
        </h3>
        <p class="text-xs text-slate-500 leading-relaxed">
          Поддерживаются форматы: <strong class="text-slate-700">.XLSX</strong>, <strong class="text-slate-700">.CSV</strong>, <strong class="text-slate-700">.JSON</strong>.
          Автоматически создаются хосты по <code class="font-mono text-blue-600">COMPUTERS.SERIAL_NUMBER</code> и выполняется связка софта через pgvector.
        </p>

        <div class="pt-2">
          <Button variant="primary" size="sm" :loading="uploading">
            Выбрать файл на диске
          </Button>
        </div>
      </div>
    </div>

    <!-- Баннер успешной загрузки -->
    <div v-if="uploadResult" class="p-5 bg-emerald-50 border border-emerald-200 rounded-xl space-y-3">
      <div class="flex items-center gap-2 text-emerald-800 font-bold text-sm">
        <CheckCircle2 class="w-5 h-5 text-emerald-600" />
        <span>Дамп «{{ uploadResult.filename }}» успешно загружен и обработан!</span>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div class="bg-white p-3 rounded-lg border border-emerald-200">
          <span class="text-slate-500 block text-[11px]">Строк обработано</span>
          <span class="font-bold text-slate-900 font-mono text-base">{{ uploadResult.total_rows }}</span>
        </div>
        <div class="bg-white p-3 rounded-lg border border-emerald-200">
          <span class="text-slate-500 block text-[11px]">Хостов обновлено</span>
          <span class="font-bold text-slate-900 font-mono text-base">{{ uploadResult.computers_affected }}</span>
        </div>
        <div class="bg-white p-3 rounded-lg border border-emerald-200">
          <span class="text-slate-500 block text-[11px]">Установок софта</span>
          <span class="font-bold text-slate-900 font-mono text-base">{{ uploadResult.software_rows_imported }}</span>
        </div>
        <div class="bg-white p-3 rounded-lg border border-emerald-200">
          <span class="text-slate-500 block text-[11px]">Автоматический мэтчинг</span>
          <span class="font-bold text-emerald-700 font-mono text-base">{{ uploadResult.matched_automatically }}</span>
        </div>
      </div>
    </div>

    <!-- Справочная карточка структуры колонок -->
    <Card title="Требования к структуре колонок файла (Пример дампа с компов.xlsx)">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs font-mono border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold text-[11px]">
              <th class="py-2.5 px-3">COMPUTERS.SERIAL_NUMBER</th>
              <th class="py-2.5 px-3">SOFTWARE.DISPLAYNAME</th>
              <th class="py-2.5 px-3">SOFTWARE.PUBLISHER</th>
              <th class="py-2.5 px-3">SOFTWARE.VERSION</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 text-slate-700">
            <tr>
              <td class="py-2 px-3 text-blue-700 font-semibold">G69ZD5J</td>
              <td class="py-2 px-3">Google Chrome</td>
              <td class="py-2 px-3">Google LLC</td>
              <td class="py-2 px-3">67.208.108</td>
            </tr>
            <tr>
              <td class="py-2 px-3 text-blue-700 font-semibold">B1FG0S2</td>
              <td class="py-2 px-3">7-Zip 19.00 (x64 edition)</td>
              <td class="py-2 px-3">Igor Pavlov</td>
              <td class="py-2 px-3">19.00.00.0</td>
            </tr>
            <tr>
              <td class="py-2 px-3 text-blue-700 font-semibold">B1RG0S2</td>
              <td class="py-2 px-3">Java 8 Update 201</td>
              <td class="py-2 px-3">Oracle Corporation</td>
              <td class="py-2 px-3">8.0.2010.9</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Таблица истории импорта -->
    <Card title="История предыдущих загрузок дампов" noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Имя файла</th>
              <th class="py-3 px-4 text-center">Всего записей</th>
              <th class="py-3 px-4 text-center">Хостов затронуто</th>
              <th class="py-3 px-4 text-center">Сопоставлено ИИ</th>
              <th class="py-3 px-4 text-center">Статус</th>
              <th class="py-3 px-4 text-right">Дата и время</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="item in history" :key="item.id" class="hover:bg-slate-50/80 transition-colors">
              <td class="py-3 px-4 font-semibold text-slate-900 flex items-center gap-2">
                <FileSpreadsheet class="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{{ item.filename }}</span>
              </td>
              <td class="py-3 px-4 text-center font-mono font-medium text-slate-700">
                {{ item.total_rows }}
              </td>
              <td class="py-3 px-4 text-center font-mono font-medium text-slate-700">
                {{ item.computers_affected }}
              </td>
              <td class="py-3 px-4 text-center font-mono font-bold text-emerald-600">
                {{ item.matched_automatically }}
              </td>
              <td class="py-3 px-4 text-center">
                <Badge :variant="item.status === 'success' ? 'success' : 'destructive'" size="sm">
                  {{ item.status === 'success' ? 'Успешно' : 'Ошибка' }}
                </Badge>
              </td>
              <td class="py-3 px-4 text-right text-slate-500 font-mono text-[11px]">
                {{ new Date(item.created_at).toLocaleString('ru-RU') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>
