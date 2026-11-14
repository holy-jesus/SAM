<script setup lang="ts">
import { onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useSamStore } from '@/stores/sam';
import {
  Monitor,
  Users,
  Laptop,
  AlertTriangle,
  ShieldCheck,
  TrendingUp,
  Wand2,
  UploadCloud,
  FileText,
  Bot,
  ArrowRight,
  RefreshCw,
  CheckCircle2,
  Check,
  AlertOctagon,
  Clock,
  Sparkles,
} from 'lucide-vue-next';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';

const router = useRouter();
const samStore = useSamStore();

onMounted(() => {
  samStore.loadDashboard();
});

// Форматирование чисел в денежный формат рублей
function formatRub(val?: number) {
  if (val === undefined || val === null) return '0 ₽';
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(val);
}

// Расчёт процента ПК, закреплённых за сотрудниками
const assignedPercentage = computed(() => {
  const total = samStore.summary?.total_computers || samStore.computers.length || 0;
  if (!total) return 0;
  const assigned = samStore.computers.filter((c) => c.employee_id).length;
  return Math.round((assigned / total) * 100);
});

// Расчёт процента софта, сопоставленного с эталонным каталогом
const catalogCoveragePercentage = computed(() => {
  const total = samStore.summary?.total_installed_software_count || samStore.installedSoftware.length || 0;
  if (!total) return 0;
  const matched = samStore.installedSoftware.filter((s) => s.catalog_software_id).length;
  return Math.round((matched / total) * 100);
});

