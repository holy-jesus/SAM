<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useSamStore } from '@/stores/sam';
import { api } from '@/services/api';
import { ComplianceBalanceItem, ComplianceAlert } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import {
  ShieldAlert,
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  RefreshCw,
  Search,
  Filter,
  DollarSign,
  UserX,
  Skull,
  Clock,
  Sparkles,
  ExternalLink,
} from 'lucide-vue-next';

const samStore = useSamStore();

const activeTab = ref<'all' | 'overuse' | 'zombie' | 'prohibited'>('all');
const searchQuery = ref('');
const recalculating = ref(false);
const recalculateSuccess = ref(false);

onMounted(() => {
  samStore.loadDashboard();
});

// Форматирование числовых значений в рубли
function formatRub(val?: number) {
  if (val === undefined || val === null) return '0 ₽';
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(val);
}

// Расчёт общей суммы штрафного риска (дефицит лицензий)
const totalPenaltyRisk = computed(() => {
  return samStore.balance.reduce((sum, item) => sum + (item.total_penalty_risk_rub || 0), 0);
});

// Расчёт финансовых потерь от простаивающего («зомби») софта
const totalZombieLosses = computed(() => {
  return samStore.alerts
    .filter((a) => a.alert_type === 'zombie_software' || a.alert_type === 'commercial_risk')
    .reduce((sum, item) => sum + (item.financial_risk_amount || 0), 0);
});

// Количество активных инцидентов запрещённого ПО
const prohibitedCount = computed(() => {
  return samStore.alerts.filter((a) => a.alert_type === 'prohibited_software').length;
});

// Динамическое текстовое описание дефицита софта
const deficitSoftwareDescription = computed(() => {
  const deficitItems = samStore.balance.filter((b) => b.balance < 0);
  if (!deficitItems.length) return 'Дефицита лицензий не обнаружено. Баланс соблюдён.';
  const details = deficitItems
    .slice(0, 3)
    .map((b) => `${b.software_name} (${b.balance} шт.)`)
    .join(', ');
  return `Установлено больше купленного: ${details}${deficitItems.length > 3 ? ' и др.' : ''}.`;
});

// Динамическое описание для карточки зомби-софта
const zombieDescription = computed(() => {
  const zombieAlerts = samStore.alerts.filter(
    (a) => a.alert_type === 'zombie_software' || a.alert_type === 'commercial_risk'
  );
  if (!zombieAlerts.length) return 'Простаивающего ПО не обнаружено. Лицензии используются эффективно.';
  return `Обнаружено предупреждений: ${zombieAlerts.length}. Софт простаивает или числится за уволенными.`;
});

// Динамическое описание для запрещённого софта
const prohibitedDescription = computed(() => {
  const prohibitedAlerts = samStore.alerts.filter((a) => a.alert_type === 'prohibited_software');
  if (!prohibitedAlerts.length) return 'Запрещённого ПО в сети не обнаружено. Политика безопасности соблюдена.';
  return `Зафиксировано ${prohibitedAlerts.length} инцидентов использования неавторизованного софта.`;
});

// Флаги наличия предупреждений для карточек комплаенса
const hasPenaltyRisk = computed(() => {
  return totalPenaltyRisk.value > 0 || samStore.balance.some((b) => b.balance < 0);
});

const hasZombieLosses = computed(() => {
  return (
    totalZombieLosses.value > 0 ||
    samStore.alerts.some((a) => a.alert_type === 'zombie_software' || a.alert_type === 'commercial_risk')
  );
});

const hasProhibitedRisk = computed(() => {
  return prohibitedCount.value > 0;
});

// Фильтрация таблицы баланса лицензий
const filteredBalance = computed(() => {
  let list = samStore.balance;
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter((b) => b.software_name.toLowerCase().includes(q) || b.vendor?.toLowerCase().includes(q));
  }
  if (activeTab.value === 'overuse') {
    return list.filter((b) => b.balance < 0);
  }
  return list;
});

// Фильтрация журнала инцидентов комплаенса
const filteredAlerts = computed(() => {
  let list = samStore.alerts;
  if (activeTab.value === 'overuse') {
    list = list.filter((a) => a.alert_type === 'license_overuse');
  } else if (activeTab.value === 'zombie') {
    list = list.filter((a) => a.alert_type === 'zombie_software' || a.alert_type === 'commercial_risk');
  } else if (activeTab.value === 'prohibited') {
    list = list.filter((a) => a.alert_type === 'prohibited_software' || a.alert_type === 'shadow_it');
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter((a) => a.title.toLowerCase().includes(q) || a.description.toLowerCase().includes(q));
  }
  return list;
});

