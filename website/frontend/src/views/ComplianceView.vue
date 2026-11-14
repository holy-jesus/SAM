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

function formatRub(val?: number) {
  if (val === undefined || val === null) return '0 ₽';
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(val);
}

// Calculate summary numbers
const totalPenaltyRisk = computed(() => {
  return samStore.balance.reduce((sum, item) => sum + (item.total_penalty_risk_rub || 0), 0);
});

const totalZombieLosses = computed(() => {
  return 25000 + 18000; // MS Office + Java on dismissed PC
});

const prohibitedCount = computed(() => {
  return samStore.alerts.filter((a) => a.alert_type === 'prohibited_software').length;
});

// Filtered balance items
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

// Filtered alerts
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
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Комплаенс-контроль ПО</h1>
          <span class="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-bold border border-red-200">
            Ключевой экран SAM
          </span>
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

    <!-- Success Toast -->
    <div v-if="recalculateSuccess" class="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
      <CheckCircle2 class="w-4 h-4 text-emerald-600 shrink-0" />
      <span>Все правила комплаенса и баланс лицензий успешно пересчитаны по актуальным данным хостов!</span>
    </div>

    <!-- Critical Risk Metric Banners -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- 1. Penalty Risk Card -->
      <div class="p-5 bg-red-50 border-2 border-red-200 rounded-xl relative overflow-hidden shadow-2xs">
        <div class="flex items-start justify-between">
          <div>
            <span class="text-xs font-bold uppercase text-red-700 tracking-wider block">
              1. Штрафной риск (Дефицит лицензий)
            </span>
            <div class="text-2xl font-extrabold text-red-800 mt-1">
              {{ formatRub(totalPenaltyRisk) }}
            </div>
            <p class="text-xs text-red-700 mt-1.5 leading-snug">
              Установлено больше, чем закуплено: MS Office (+20 ПК), Oracle Java (+8 ПК).
            </p>
          </div>
          <div class="p-3 bg-red-100 text-red-700 rounded-xl">
            <AlertOctagon class="w-6 h-6" />
          </div>
        </div>
      </div>

      <!-- 2. Zombie Software & Dismissed Employees Card -->
      <div class="p-5 bg-amber-50 border-2 border-amber-200 rounded-xl relative overflow-hidden shadow-2xs">
        <div class="flex items-start justify-between">
          <div>
            <span class="text-xs font-bold uppercase text-amber-700 tracking-wider block">
              2. Финансовые потери («Зомби-софт»)
            </span>
            <div class="text-2xl font-extrabold text-amber-800 mt-1">
              {{ formatRub(totalZombieLosses) }}
            </div>
            <p class="text-xs text-amber-700 mt-1.5 leading-snug">
              ПО простаивает >90 дней или числится на рабочих станциях уволенных сотрудников.
            </p>
          </div>
          <div class="p-3 bg-amber-100 text-amber-700 rounded-xl">
            <UserX class="w-6 h-6" />
          </div>
        </div>
      </div>

      <!-- 3. Prohibited & Legal Risks Card -->
      <div class="p-5 bg-slate-900 border-2 border-slate-800 text-white rounded-xl relative overflow-hidden shadow-2xs">
        <div class="flex items-start justify-between">
          <div>
            <span class="text-xs font-bold uppercase text-red-400 tracking-wider block">
              3. Риски ИБ и запрещённое ПО
            </span>
            <div class="text-2xl font-extrabold text-white mt-1">
              {{ prohibitedCount }} инцидента
            </div>
            <p class="text-xs text-slate-300 mt-1.5 leading-snug">
              Обнаружены торрент-клиенты и неавторизованное использование Personal лицензий.
            </p>
          </div>
          <div class="p-3 bg-red-950 text-red-400 rounded-xl border border-red-800">
            <Skull class="w-6 h-6" />
          </div>
        </div>
      </div>
    </div>

    <!-- Interactive Navigation Tabs & Filter Bar -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-slate-200 pb-3">
      <!-- Tabs -->
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

      <!-- Search Input -->
      <div class="w-full sm:w-72">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по названию ПО..."
        />
      </div>
    </div>

    <!-- Section 1: License Balance Table (Куплено vs Установлено) -->
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

    <!-- Section 2: Detailed Compliance Alerts Log -->
    <Card title="Журнал инцидентов и угроз комплаенса">
      <div class="space-y-3">
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
