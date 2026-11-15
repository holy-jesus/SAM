<script setup lang="ts">
import { ref, watch } from 'vue';
import { useSamStore } from '@/stores/sam';
import { api } from '@/services/api';
import { SmartMatchResult } from '@/types';
import Modal from '@/components/ui/Modal.vue';
import Button from '@/components/ui/Button.vue';
import Input from '@/components/ui/Input.vue';
import Badge from '@/components/ui/Badge.vue';
import { Wand2, CheckCircle2, AlertTriangle, ArrowRight, Sparkles } from 'lucide-vue-next';

const samStore = useSamStore();

const processInput = ref('');
const loading = ref(false);
const batchLoading = ref(false);
const result = ref<SmartMatchResult | null>(null);
const successMessage = ref('');

watch(
  () => samStore.smartMatchProcessTarget,
  (val) => {
    if (val) {
      processInput.value = val;
      runMatch();
    }
  }
);

// Запуск семантического сопоставления процесса
async function runMatch() {
  if (!processInput.value.trim()) return;
  loading.value = true;
  result.value = null;
  successMessage.value = '';
  try {
    result.value = await api.smartMatchSoftware(processInput.value.trim());
  } finally {
    loading.value = false;
  }
}

// Запуск фоновой массовой нормализации всех нераспознанных процессов в БД
async function runBatchNormalize() {
  batchLoading.value = true;
  try {
    const res = await api.batchNormalize();
    successMessage.value = `Успешно нормализовано ${res.matched_count} процессов из ${res.normalized_count} нераспознанных в базе через pgvector & LLM!`;
  } finally {
    batchLoading.value = false;
  }
}

// Подтверждение и связывание процесса с каталогом
function approveMatch() {
  if (!result.value) return;
  successMessage.value = `Сопоставление для "${result.value.raw_process_name}" сохранено и верифицировано в каталоге!`;
  setTimeout(() => {
    samStore.smartMatchModalOpen = false;
  }, 1200);
}
</script>

<template>
  <Modal
    v-model="samStore.smartMatchModalOpen"
    title="ИИ «Умный мэтчинг» процессов (Кейс А)"
    subtitle="Семантическая нормализация грязных имён процессов из ОС в официальный каталог (pgvector + LLM)"
    maxWidth="2xl"
  >
    <div class="space-y-5">
      <!-- Поле ввода имени процесса -->
      <div class="flex gap-2 items-end">
        <div class="flex-1">
          <Input
            v-model="processInput"
            label="Грязное имя процесса / исполняемого файла из дампа ОС"
            placeholder="например: studio_visual_2022_setup_x64.exe, chrome.exe, pycharm64.exe"
            @keydown.enter="runMatch"
          />
        </div>
        <Button variant="primary" :loading="loading" @click="runMatch">
          <Wand2 class="w-4 h-4 mr-1.5" />
          Мэтчинг
        </Button>
      </div>

      <!-- Карточка результата семантического анализа -->
      <div v-if="result" class="border border-blue-100 bg-blue-50/40 rounded-xl p-4.5 space-y-4">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-2">
            <Sparkles class="w-5 h-5 text-blue-600" />
            <h4 class="font-semibold text-slate-900 text-sm">Результат семантического анализа</h4>
          </div>
          <Badge
            :variant="result.confidence >= 0.9 ? 'success' : result.confidence >= 0.75 ? 'warning' : 'destructive'"
            size="md"
          >
            Уверенность ИИ: {{ Math.round(result.confidence * 100) }}%
          </Badge>
        </div>

        <!-- Визуализация сопоставления процесса и каталога -->
        <div class="flex items-center gap-3 bg-white p-3 rounded-lg border border-slate-200 text-xs font-mono">
          <div class="text-slate-600 truncate flex-1 font-semibold text-red-600">
            {{ result.raw_process_name }}
          </div>
          <ArrowRight class="w-4 h-4 text-slate-400 shrink-0" />
          <div class="text-emerald-700 truncate flex-1 font-semibold text-sm font-sans">
            {{ result.matched_name }}
          </div>
        </div>

        <div class="text-xs text-slate-600 space-y-1">
          <p><span class="font-medium text-slate-700">Вендор:</span> {{ result.vendor || 'Корпоративный каталог' }}</p>
          <p v-if="result.matched_version"><span class="font-medium text-slate-700">Определённая версия:</span> <code class="font-mono bg-white px-1.5 py-0.5 rounded border border-slate-200 text-slate-900">{{ result.matched_version }}</code></p>
          <p v-if="result.match_source">
            <span class="font-medium text-slate-700">Ступень конвейера (Источник):</span>
            <span class="font-semibold text-blue-700 ml-1">
              {{
                result.match_source === 'hash' ? 'Шаг 1: Контрольная сумма SHA-256' :
                result.match_source === 'path_heuristic' ? 'Шаг 2: Эвристика пути установки и имени .exe' :
                result.match_source === 'process_signatures' ? 'Шаг 3: Самообучающаяся база сигнатур' :
                result.match_source === 'ru_registry' ? 'Шаг 4: Единый реестр отечественного ПО' :
                result.match_source === 'embedding' ? 'Шаг 5: Векторный семантический поиск (pgvector)' :
                result.match_source === 'wikimedia' ? 'Шаг 6: Wikimedia Semantic Search API' :
                result.match_source === 'openai' ? 'Шаг 7: Нейросеть (OpenAI LLM)' : 'Шаг 8: Локальный каталог'
              }}
            </span>
          </p>
          <p><span class="font-medium text-slate-700">Обоснование ИИ:</span> {{ result.reasoning }}</p>
        </div>

        <div class="flex items-center justify-end gap-2 pt-2 border-t border-blue-100">
          <Button variant="outline" size="sm" @click="samStore.smartMatchModalOpen = false">Отмена</Button>
          <Button variant="success" size="sm" @click="approveMatch">
            <CheckCircle2 class="w-4 h-4 mr-1" />
            Подтвердить и связать с каталогом
          </Button>
        </div>
      </div>

      <!-- Уведомление об успешном результате -->
      <div v-if="successMessage" class="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
        <CheckCircle2 class="w-4 h-4 text-emerald-600 shrink-0" />
        <span>{{ successMessage }}</span>
      </div>

      <!-- Раздел массовой нормализации процессов -->
      <div class="pt-3 border-t border-slate-200 flex items-center justify-between">
        <div>
          <h5 class="text-xs font-semibold text-slate-800">Массовая обработка нераспознанных процессов</h5>
          <p class="text-xs text-slate-500">Автоматически сопоставить все нераспознанные записи в БД через pgvector</p>
        </div>
        <Button variant="secondary" size="sm" :loading="batchLoading" @click="runBatchNormalize">
          <Sparkles class="w-3.5 h-3.5 mr-1 text-indigo-600" />
          Массовая нормализация
        </Button>
      </div>
    </div>
  </Modal>
</template>