// Обработчик быстрого вызова умного мэтчинга для нераспознанного софта
function handleSmartMatchShortcut() {
  const unverified = samStore.installedSoftware.find((s) => !s.catalog_software_id);
  samStore.triggerSmartMatch(unverified?.raw_display_name || '');
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Сводка системы (Дашборд SAM)</h1>
        <p class="text-xs text-slate-500 mt-1">
          Оперативный статус корпоративных рабочих станций, лицензионного комплаенса и финансовых рисков
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :loading="samStore.loading" @click="samStore.loadDashboard">
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          Обновить
        </Button>
        <Button variant="primary" size="sm" @click="router.push('/import')">
          <UploadCloud class="w-3.5 h-3.5 mr-1" />
          Загрузить дамп
        </Button>
      </div>
    </div>

    <!-- Плитки ключевых метрик (стиль Home Assistant) -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- Плитка: Рабочие станции -->
      <Card class="hover:border-blue-300 transition-all">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-slate-500 block">Рабочие станции</span>
            <div class="text-2xl font-bold text-slate-900 mt-1">
              {{ samStore.summary?.total_computers ?? 0 }}
            </div>
            <div class="flex items-center gap-2 mt-2 text-xs">
              <span class="inline-flex items-center gap-1 text-emerald-600 font-medium">
                <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                {{ samStore.summary?.online_computers ?? 0 }} в сети
              </span>
              <span class="text-slate-300">•</span>
              <span class="inline-flex items-center gap-1 text-slate-500">
                <span class="w-2 h-2 rounded-full bg-slate-300"></span>
                {{ samStore.summary?.offline_computers ?? 0 }} офлайн
              </span>
            </div>
          </div>
          <div class="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <Monitor class="w-6 h-6" />
          </div>
        </div>
      </Card>

      <!-- Плитка: Сотрудники компании -->
      <Card class="hover:border-indigo-300 transition-all">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-slate-500 block">Сотрудники компании</span>
            <div class="text-2xl font-bold text-slate-900 mt-1">
              {{ samStore.summary?.total_employees ?? 0 }}
            </div>
            <p class="text-xs text-slate-500 mt-2">
              Закреплено за ПК: <span class="font-semibold text-slate-700">{{ assignedPercentage }}%</span>
            </p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Users class="w-6 h-6" />
          </div>
        </div>
      </Card>

      <!-- Плитка: Установленное ПО -->
      <Card class="hover:border-purple-300 transition-all">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-slate-500 block">Установленное ПО</span>
            <div class="text-2xl font-bold text-slate-900 mt-1">
              {{ samStore.summary?.total_installed_software_count ?? 0 }}
            </div>
            <p class="text-xs text-slate-500 mt-2">
              В эталонном каталоге: <span class="font-semibold text-slate-700">{{ catalogCoveragePercentage }}%</span>
            </p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
            <Laptop class="w-6 h-6" />
          </div>
        </div>
      </Card>

      <!-- Плитка: Финансовый штрафной риск -->
      <Card v-if="samStore.summary?.active_compliance_issues_count" class="border-red-200 bg-red-50/20 hover:border-red-300 transition-all">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-red-600 block flex items-center gap-1">
              <AlertTriangle class="w-3.5 h-3.5 text-red-600" /> Финансовый штрафной риск
            </span>
            <div class="text-2xl font-bold text-red-700 mt-1">
              {{ formatRub(samStore.summary?.total_financial_risk_rub ?? 0) }}
            </div>
            <p class="text-xs text-red-600 font-medium mt-2">
              {{ samStore.summary?.active_compliance_issues_count ?? 0 }} критических нарушений
            </p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-red-100 text-red-600 flex items-center justify-center">
            <AlertOctagon class="w-6 h-6" />
          </div>
        </div>
      </Card>

      <!-- Плитка: Отсутствие финансовых рисков -->
      <Card v-else class="border-emerald-200 bg-emerald-50/20 hover:border-emerald-300 transition-all">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-emerald-700 block flex items-center gap-1">
              <Check class="w-3.5 h-3.5 text-emerald-600" /> Финансовые риски отсутствуют
            </span>
            <div class="text-2xl font-bold text-emerald-800 mt-1">
              0 ₽
            </div>
            <p class="text-xs text-emerald-700 font-medium mt-2">
              Все лицензии соответствуют нормам
            </p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center">
            <Check class="w-6 h-6" />
          </div>
        </div>
      </Card>
    </div>

    <!-- Панель быстрых действий (в стиле Home Assistant) -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <button
        type="button"
        class="p-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-3 transition cursor-pointer text-left shadow-2xs"
        @click="router.push('/compliance')"
      >
        <div class="w-9 h-9 rounded-lg bg-red-100 text-red-700 flex items-center justify-center shrink-0">
          <AlertTriangle class="w-5 h-5" />
        </div>
        <div>
          <h4 class="text-xs font-semibold text-slate-900 leading-tight">Комплаенс-контроль</h4>
          <p class="text-[10px] text-slate-500">Баланс и риски дефицита</p>
        </div>
      </button>

      <button
        type="button"
        class="p-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-3 transition cursor-pointer text-left shadow-2xs"
        @click="handleSmartMatchShortcut"
      >
        <div class="w-9 h-9 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
          <Wand2 class="w-5 h-5" />
        </div>
        <div>
          <h4 class="text-xs font-semibold text-slate-900 leading-tight">Умный мэтчинг</h4>
          <p class="text-[10px] text-slate-500">Нормализация процессов ИИ</p>
        </div>
      </button>

      <button
        type="button"
        class="p-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-3 transition cursor-pointer text-left shadow-2xs"
        @click="samStore.triggerEulaAnalysis()"
      >
        <div class="w-9 h-9 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
          <FileText class="w-5 h-5" />
        </div>
        <div>
          <h4 class="text-xs font-semibold text-slate-900 leading-tight">Анализ EULA</h4>
          <p class="text-[10px] text-slate-500">Аудит коммерческих прав</p>
        </div>
      </button>

      <button
        type="button"
        class="p-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-3 transition cursor-pointer text-left shadow-2xs"
        @click="samStore.toggleAIChat()"
      >
        <div class="w-9 h-9 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center shrink-0">
          <Bot class="w-5 h-5" />
        </div>
        <div>
          <h4 class="text-xs font-semibold text-slate-900 leading-tight">Чат ИТ-директора</h4>
          <p class="text-[10px] text-slate-500">Запросы на естественном языке</p>
        </div>
      </button>
    </div>

    <!-- Сетка из двух колонок: лента инцидентов и сводка -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Левая колонка: активные инциденты комплаенса -->
      <div class="lg:col-span-2 space-y-4">
        <Card title="Критические инциденты и предупреждения комплаенса">
          <template #actions>
            <Button variant="ghost" size="sm" @click="router.push('/compliance')">
              Все нарушения
              <ArrowRight class="w-3.5 h-3.5 ml-1" />
            </Button>
          </template>

          <div v-if="samStore.alerts.length === 0" class="text-xs text-slate-500 text-center py-8">
            Нарушений комплаенса не обнаружено. Все лицензии соответствуют установкам.
          </div>

          <div v-else class="space-y-3">
            <div
              v-for="alert in samStore.alerts"
              :key="alert.id"
              class="p-4 rounded-xl border transition-all"
              :class="[
                alert.severity === 'critical'
                  ? 'bg-red-50/50 border-red-200'
                  : alert.severity === 'warning'
                  ? 'bg-amber-50/50 border-amber-200'
                  : 'bg-blue-50/50 border-blue-200',
              ]"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="flex items-start gap-3">
                  <div
                    class="p-2 rounded-lg mt-0.5 shrink-0"
                    :class="[
                      alert.severity === 'critical'
                        ? 'bg-red-100 text-red-700'
                        : alert.severity === 'warning'
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-blue-100 text-blue-700',
                    ]"
                  >
                    <AlertOctagon v-if="alert.severity === 'critical'" class="w-4 h-4" />
                    <AlertTriangle v-else-if="alert.severity === 'warning'" class="w-4 h-4" />
                    <Clock v-else class="w-4 h-4" />
                  </div>
                  <div>
                    <div class="flex items-center gap-2 flex-wrap">
                      <h4 class="text-sm font-semibold text-slate-900">{{ alert.title }}</h4>
                      <Badge
                        :variant="alert.severity === 'critical' ? 'destructive' : alert.severity === 'warning' ? 'warning' : 'info'"
                        size="sm"
                      >
                        {{ alert.severity === 'critical' ? 'Критический' : alert.severity === 'warning' ? 'Предупреждение' : 'Информация' }}
                      </Badge>
                    </div>
                    <p class="text-xs text-slate-600 mt-1 leading-relaxed">{{ alert.description }}</p>
                    <div class="flex items-center gap-3 mt-2 text-[11px] text-slate-500">
                      <span v-if="alert.computer_hostname" class="font-mono bg-white px-2 py-0.5 rounded border border-slate-200">
                        {{ alert.computer_hostname }}
                      </span>
                      <span>{{ new Date(alert.created_at).toLocaleString('ru-RU') }}</span>
                    </div>
                  </div>
                </div>

                <div v-if="alert.financial_risk_amount > 0" class="text-right shrink-0">
                  <span class="text-[10px] text-slate-400 block font-medium">Сумма риска:</span>
                  <span class="text-xs font-bold text-red-600 font-mono">
                    {{ formatRub(alert.financial_risk_amount) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Правая колонка: баланс лицензий и компоненты платформы -->
      <div class="space-y-6">
        <!-- Виджет баланса ключевых лицензий -->
        <Card title="Баланс ключевых лицензий">
          <template #actions>
            <Button variant="ghost" size="sm" @click="router.push('/compliance')">Детали</Button>
          </template>

          <div v-if="samStore.balance.length === 0" class="text-xs text-slate-500 text-center py-6">
            Лицензии ещё не внесены в систему
          </div>

          <div v-else class="space-y-4">
            <div v-for="item in samStore.balance.slice(0, 4)" :key="item.software_id" class="space-y-1.5">
              <div class="flex items-center justify-between text-xs">
                <span class="font-semibold text-slate-800 truncate max-w-[170px]" :title="item.software_name">
                  {{ item.software_name }}
                </span>
                <span
                  :class="[
                    'font-mono font-bold',
                    item.balance < 0 ? 'text-red-600' : 'text-emerald-600',
                  ]"
                >
                  {{ item.installed_count }} / {{ item.purchased_count }} ({{ item.balance > 0 ? '+' : '' }}{{ item.balance }})
                </span>
              </div>
              <!-- Прогресс-бар использования лицензий -->
              <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  :class="[
                    'h-full rounded-full transition-all',
                    item.balance < 0 ? 'bg-red-500' : 'bg-emerald-500',
                  ]"
                  :style="{
                    width: item.purchased_count > 0
                      ? Math.min(100, (item.installed_count / item.purchased_count) * 100) + '%'
                      : '100%',
                  }"
                ></div>
              </div>
            </div>
          </div>
        </Card>

        <!-- Карточка статуса компонентов платформы -->
        <Card title="Компоненты платформы">
          <div class="space-y-2.5 text-xs">
            <div class="flex items-center justify-between py-1.5 border-b border-slate-100">
              <span class="text-slate-600">Агент сбора Go (Windows)</span>
              <span class="font-medium text-emerald-600 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                Активен
              </span>
            </div>
            <div class="flex items-center justify-between py-1.5 border-b border-slate-100">
              <span class="text-slate-600">PostgreSQL + pgvector</span>
              <span class="font-medium text-emerald-600 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                Индексация 384d
              </span>
            </div>
            <div class="flex items-center justify-between py-1.5 border-b border-slate-100">
              <span class="text-slate-600">Единый реестр ПО РФ</span>
              <span class="font-medium text-slate-700 font-mono">
                {{ samStore.registryStatus ? samStore.registryStatus.total_records.toLocaleString('ru-RU') + ' записей' : 'Синхронизация...' }}
              </span>
            </div>
            <div class="flex items-center justify-between py-1.5">
              <span class="text-slate-600">ИИ-модули (Мэтчинг / EULA)</span>
              <span class="font-medium text-indigo-600 flex items-center gap-1">
                <Sparkles class="w-3.5 h-3.5" />
                Готовы к работе
              </span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  </div>
</template>
