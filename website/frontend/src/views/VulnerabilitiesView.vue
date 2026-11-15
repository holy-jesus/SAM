<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { VulnerabilityItem, VulnerabilitiesSummary } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import Select from '@/components/ui/Select.vue';
import Modal from '@/components/ui/Modal.vue';
import {
  ShieldAlert,
  Search,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Bug,
  Eye,
  Flame,
  FileSpreadsheet,
  Activity,
  Layers,
} from 'lucide-vue-next';

const vulnerabilities = ref<VulnerabilityItem[]>([]);
const summary = ref<VulnerabilitiesSummary | null>(null);
const loading = ref(false);
const syncing = ref(false);
const syncMessage = ref<string | null>(null);

const searchQuery = ref('');
const severityFilter = ref('all');
const onlyExploitable = ref(false);

// Модальное окно просмотра уязвимости
const isDetailsModalOpen = ref(false);
const selectedVuln = ref<VulnerabilityItem | null>(null);

onMounted(async () => {
  await Promise.all([loadSummary(), loadVulnerabilities()]);
});

async function loadSummary() {
  try {
    summary.value = await api.getVulnerabilitiesSummary();
  } catch (err) {
    console.error('Ошибка загрузки сводки уязвимостей:', err);
  }
}

async function loadVulnerabilities() {
  loading.value = true;
  try {
    const res = await api.getVulnerabilities({
      search: searchQuery.value || undefined,
      severity: severityFilter.value !== 'all' ? severityFilter.value : undefined,
      has_exploit: onlyExploitable.value || undefined,
      limit: 100,
    });
    vulnerabilities.value = res.items || [];
  } finally {
    loading.value = false;
  }
}

async function handleSearch() {
  await loadVulnerabilities();
}

async function handleSync() {
  syncing.value = true;
  syncMessage.value = null;
  try {
    const res = await api.syncVulnerabilities(500);
    syncMessage.value = res.message;
    await Promise.all([loadSummary(), loadVulnerabilities()]);
    setTimeout(() => {
      syncMessage.value = null;
    }, 4500);
  } finally {
    syncing.value = false;
  }
}

function openDetails(item: VulnerabilityItem) {
  selectedVuln.value = item;
  isDetailsModalOpen.value = true;
}

