<script setup lang="ts">
import { ref, watch } from 'vue';
import { useSamStore } from '@/stores/sam';
import { api } from '@/services/api';
import { EulaAnalysisResult } from '@/types';
import Modal from '@/components/ui/Modal.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import { FileText, ShieldAlert, CheckCircle2, AlertOctagon, HelpCircle, Sparkles } from 'lucide-vue-next';

const samStore = useSamStore();

const eulaText = ref('');
const loading = ref(false);
const result = ref<EulaAnalysisResult | null>(null);

// Типовые предустановленные примеры для демонстрации
const presetTemplates = [
  {
    name: 'Oracle Java OTN (Коммерческий риск)',
    text: `Oracle Technology Network License Agreement for Oracle Java SE.
You may download and use the Software only for personal use, development, testing, prototyping and demonstrating your application.
Commercial use in production or enterprise operations is strictly prohibited without a separate paid commercial subscription. Any enterprise deployment is subject to compliance verification and back-billing of licensing fees.`,
  },
  {
    name: 'AnyDesk / TeamViewer Free (Запрет коммерции)',
    text: `Personal, Non-Commercial Use Agreement.
The free version is provided exclusively for personal and non-commercial purposes.
Use in a commercial, business, professional, educational or corporate environment requires an active paid commercial license. Automatic detection algorithms are deployed to flag connections originating from corporate IP networks.`,
  },
  {
    name: 'SaaS с автопродлением (Скрытые списания)',
    text: `Subscription and Trial Terms.
The free trial period lasts 14 days. Unless explicitly cancelled at least 48 hours prior to the expiration of the trial term, this subscription automatically converts into an annual recurring enterprise plan at $1,200/year, billed immediately to the provided corporate payment method with no refunds.`,
  },
];

watch(
  () => samStore.eulaModalOpen,
  (val) => {
    if (val && !eulaText.value) {
      eulaText.value = presetTemplates[0].text;
    }
  }
);

// Запуск аудита текста лицензионного соглашения
async function analyze() {
  if (!eulaText.value.trim()) return;
  loading.value = true;
  result.value = null;
  try {
    result.value = await api.analyzeEula(eulaText.value, samStore.eulaModalLicenseId);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Modal
    v-model="samStore.eulaModalOpen"
    title="ИИ «Анализатор лицензий и EULA» (Кейс Б)"
    subtitle="Автоматический аудит условий использования: коммерческие права, скрытые подписки и риски ИБ"
    maxWidth="4xl"
  >
    <div class="space-y-4">
      <!-- Готовые шаблоны лицензий для быстрого тестирования -->
      <div class="flex items-center gap-2 flex-wrap text-xs">
        <span class="text-slate-500 font-medium">Быстрые примеры:</span>
        <button
          v-for="tmpl in presetTemplates"
          :key="tmpl.name"
          type="button"
          class="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md transition-colors cursor-pointer"
          @click="eulaText = tmpl.text; analyze()"
        >
          {{ tmpl.name }}
        </button>
      </div>

      <!-- Текстовое поле ввода условий соглашения -->
      <div>
        <label class="block text-xs font-medium text-slate-700 mb-1">
          Текст лицензионного соглашения (EULA / License Terms)
        </label>
        <textarea
          v-model="eulaText"
          rows="6"
          placeholder="Вставьте сюда текст лицензионного соглашения софта..."
          class="w-full px-3 py-2 text-xs font-mono bg-white border border-slate-300 rounded-lg shadow-2xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />
      </div>

      <div class="flex justify-end">
        <Button variant="primary" :loading="loading" @click="analyze">
          <Sparkles class="w-4 h-4 mr-1.5" />
          Запустить анализ EULA
        </Button>
      </div>

      <!-- Результаты анализа соглашения -->
      <div v-if="result" class="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-xs space-y-4 p-5">
        <!-- Индикаторы рисков и коммерческих прав -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div class="p-3 rounded-lg border bg-slate-50 flex items-center justify-between">
            <div>
              <span class="text-xs text-slate-500 block">Коммерческое использование</span>
              <span :class="['text-sm font-semibold', result.commercial_use_allowed ? 'text-emerald-700' : 'text-red-600']">
                {{ result.commercial_use_allowed ? 'Разрешено в компании' : 'ЗАПРЕЩЕНО (Personal Only)' }}
              </span>
            </div>
            <component
              :is="result.commercial_use_allowed ? CheckCircle2 : AlertOctagon"
              :class="['w-6 h-6', result.commercial_use_allowed ? 'text-emerald-600' : 'text-red-600']"
            />
          </div>

          <div class="p-3 rounded-lg border bg-slate-50 flex items-center justify-between">
            <div>
              <span class="text-xs text-slate-500 block">Уровень комплаенс-риска</span>
              <span class="text-sm font-semibold capitalize" :class="result.risk_level === 'critical' ? 'text-red-600' : result.risk_level === 'high' ? 'text-orange-600' : 'text-emerald-600'">
                {{ result.risk_level === 'critical' ? 'Критический риск' : result.risk_level === 'high' ? 'Высокий риск' : 'Низкий риск' }}
              </span>
            </div>
            <ShieldAlert class="w-6 h-6 text-amber-600" />
          </div>

          <div class="p-3 rounded-lg border bg-slate-50 flex items-center justify-between">
            <div>
              <span class="text-xs text-slate-500 block">Скрытые подписки / автоплатежи</span>
              <span :class="['text-sm font-semibold', result.has_auto_renewal ? 'text-amber-700' : 'text-slate-700']">
                {{ result.has_auto_renewal ? 'Обнаружены автосписания' : 'Нет автопродления' }}
              </span>
            </div>
            <HelpCircle class="w-6 h-6 text-slate-400" />
          </div>
        </div>

        <!-- Экспертное резюме юридического аудитора ИИ -->
        <div
          :class="[
            'p-4 rounded-lg border text-xs leading-relaxed',
            result.commercial_use_allowed
              ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
              : 'bg-red-50/70 border-red-200 text-red-900',
          ]"
        >
          <div class="font-semibold mb-1 flex items-center gap-1.5">
            <Sparkles class="w-4 h-4 text-indigo-600" />
            Резюме юридического аудитора ИИ:
          </div>
          {{ result.summary_ru }}
        </div>

        <!-- Перечень выявленных ограничений -->
        <div>
          <h5 class="text-xs font-semibold text-slate-800 mb-2">Ключевые юридические ограничения:</h5>
          <ul class="space-y-1.5 text-xs text-slate-600">
            <li v-for="(restr, i) in result.key_restrictions" :key="i" class="flex items-start gap-2">
              <span class="text-red-500 font-bold shrink-0">•</span>
              <span>{{ restr }}</span>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <template #footer>
      <Button variant="outline" size="sm" @click="samStore.eulaModalOpen = false">Закрыть</Button>
    </template>
  </Modal>
</template>