// Запуск принудительного перерасчёта всех правил комплаенса на бэкенде
async function triggerRecalculate() {
  recalculating.value = true;
  recalculateSuccess.value = false;
  try {
    await api.recalculateCompliance();
    await samStore.loadDashboard();
    recalculateSuccess.value = true;
    setTimeout(() => {
      recalculateSuccess.value = false;
    }, 2500);
  } finally {
    recalculating.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок экрана -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Комплаенс-контроль ПО</h1>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Расчёт баланса (Куплено vs Установлено), штрафные санкции, «зомби-софт» и выявление запрещённого ПО
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button
          variant="primary"
          size="sm"
          :loading="recalculating"
          @click="triggerRecalculate"
        >
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          Пересчитать комплаенс
        </Button>
      </div>
    </div>

    <!-- Уведомление об успешном перерасчёте -->
    <div v-if="recalculateSuccess" class="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
      <CheckCircle2 class="w-4 h-4 text-emerald-600 shrink-0" />
      <span>Все правила комплаенса и баланс лицензий успешно пересчитаны по актуальным данным хостов!</span>
    </div>

    <!-- Карточки ключевых метрик комплаенса -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- 1. Карточка штрафного риска (дефицит лицензий) -->
      <div
        :class="[
          'p-5 border-2 rounded-xl relative overflow-hidden shadow-2xs transition-colors',
          hasPenaltyRisk
            ? 'bg-red-50 border-red-200'
            : 'bg-emerald-50 border-emerald-200',
        ]"
      >
        <div class="flex items-start justify-between">
          <div>
            <span
              :class="[
                'text-xs font-bold uppercase tracking-wider block',
                hasPenaltyRisk ? 'text-red-700' : 'text-emerald-700',
              ]"
            >
              1. Штрафной риск (Дефицит лицензий)
            </span>
            <div
              :class="[
                'text-2xl font-extrabold mt-1',
                hasPenaltyRisk ? 'text-red-800' : 'text-emerald-800',
              ]"
            >
              {{ formatRub(totalPenaltyRisk) }}
            </div>
            <p
              :class="[
                'text-xs mt-1.5 leading-snug',
                hasPenaltyRisk ? 'text-red-700' : 'text-emerald-700',
              ]"
            >
              {{ deficitSoftwareDescription }}
            </p>
          </div>
          <div
            :class="[
              'p-3 rounded-xl transition-colors',
              hasPenaltyRisk ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700',
            ]"
          >
            <AlertOctagon v-if="hasPenaltyRisk" class="w-6 h-6" />
            <CheckCircle2 v-else class="w-6 h-6" />
          </div>
        </div>
      </div>

      <!-- 2. Карточка финансовых потерь (зомби-софт) -->
      <div
        :class="[
          'p-5 border-2 rounded-xl relative overflow-hidden shadow-2xs transition-colors',
          hasZombieLosses
            ? 'bg-amber-50 border-amber-200'
            : 'bg-emerald-50 border-emerald-200',
        ]"
      >
        <div class="flex items-start justify-between">
          <div>
            <span
              :class="[
                'text-xs font-bold uppercase tracking-wider block',
                hasZombieLosses ? 'text-amber-700' : 'text-emerald-700',
              ]"
            >
              2. Финансовые потери («Зомби-софт»)
            </span>
            <div
              :class="[
                'text-2xl font-extrabold mt-1',
                hasZombieLosses ? 'text-amber-800' : 'text-emerald-800',
              ]"
            >
              {{ formatRub(totalZombieLosses) }}
            </div>
            <p
              :class="[
                'text-xs mt-1.5 leading-snug',
                hasZombieLosses ? 'text-amber-700' : 'text-emerald-700',
              ]"
            >
              {{ zombieDescription }}
            </p>
          </div>
          <div
            :class="[
              'p-3 rounded-xl transition-colors',
              hasZombieLosses ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700',
            ]"
          >
            <UserX v-if="hasZombieLosses" class="w-6 h-6" />
            <CheckCircle2 v-else class="w-6 h-6" />
          </div>
        </div>
      </div>

      <!-- 3. Карточка рисков ИБ и запрещённого ПО -->
      <div
        :class="[
          'p-5 border-2 rounded-xl relative overflow-hidden shadow-2xs transition-colors',
          hasProhibitedRisk
            ? 'bg-slate-900 border-slate-800 text-white'
            : 'bg-emerald-50 border-emerald-200 text-slate-900',
        ]"
      >
        <div class="flex items-start justify-between">
          <div>
            <span
              :class="[
                'text-xs font-bold uppercase tracking-wider block',
                hasProhibitedRisk ? 'text-red-400' : 'text-emerald-700',
              ]"
            >
              3. Риски ИБ и запрещённое ПО
            </span>
            <div
              :class="[
                'text-2xl font-extrabold mt-1',
                hasProhibitedRisk ? 'text-white' : 'text-emerald-800',
              ]"
            >
              {{ prohibitedCount }} инцидентов
            </div>
            <p
              :class="[
                'text-xs mt-1.5 leading-snug',
                hasProhibitedRisk ? 'text-slate-300' : 'text-emerald-700',
              ]"
            >
              {{ prohibitedDescription }}
            </p>
          </div>
          <div
            :class="[
              'p-3 rounded-xl border transition-colors',
              hasProhibitedRisk
                ? 'bg-red-950 text-red-400 border-red-800'
                : 'bg-emerald-100 text-emerald-700 border-emerald-200',
            ]"
          >
            <Skull v-if="hasProhibitedRisk" class="w-6 h-6" />
            <CheckCircle2 v-else class="w-6 h-6" />
          </div>
        </div>
      </div>
    </div>

    <!-- Вкладки фильтрации и строка поиска -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-slate-200 pb-3">
      <!-- Вкладки фильтрации -->
      <div class="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl text-xs font-medium">
        <button
          type="button"
          :class="[
            'px-3 py-1.5 rounded-lg transition-colors cursor-pointer',
            activeTab === 'all' ? 'bg-white text-slate-900 shadow-2xs font-semibold' : 'text-slate-600 hover:text-slate-900',
          ]"
          @click="activeTab = 'all'"
        >
          Сводный баланс и всё
        </button>
        <button
          type="button"
          :class="[
            'px-3 py-1.5 rounded-lg transition-colors cursor-pointer flex items-center gap-1',
            activeTab === 'overuse' ? 'bg-white text-red-700 shadow-2xs font-semibold' : 'text-slate-600 hover:text-slate-900',
          ]"
          @click="activeTab = 'overuse'"
        >
          <span class="w-2 h-2 rounded-full bg-red-500"></span>
          Дефицит и штрафы
        </button>
        <button
          type="button"
          :class="[
            'px-3 py-1.5 rounded-lg transition-colors cursor-pointer flex items-center gap-1',
            activeTab === 'zombie' ? 'bg-white text-amber-700 shadow-2xs font-semibold' : 'text-slate-600 hover:text-slate-900',
          ]"
          @click="activeTab = 'zombie'"
        >
          <span class="w-2 h-2 rounded-full bg-amber-500"></span>
          Зомби-софт и уволенные
        </button>
        <button
          type="button"
          :class="[
            'px-3 py-1.5 rounded-lg transition-colors cursor-pointer flex items-center gap-1',
            activeTab === 'prohibited' ? 'bg-white text-slate-900 shadow-2xs font-semibold' : 'text-slate-600 hover:text-slate-900',
          ]"
          @click="activeTab = 'prohibited'"
        >
          <span class="w-2 h-2 rounded-full bg-slate-900"></span>
          Запрещённое ПО
        </button>
      </div>

      <!-- Поле поиска -->
      <div class="w-full sm:w-72">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по названию ПО..."
        />
      </div>
    </div>

    <!-- Раздел 1: Таблица баланса лицензий (Куплено vs Установлено) -->
    <Card title="Баланс лицензий: Куплено vs Установлено по факту" noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Программное обеспечение</th>
              <th class="py-3 px-4">Тип лицензии</th>
              <th class="py-3 px-4 text-center">Куплено</th>
              <th class="py-3 px-4 text-center">Установлено</th>
              <th class="py-3 px-4 text-center">Баланс мест</th>
              <th class="py-3 px-4 text-right">Стоимость 1 шт.</th>
              <th class="py-3 px-4 text-right">Сумма штрафного риска</th>
              <th class="py-3 px-4 text-center">Статус</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr
              v-for="row in filteredBalance"
              :key="row.software_id"
              :class="[
                'hover:bg-slate-50/80 transition-colors',
                row.balance < 0 ? 'bg-red-50/30' : '',
              ]"
            >
              <td class="py-3 px-4 font-semibold text-slate-900">
                <div class="flex items-center gap-2">
                  <span>{{ row.software_name }}</span>
                  <Badge v-if="row.is_prohibited" variant="destructive" size="sm">ЗАПРЕЩЕНО</Badge>
                </div>
                <span class="text-[10px] text-slate-400 block font-normal">{{ row.vendor }}</span>
              </td>
              <td class="py-3 px-4 text-slate-600">
                {{ row.license_type }}
              </td>
              <td class="py-3 px-4 text-center font-mono font-semibold text-slate-700">
                {{ row.purchased_count }}
              </td>
              <td class="py-3 px-4 text-center font-mono font-semibold text-slate-900">
                {{ row.installed_count }}
              </td>
              <td class="py-3 px-4 text-center">
                <span
                  :class="[
                    'font-mono font-bold px-2 py-0.5 rounded-full text-xs inline-block',
                    row.balance < 0
                      ? 'bg-red-100 text-red-700 border border-red-200'
                      : row.balance === 0
                      ? 'bg-slate-100 text-slate-700'
                      : 'bg-emerald-100 text-emerald-700 border border-emerald-200',
                  ]"
                >
                  {{ row.balance > 0 ? '+' : '' }}{{ row.balance }}
                </span>
              </td>
              <td class="py-3 px-4 text-right font-mono text-slate-600">
                {{ formatRub(row.unit_cost) }}
              </td>
              <td class="py-3 px-4 text-right font-mono font-bold">
                <span :class="row.total_penalty_risk_rub > 0 ? 'text-red-600' : 'text-slate-400'">
                  {{ formatRub(row.total_penalty_risk_rub) }}
                </span>
              </td>
              <td class="py-3 px-4 text-center">
                <Badge
                  :variant="row.balance < 0 ? 'destructive' : row.balance === 0 ? 'default' : 'success'"
                  size="sm"
                >
                  {{ row.balance < 0 ? 'Критический дефицит' : row.balance === 0 ? 'Точный баланс' : 'Норма' }}
                </Badge>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Раздел 2: Детальный журнал инцидентов комплаенса -->
    <Card title="Журнал инцидентов и угроз комплаенса">
      <div v-if="filteredAlerts.length === 0" class="text-xs text-slate-500 text-center py-6">
        Инцидентов в выбранной категории не обнаружено
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="alert in filteredAlerts"
          :key="alert.id"
          class="p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 transition-all"
          :class="[
            alert.severity === 'critical'
              ? 'bg-red-50/40 border-red-200'
              : alert.severity === 'warning'
              ? 'bg-amber-50/40 border-amber-200'
              : 'bg-blue-50/40 border-blue-200',
          ]"
        >
          <div class="space-y-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-semibold text-slate-900 text-sm">{{ alert.title }}</span>
              <Badge
                :variant="alert.severity === 'critical' ? 'destructive' : alert.severity === 'warning' ? 'warning' : 'info'"
                size="sm"
              >
                {{ alert.severity === 'critical' ? 'Критический риск' : 'Предупреждение' }}
              </Badge>
            </div>
            <p class="text-xs text-slate-600 leading-relaxed">{{ alert.description }}</p>
            <div class="flex items-center gap-3 text-[11px] text-slate-500 pt-1">
              <span v-if="alert.computer_hostname" class="font-mono bg-white px-2 py-0.5 rounded border border-slate-200">
                Хост: {{ alert.computer_hostname }}
              </span>
              <span>Время фиксации: {{ new Date(alert.created_at).toLocaleString('ru-RU') }}</span>
            </div>
          </div>

          <div class="text-right shrink-0">
            <div v-if="alert.financial_risk_amount > 0">
              <span class="text-[10px] text-slate-400 block">Потенциальный ущерб:</span>
              <span class="text-sm font-bold text-red-600 font-mono">
                {{ formatRub(alert.financial_risk_amount) }}
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              class="mt-2 text-xs"
              @click="samStore.toggleAIChat()"
            >
              Спросить ИИ
            </Button>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>