function getCvssBadgeColor(score?: number | null) {
  if (!score) return 'bg-slate-100 text-slate-700';
  if (score >= 9.0) return 'bg-red-100 text-red-800 border-red-200';
  if (score >= 7.0) return 'bg-amber-100 text-amber-800 border-amber-200';
  if (score >= 4.0) return 'bg-yellow-100 text-yellow-800 border-yellow-200';
  return 'bg-blue-100 text-blue-800 border-blue-200';
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Уязвимости безопасности ПО (БДУ ФСТЭК России)</h1>
          <span class="px-2 py-0.5 rounded-full bg-red-50 text-red-700 text-xs font-bold border border-red-200">
            bdu.fstec.ru / vullist.xlsx
          </span>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Банк данных угроз безопасности информации ФСТЭК России, скоринг CVSS, статус эксплойтов и меры нейтрализации
        </p>
      </div>

      <div class="flex items-center gap-2">
        <a
          href="https://bdu.fstec.ru/vul"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-lg shadow-2xs transition-colors"
        >
          <span>Портал БДУ ФСТЭК</span>
          <ExternalLink class="w-3.5 h-3.5 text-slate-400" />
        </a>

        <Button
          variant="primary"
          size="sm"
          :loading="syncing"
          @click="handleSync"
        >
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          Обновить базу БДУ
        </Button>
      </div>
    </div>

    <!-- Уведомление об успешной синхронизации -->
    <div v-if="syncMessage" class="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
      <CheckCircle2 class="w-4 h-4 text-emerald-600 shrink-0" />
      <span>{{ syncMessage }}</span>
    </div>

    <!-- Карточки сводной статистики БДУ ФСТЭК -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
        <span class="text-slate-400 block text-[11px] font-semibold uppercase">Всего в реестре БДУ</span>
        <div class="text-2xl font-extrabold text-slate-900 mt-0.5 font-mono">
          {{ summary ? summary.total_in_db.toLocaleString('ru-RU') : '99 420' }}
        </div>
        <span class="text-[10px] text-slate-500 mt-1 block">База уязвимостей РФ</span>
      </div>

      <div class="bg-white p-4 rounded-xl border border-red-200 bg-red-50/20 shadow-2xs">
        <div class="flex items-center justify-between">
          <span class="text-red-700 block text-[11px] font-semibold uppercase">Критический уровень</span>
          <span class="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse"></span>
        </div>
        <div class="text-2xl font-extrabold text-red-700 mt-0.5 font-mono">
          {{ summary ? summary.critical_count.toLocaleString('ru-RU') : '8 140' }}
        </div>
        <span class="text-[10px] text-red-600 mt-1 block">CVSS 9.0 — 10.0</span>
      </div>

      <div class="bg-white p-4 rounded-xl border border-amber-200 bg-amber-50/20 shadow-2xs">
        <span class="text-amber-700 block text-[11px] font-semibold uppercase">Высокий уровень</span>
        <div class="text-2xl font-extrabold text-amber-700 mt-0.5 font-mono">
          {{ summary ? summary.high_count.toLocaleString('ru-RU') : '24 310' }}
        </div>
        <span class="text-[10px] text-amber-600 mt-1 block">CVSS 7.0 — 8.9</span>
      </div>

      <div class="bg-white p-4 rounded-xl border border-purple-200 bg-purple-50/20 shadow-2xs">
        <div class="flex items-center justify-between">
          <span class="text-purple-700 block text-[11px] font-semibold uppercase">Есть эксплойт</span>
          <Flame class="w-3.5 h-3.5 text-purple-600" />
        </div>
        <div class="text-2xl font-extrabold text-purple-700 mt-0.5 font-mono">
          {{ summary ? summary.exploitable_count.toLocaleString('ru-RU') : '5 120' }}
        </div>
        <span class="text-[10px] text-purple-600 mt-1 block">Публичные PoC / эксплойты</span>
      </div>
    </div>

    <!-- Панель поиска и фильтров -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
      <div class="w-full sm:w-80">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по BDU, CVE, ПО, вендору..."
          @keyup.enter="handleSearch"
        />
      </div>

      <div class="flex items-center gap-2">
        <Select
          v-model="severityFilter"
          placeholder="Уровень опасности"
          :options="[
            { label: 'Все уровни', value: 'all' },
            { label: 'Критический', value: 'Критический' },
            { label: 'Высокий', value: 'Высокий' },
            { label: 'Средний', value: 'Средний' },
            { label: 'Низкий', value: 'Низкий' },
          ]"
          @change="handleSearch"
        />

        <button
          type="button"
          :class="[
            'px-3 py-2 text-xs rounded-lg border font-medium transition-colors flex items-center gap-1.5 cursor-pointer shrink-0',
            onlyExploitable
              ? 'bg-purple-50 text-purple-800 border-purple-300 font-bold'
              : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50',
          ]"
          @click="onlyExploitable = !onlyExploitable; handleSearch()"
        >
          <Flame class="w-3.5 h-3.5" :class="onlyExploitable ? 'text-purple-600' : 'text-slate-400'" />
          <span>Только с эксплойтом</span>
        </button>

        <Button variant="primary" size="sm" :loading="loading" @click="handleSearch">
          <Search class="w-3.5 h-3.5 mr-1" />
          Найти
        </Button>
      </div>
    </div>

    <!-- Таблица уязвимостей БДУ ФСТЭК -->
    <Card noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Идентификатор БДУ / CVE</th>
              <th class="py-3 px-4">Наименование уязвимости</th>
              <th class="py-3 px-4">Уязвимое ПО и вендор</th>
              <th class="py-3 px-4">Версии</th>
              <th class="py-3 px-4 text-center">Уровень / CVSS</th>
              <th class="py-3 px-4 text-center">Эксплойт</th>
              <th class="py-3 px-4 text-right">Действие</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr
              v-for="item in vulnerabilities"
              :key="item.id"
              class="hover:bg-slate-50/80 transition-colors"
            >
              <td class="py-3 px-4 font-mono">
                <span class="font-bold text-slate-900 block">{{ item.bdu_id }}</span>
                <span v-if="item.cve_id" class="text-[10px] text-blue-600 block">{{ item.cve_id }}</span>
              </td>
              <td class="py-3 px-4">
                <div class="font-semibold text-slate-900 line-clamp-2 max-w-sm" :title="item.name">
                  {{ item.name }}
                </div>
                <div class="text-[10px] text-slate-400 mt-0.5">{{ item.vuln_class || 'Уязвимость кода' }}</div>
              </td>
              <td class="py-3 px-4 text-slate-700">
                <div class="font-bold text-slate-900">{{ item.software_name }}</div>
                <div class="text-[10px] text-slate-500">{{ item.vendor }}</div>
              </td>
              <td class="py-3 px-4 font-mono text-[11px] text-slate-600">
                {{ item.software_version || 'Все версии' }}
              </td>
              <td class="py-3 px-4 text-center">
                <div class="inline-flex flex-col items-center">
                  <Badge
                    :variant="item.severity === 'Критический' ? 'destructive' : item.severity === 'Высокий' ? 'warning' : 'secondary'"
                    size="sm"
                    class="mb-0.5"
                  >
                    {{ item.severity }}
                  </Badge>
                  <span
                    v-if="item.cvss_score"
                    :class="['px-1.5 py-0.2 rounded text-[10px] font-mono font-bold border', getCvssBadgeColor(item.cvss_score)]"
                  >
                    CVSS {{ item.cvss_score.toFixed(1) }}
                  </span>
                </div>
              </td>
              <td class="py-3 px-4 text-center">
                <span
                  v-if="item.exploit_status && item.exploit_status.toLowerCase().includes('существ')"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-800 border border-red-200"
                  title="Подтверждено наличие готового эксплойта"
                >
                  <Flame class="w-3 h-3 text-red-600" />
                  Существует
                </span>
                <span v-else class="text-slate-400 text-[10px]">
                  Не подтвержден
                </span>
              </td>
              <td class="py-3 px-4 text-right">
                <button
                  type="button"
                  title="Подробная информация и решение"
                  class="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                  @click="openDetails(item)"
                >
                  <Eye class="w-4 h-4 text-blue-600" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Пустое состояние -->
        <div v-if="vulnerabilities.length === 0" class="text-center py-10 px-4 text-slate-500">
          <Bug class="w-8 h-8 text-slate-400 mx-auto mb-2" />
          <p class="font-medium text-sm text-slate-800">Уязвимостей по заданным критериям не найдено</p>
          <p class="text-xs text-slate-400 mt-1">Попробуйте изменить поисковый запрос или сбросить фильтры опасности</p>
        </div>
      </div>
    </Card>

    <!-- Модальное окно детальной информации об уязвимости БДУ ФСТЭК -->
    <Modal
      v-model="isDetailsModalOpen"
      :title="selectedVuln?.bdu_id || 'Карточка уязвимости ФСТЭК'"
      subtitle="Сведения из Банка данных угроз безопасности информации"
      maxWidth="2xl"
    >
      <div v-if="selectedVuln" class="space-y-4">
        <!-- Заголовок карточки -->
        <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="flex items-center gap-2">
                <span class="font-mono font-bold text-sm text-slate-900">{{ selectedVuln.bdu_id }}</span>
                <span v-if="selectedVuln.cve_id" class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-mono text-[11px] font-bold border border-blue-200">
                  {{ selectedVuln.cve_id }}
                </span>
              </div>
              <h4 class="font-bold text-slate-900 text-sm mt-1 leading-snug">{{ selectedVuln.name }}</h4>
            </div>

            <Badge
              :variant="selectedVuln.severity === 'Критический' ? 'destructive' : selectedVuln.severity === 'Высокий' ? 'warning' : 'secondary'"
              size="md"
            >
              {{ selectedVuln.severity }} (CVSS {{ selectedVuln.cvss_score || '—' }})
            </Badge>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2 border-t border-slate-200 text-xs">
            <div>
              <span class="text-slate-400 block text-[10px] uppercase font-bold">Программа</span>
              <span class="font-bold text-slate-800">{{ selectedVuln.software_name }}</span>
            </div>
            <div>
              <span class="text-slate-400 block text-[10px] uppercase font-bold">Вендор</span>
              <span class="font-medium text-slate-700">{{ selectedVuln.vendor }}</span>
            </div>
            <div>
              <span class="text-slate-400 block text-[10px] uppercase font-bold">Уязвимые версии</span>
              <span class="font-mono text-slate-700">{{ selectedVuln.software_version || 'Все версии' }}</span>
            </div>
          </div>
        </div>

        <!-- Описание уязвимости -->
        <div>
          <h5 class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
            Описание уязвимости
          </h5>
          <p class="text-xs text-slate-700 leading-relaxed bg-white p-3 rounded-lg border border-slate-200">
            {{ selectedVuln.description || 'Описание не предоставлено.' }}
          </p>
        </div>

        <!-- Рекомендации и устранение -->
        <div v-if="selectedVuln.solution">
          <h5 class="text-xs font-bold uppercase tracking-wider text-emerald-700 mb-1 flex items-center gap-1">
            <CheckCircle2 class="w-3.5 h-3.5 text-emerald-600" />
            Меры по устранению уязвимости
          </h5>
          <div class="text-xs text-emerald-900 bg-emerald-50/80 p-3 rounded-lg border border-emerald-200 leading-relaxed">
            {{ selectedVuln.solution }}
          </div>
        </div>

        <!-- Эксплойт и статус -->
        <div class="grid grid-cols-2 gap-3 text-xs bg-slate-50 p-3 rounded-lg border border-slate-200">
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Наличие эксплойта</span>
            <span :class="selectedVuln.exploit_status && selectedVuln.exploit_status.toLowerCase().includes('существ') ? 'text-red-700 font-bold' : 'text-slate-600'">
              {{ selectedVuln.exploit_status || 'Не подтвержден' }}
            </span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Дата публикации ФСТЭК</span>
            <span class="font-mono text-slate-700">{{ selectedVuln.publish_date || '—' }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <Button variant="outline" size="sm" @click="isDetailsModalOpen = false">Закрыть</Button>
      </template>
    </Modal>
  </div>
</template>