<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { Computer, Employee, InstalledSoftware, SoftwareCatalogItem, ComputerEnrollmentStats, ComputerVulnerabilitiesResponse } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import Select from '@/components/ui/Select.vue';
import Modal from '@/components/ui/Modal.vue';
import {
  Monitor,
  Plus,
  Search,
  Edit,
  Trash2,
  UserCheck,
  Cpu,
  HardDrive,
  Calendar,
  Layers,
  XCircle,
  CheckCircle2,
  Wand2,
  PlusCircle,
  Bug,
  Flame,
  ShieldAlert,
  ShieldCheck,
  Shield,
  Ban,
  Check,
  Radio,
  RotateCcw,
  AlertCircle,
  RefreshCw,
} from 'lucide-vue-next';

const computers = ref<Computer[]>([]);
const employees = ref<Employee[]>([]);
const catalog = ref<SoftwareCatalogItem[]>([]);
const loading = ref(false);
const searchQuery = ref('');
const onlineFilter = ref<string>('all');
const enrollmentFilter = ref<string>('all');
const enrollmentStats = ref<ComputerEnrollmentStats>({ total: 0, pending: 0, approved: 0, blocked: 0 });
const actionNotification = ref<string | null>(null);

// Модальные окна
const isCreateModalOpen = ref(false);
const isDetailsModalOpen = ref(false);
const isAddSoftwareModalOpen = ref(false);
const editingComputer = ref<Partial<Computer> | null>(null);
const selectedComputer = ref<Computer | null>(null);
const detailsTab = ref<'software' | 'vulnerabilities'>('software');
const vulnReport = ref<ComputerVulnerabilitiesResponse | null>(null);
const loadingVulns = ref(false);
const scanning = ref(false);

const compForm = ref<{
  hostname: string;
  serial_number: string;
  ip_address: string;
  mac_address: string;
  os_name: string;
  os_version: string;
  cpu_info: string;
  ram_mb: number;
  employee_id: string | null;
  enrollment_status: 'pending' | 'approved' | 'blocked';
}>({
  hostname: '',
  serial_number: '',
  ip_address: '',
  mac_address: '',
  os_name: '',
  os_version: '',
  cpu_info: '',
  ram_mb: 0,
  employee_id: null,
  enrollment_status: 'approved',
});

const softForm = ref({
  catalog_software_id: '',
  raw_display_name: '',
  raw_publisher: '',
  raw_version: '',
});

onMounted(async () => {
  await Promise.all([loadComputers(), loadEmployees(), loadCatalog(), loadEnrollmentStats()]);
});

async function refreshAll() {
  await Promise.all([loadComputers(), loadEnrollmentStats()]);
}

async function loadComputers() {
  loading.value = true;
  try {
    computers.value = await api.getComputers();
  } finally {
    loading.value = false;
  }
}

async function loadEnrollmentStats() {
  try {
    enrollmentStats.value = await api.getComputerEnrollmentStats();
  } catch (e) {
    const total = computers.value.length;
    const pending = computers.value.filter((c) => c.enrollment_status === 'pending').length;
    const blocked = computers.value.filter((c) => c.enrollment_status === 'blocked').length;
    enrollmentStats.value = { total, pending, approved: total - pending - blocked, blocked };
  }
}

async function loadEmployees() {
  employees.value = await api.getEmployees();
}

async function loadCatalog() {
  catalog.value = await api.getCatalog();
}

const filteredComputers = computed(() => {
  return computers.value.filter((comp) => {
    const matchSearch =
      !searchQuery.value ||
      comp.hostname.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      comp.serial_number.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      comp.ip_address?.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      comp.employee?.full_name.toLowerCase().includes(searchQuery.value.toLowerCase());

    const matchOnline =
      onlineFilter.value === 'all' ||
      (onlineFilter.value === 'online' && comp.is_online) ||
      (onlineFilter.value === 'offline' && !comp.is_online);

    const statusVal = comp.enrollment_status || 'approved';
    const matchEnrollment =
      enrollmentFilter.value === 'all' || statusVal === enrollmentFilter.value;

    return matchSearch && matchOnline && matchEnrollment;
  });
});

function showToast(msg: string) {
  actionNotification.value = msg;
  setTimeout(() => {
    actionNotification.value = null;
  }, 4000);
}

async function handleApprove(comp: Computer) {
  try {
    const updated = await api.approveComputer(comp.id);
    comp.enrollment_status = 'approved';
    showToast(`Рабочая станция ${comp.hostname} успешно одобрена! Приём данных разрешён.`);
    await Promise.all([loadComputers(), loadEnrollmentStats()]);
  } catch (err: any) {
    showToast(`Ошибка одобрения ПК: ${err.message || 'Ошибка сети'}`);
  }
}

async function handleBlock(comp: Computer) {
  if (confirm(`Заблокировать ПК ${comp.hostname}? Данные от его агента будут отклоняться сервером.`)) {
    try {
      await api.blockComputer(comp.id);
      comp.enrollment_status = 'blocked';
      showToast(`ПК ${comp.hostname} заблокирован (в чёрном списке).`);
      await Promise.all([loadComputers(), loadEnrollmentStats()]);
    } catch (err: any) {
      showToast(`Ошибка блокировки: ${err.message || 'Ошибка сети'}`);
    }
  }
}

async function handleResetPending(comp: Computer) {
  try {
    await api.resetPendingComputer(comp.id);
    comp.enrollment_status = 'pending';
    showToast(`ПК ${comp.hostname} возвращён в статус ожидания заявки (Pending).`);
    await Promise.all([loadComputers(), loadEnrollmentStats()]);
  } catch (err: any) {
    showToast(`Ошибка: ${err.message}`);
  }
}

async function handleTriggerScan(comp: Computer, thorough = false) {
  scanning.value = true;
  try {
    const res = await api.triggerComputerScan(comp.id, thorough);
    showToast(res.message || `Команда сканирования передана агенту ${comp.hostname}`);
  } catch (err: any) {
    showToast(`Ошибка отправки команды: ${err.message}`);
  } finally {
    scanning.value = false;
  }
}

function openCreate() {
  editingComputer.value = null;
  compForm.value = {
    hostname: '',
    serial_number: '',
    ip_address: '',
    mac_address: '',
    os_name: '',
    os_version: '',
    cpu_info: '',
    ram_mb: 0,
    employee_id: employees.value[0]?.id || null,
    enrollment_status: 'approved',
  };
  isCreateModalOpen.value = true;
}

function openEdit(comp: Computer) {
  editingComputer.value = comp;
  compForm.value = {
    hostname: comp.hostname,
    serial_number: comp.serial_number,
    ip_address: comp.ip_address || '',
    mac_address: comp.mac_address || '',
    os_name: comp.os_name || '',
    os_version: comp.os_version || '',
    cpu_info: comp.cpu_info || '',
    ram_mb: comp.ram_mb ?? 0,
    employee_id: comp.employee_id || null,
    enrollment_status: comp.enrollment_status || 'approved',
  };
  isCreateModalOpen.value = true;
}

async function saveComputer() {
  if (!compForm.value.hostname.trim() || !compForm.value.serial_number.trim()) return;
  if (editingComputer.value?.id) {
    await api.updateComputer(editingComputer.value.id, compForm.value);
  } else {
    await api.createComputer(compForm.value);
  }
  isCreateModalOpen.value = false;
  await loadComputers();
}

async function deleteComputer(id: string) {
  if (confirm('Удалить данный компьютер из системы SAM?')) {
    await api.deleteComputer(id);
    await loadComputers();
  }
}

async function openDetails(comp: Computer, initialTab: 'software' | 'vulnerabilities' = 'software') {
  const details = await api.getComputer(comp.id);
  selectedComputer.value = details;
  detailsTab.value = initialTab;
  vulnReport.value = null;
  isDetailsModalOpen.value = true;
  await loadComputerVulns(comp.id);
}

async function loadComputerVulns(compId: string) {
  loadingVulns.value = true;
  try {
    vulnReport.value = await api.getComputerVulnerabilities(compId);
  } catch (err) {
    console.error('Ошибка загрузки уязвимостей хоста:', err);
  } finally {
    loadingVulns.value = false;
  }
}

function openAddSoftware(comp: Computer) {
  selectedComputer.value = comp;
  softForm.value = {
    catalog_software_id: catalog.value[0]?.id || '',
    raw_display_name: catalog.value[0]?.name || '',
    raw_publisher: catalog.value[0]?.vendor || '',
    raw_version: '',
  };
  isAddSoftwareModalOpen.value = true;
}

async function saveManualSoftware() {
  if (!selectedComputer.value) return;
  await api.addSoftwareToComputer(selectedComputer.value.id, softForm.value);
  isAddSoftwareModalOpen.value = false;
  await openDetails(selectedComputer.value);
  await loadComputers();
}

async function removeSoftware(instId: string) {
  if (!selectedComputer.value) return;
  if (confirm('Удалить факт установки данного ПО на хосте?')) {
    await api.removeSoftwareFromComputer(selectedComputer.value.id, instId);
    await openDetails(selectedComputer.value);
    await loadComputers();
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Уведомление о действиях -->
    <div
      v-if="actionNotification"
      class="bg-blue-50 border border-blue-200 text-blue-900 text-xs px-4 py-2.5 rounded-xl flex items-center justify-between shadow-sm animate-fade-in"
    >
      <div class="flex items-center gap-2">
        <AlertCircle class="w-4 h-4 text-blue-600 shrink-0" />
        <span class="font-medium">{{ actionNotification }}</span>
      </div>
      <button
        type="button"
        @click="actionNotification = null"
        class="text-blue-500 hover:text-blue-800 text-xs font-bold cursor-pointer"
      >
        ✕
      </button>
    </div>

    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Компьютеры и рабочие станции</h1>
        <p class="text-xs text-slate-500 mt-1">
          Реестр оборудования, авторизация агентов (Enrollment), удалённый запуск аудита и привязка к персоналу
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="loading" @click="refreshAll">
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          Обновить
        </Button>
        <Button variant="primary" size="sm" @click="openCreate">
          <Plus class="w-4 h-4 mr-1.5" />
          Добавить ПК вручную
        </Button>
      </div>
    </div>

    <!-- Метрики регистрации оборудования (Enrollment) -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <Card
        class="hover:border-slate-300 transition-all cursor-pointer"
        :class="enrollmentFilter === 'all' ? 'ring-1 ring-slate-300' : ''"
        @click="enrollmentFilter = 'all'"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-slate-500 block">Всего рабочих станций</span>
            <div class="text-2xl font-bold text-slate-900 mt-1 font-mono">
              {{ enrollmentStats.total }}
            </div>
            <p class="text-[11px] text-slate-400 mt-1">Оборудование в базе SAM</p>
          </div>
          <div class="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-600">
            <Monitor class="w-5 h-5" />
          </div>
        </div>
      </Card>

      <Card
        class="transition-all cursor-pointer"
        :class="enrollmentStats.pending > 0 ? 'border-amber-300 bg-amber-50/40 ring-1 ring-amber-300' : 'hover:border-slate-300'"
        @click="enrollmentFilter = enrollmentFilter === 'pending' ? 'all' : 'pending'"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-amber-800 block flex items-center gap-1">
              Заявки на подключение
              <span v-if="enrollmentStats.pending > 0" class="w-2 h-2 rounded-full bg-amber-500 animate-ping"></span>
            </span>
            <div class="text-2xl font-bold text-amber-900 mt-1 font-mono">
              {{ enrollmentStats.pending }}
            </div>
            <p class="text-[11px] text-amber-700 mt-1">
              {{ enrollmentStats.pending > 0 ? 'Требуют авторизации админа' : 'Нет новых заявок' }}
            </p>
          </div>
          <div class="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center text-amber-700">
            <AlertCircle class="w-5 h-5" />
          </div>
        </div>
      </Card>

      <Card
        class="hover:border-emerald-300 transition-all cursor-pointer"
        :class="enrollmentFilter === 'approved' ? 'border-emerald-300 bg-emerald-50/20 ring-1 ring-emerald-300' : ''"
        @click="enrollmentFilter = enrollmentFilter === 'approved' ? 'all' : 'approved'"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-emerald-700 block">Авторизовано (Approved)</span>
            <div class="text-2xl font-bold text-emerald-900 mt-1 font-mono">
              {{ enrollmentStats.approved }}
            </div>
            <p class="text-[11px] text-emerald-600 mt-1">Данные агентов принимаются</p>
          </div>
          <div class="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-700">
            <ShieldCheck class="w-5 h-5" />
          </div>
        </div>
      </Card>

      <Card
        class="transition-all cursor-pointer"
        :class="enrollmentStats.blocked > 0 ? 'border-rose-300 bg-rose-50/30 ring-1 ring-rose-300' : 'hover:border-slate-300'"
        @click="enrollmentFilter = enrollmentFilter === 'blocked' ? 'all' : 'blocked'"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="text-xs font-medium text-rose-700 block">Заблокировано (Blocked)</span>
            <div class="text-2xl font-bold text-rose-900 mt-1 font-mono">
              {{ enrollmentStats.blocked }}
            </div>
            <p class="text-[11px] text-rose-600 mt-1">Отклоняются сервером SAM</p>
          </div>
          <div class="w-10 h-10 rounded-xl bg-rose-100 flex items-center justify-center text-rose-700">
            <Ban class="w-5 h-5" />
          </div>
        </div>
      </Card>
    </div>

    <!-- Панель фильтров -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
      <div class="w-full sm:w-80">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по Hostname, Serial Number, IP, сотруднику..."
        />
      </div>

      <div class="flex items-center gap-2">
        <Select
          v-model="enrollmentFilter"
          placeholder="Статус допуска"
          :options="[
            { label: 'Все допуски', value: 'all' },
            { label: 'Заявки (Pending)', value: 'pending' },
            { label: 'Авторизован (Approved)', value: 'approved' },
            { label: 'Заблокирован (Blocked)', value: 'blocked' },
          ]"
        />
        <Select
          v-model="onlineFilter"
          placeholder="Статус сети"
          :options="[
            { label: 'Все ПК', value: 'all' },
            { label: 'Только онлайн', value: 'online' },
            { label: 'Только офлайн', value: 'offline' },
          ]"
        />
      </div>
    </div>

    <!-- Таблица рабочих станций -->
    <Card noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Имя хоста (Hostname)</th>
              <th class="py-3 px-4">Серийный номер (BIOS SN)</th>
              <th class="py-3 px-4">IP и Сеть</th>
              <th class="py-3 px-4">ОС и Железо</th>
              <th class="py-3 px-4">Закреплённый сотрудник</th>
              <th class="py-3 px-4 text-center">Допуск агента</th>
              <th class="py-3 px-4 text-center">Статус сети</th>
              <th class="py-3 px-4 text-right">Действия</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="comp in filteredComputers" :key="comp.id" class="hover:bg-slate-50/80 transition-colors">
              <td class="py-3 px-4">
                <button
                  type="button"
                  class="font-semibold text-blue-600 hover:text-blue-800 text-left flex items-center gap-1.5 cursor-pointer"
                  @click="openDetails(comp)"
                >
                  <Monitor class="w-4 h-4 text-slate-500 shrink-0" />
                  <span>{{ comp.hostname }}</span>
                </button>
              </td>
              <td class="py-3 px-4 font-mono font-medium text-slate-700">
                {{ comp.serial_number }}
              </td>
              <td class="py-3 px-4 font-mono text-slate-600">
                <div>{{ comp.ip_address || '—' }}</div>
                <div class="text-[10px] text-slate-400">{{ comp.mac_address || '—' }}</div>
              </td>
              <td class="py-3 px-4 text-slate-700">
                <div class="font-medium text-slate-900">{{ comp.os_name }} {{ comp.os_version }}</div>
                <div class="text-[10px] text-slate-400 font-mono">{{ comp.cpu_info }} • {{ (comp.ram_mb || 0) / 1024 }}GB RAM</div>
              </td>
              <td class="py-3 px-4">
                <div v-if="comp.employee" class="flex items-center gap-1.5 text-slate-800">
                  <UserCheck class="w-3.5 h-3.5 text-blue-600 shrink-0" />
                  <span class="font-medium">{{ comp.employee.full_name }}</span>
                </div>
                <span v-else class="text-slate-400 italic text-[11px]">Не закреплен</span>
              </td>
              <td class="py-3 px-4 text-center">
                <span
                  v-if="comp.enrollment_status === 'pending'"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200"
                  title="Ожидает подтверждения администратора SAM"
                >
                  <AlertCircle class="w-3 h-3 text-amber-600" />
                  Заявка
                </span>
                <span
                  v-else-if="comp.enrollment_status === 'blocked'"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-800 border border-rose-200"
                  title="Устройство заблокировано в SAM (чёрный список)"
                >
                  <Ban class="w-3 h-3 text-rose-600" />
                  Заблокирован
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200"
                  title="Авторизованная рабочая станция"
                >
                  <ShieldCheck class="w-3 h-3 text-emerald-600" />
                  Одобрен
                </span>
              </td>
              <td class="py-3 px-4 text-center">
                <span
                  :class="[
                    'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium border',
                    comp.is_online
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-slate-100 text-slate-500 border-slate-200',
                  ]"
                >
                  <span :class="comp.is_online ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'" class="w-2 h-2 rounded-full"></span>
                  {{ comp.is_online ? 'В сети' : 'Офлайн' }}
                </span>
              </td>
              <td class="py-3 px-4 text-right">
                <div class="flex items-center justify-end gap-1">
                  <!-- Кнопка удалённого сканирования через C2 / агент -->
                  <button
                    type="button"
                    :disabled="scanning"
                    title="Запустить удалённое сканирование ПО (Agent Scan)"
                    class="p-1.5 rounded-md hover:bg-emerald-50 text-emerald-600 transition cursor-pointer disabled:opacity-50"
                    @click="handleTriggerScan(comp)"
                  >
                    <Radio class="w-4 h-4" />
                  </button>

                  <!-- Одобрить (если Pending или Blocked) -->
                  <button
                    v-if="comp.enrollment_status === 'pending' || comp.enrollment_status === 'blocked'"
                    type="button"
                    title="Одобрить рабочую станцию (Авторизовать приём данных)"
                    class="p-1.5 rounded-md hover:bg-emerald-50 text-emerald-700 transition cursor-pointer"
                    @click="handleApprove(comp)"
                  >
                    <Check class="w-4 h-4" />
                  </button>

                  <!-- Заблокировать (если Approved или Pending) -->
                  <button
                    v-if="comp.enrollment_status !== 'blocked'"
                    type="button"
                    title="Заблокировать рабочую станцию (Внести в чёрный список)"
                    class="p-1.5 rounded-md hover:bg-rose-50 text-rose-600 transition cursor-pointer"
                    @click="handleBlock(comp)"
                  >
                    <Ban class="w-4 h-4" />
                  </button>

                  <button
                    type="button"
                    title="Аудит уязвимостей БДУ ФСТЭК"
                    class="p-1.5 rounded-md hover:bg-red-50 text-red-600 transition cursor-pointer"
                    @click="openDetails(comp, 'vulnerabilities')"
                  >
                    <Bug class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Установленное ПО на хосте"
                    class="p-1.5 rounded-md hover:bg-blue-50 text-blue-600 transition cursor-pointer"
                    @click="openDetails(comp, 'software')"
                  >
                    <Layers class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Редактировать ПК и привязку"
                    class="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                    @click="openEdit(comp)"
                  >
                    <Edit class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Удалить"
                    class="p-1.5 rounded-md hover:bg-red-50 text-red-600 transition cursor-pointer"
                    @click="deleteComputer(comp.id)"
                  >
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Модальное окно добавления / редактирования ПК -->
    <Modal
      v-model="isCreateModalOpen"
      :title="editingComputer ? 'Редактирование ПК' : 'Регистрация нового ПК'"
      maxWidth="md"
    >
      <form class="space-y-4" @submit.prevent="saveComputer">
        <Input
          v-model="compForm.hostname"
          label="Имя хоста (Hostname)"
          placeholder="WORKSTATION-01"
          required
        />
        <Input
          v-model="compForm.serial_number"
          label="Серийный номер (BIOS / WMI Serial Number)"
          placeholder="G69ZD5J"
          required
        />
        <Input
          v-model="compForm.ip_address"
          label="IP-адрес"
          placeholder="192.168.10.45"
        />
        <Input
          v-model="compForm.os_name"
          label="Операционная система"
          placeholder="Windows 11 Pro"
        />
        <Select
          v-model="compForm.enrollment_status"
          label="Статус допуска (Enrollment)"
          :options="[
            { label: 'Одобрен (Approved)', value: 'approved' },
            { label: 'Ожидает одобрения (Pending)', value: 'pending' },
            { label: 'Заблокирован (Blocked)', value: 'blocked' },
          ]"
        />
        <Select
          v-model="compForm.employee_id"
          label="Привязать к сотруднику"
          placeholder="Выберите сотрудника..."
          :options="employees.map(e => ({ label: `${e.full_name} (${e.department})`, value: e.id }))"
        />

        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" type="button" @click="isCreateModalOpen = false">Отмена</Button>
          <Button variant="primary" size="sm" type="submit">Сохранить</Button>
        </div>
      </form>
    </Modal>

    <!-- Модальное окно сведений о ПК и установленном софте -->
    <Modal
      v-model="isDetailsModalOpen"
      :title="selectedComputer?.hostname || 'Карточка рабочей станции'"
      :subtitle="`Серийный номер: ${selectedComputer?.serial_number || ''} • IP: ${selectedComputer?.ip_address || ''}`"
      maxWidth="4xl"
    >
      <div v-if="selectedComputer" class="space-y-5">
        <!-- Характеристики оборудования -->
        <div class="grid grid-cols-2 md:grid-cols-5 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs">
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">ОС</span>
            <span class="font-semibold text-slate-800">{{ selectedComputer.os_name }} {{ selectedComputer.os_version }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Процессор / RAM</span>
            <span class="font-semibold text-slate-800">{{ (selectedComputer.ram_mb || 0) / 1024 }} ГБ RAM</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Сотрудник</span>
            <span class="font-semibold text-slate-800">{{ selectedComputer.employee?.full_name || 'Не закреплен' }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Допуск агента</span>
            <span
              :class="[
                'font-semibold inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full mt-0.5',
                selectedComputer.enrollment_status === 'pending'
                  ? 'bg-amber-100 text-amber-800'
                  : selectedComputer.enrollment_status === 'blocked'
                  ? 'bg-rose-100 text-rose-800'
                  : 'bg-emerald-100 text-emerald-800',
              ]"
            >
              {{ selectedComputer.enrollment_status === 'pending' ? 'Заявка (Pending)' : selectedComputer.enrollment_status === 'blocked' ? 'Заблокирован' : 'Одобрен' }}
            </span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Статус сети</span>
            <span :class="selectedComputer.is_online ? 'text-emerald-600' : 'text-slate-500'" class="font-semibold flex items-center gap-1 mt-0.5">
              <span :class="selectedComputer.is_online ? 'bg-emerald-500' : 'bg-slate-400'" class="w-2 h-2 rounded-full"></span>
              {{ selectedComputer.is_online ? 'Онлайн' : 'Офлайн' }}
            </span>
          </div>
        </div>

        <!-- Панель управления агентом и допуском -->
        <div class="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs font-semibold text-slate-700">Управление допуском:</span>
            <Button
              v-if="selectedComputer.enrollment_status !== 'approved'"
              variant="primary"
              size="sm"
              @click="handleApprove(selectedComputer)"
            >
              <Check class="w-3.5 h-3.5 mr-1" />
              Одобрить допуск
            </Button>
            <Button
              v-if="selectedComputer.enrollment_status !== 'blocked'"
              variant="destructive"
              size="sm"
              @click="handleBlock(selectedComputer)"
            >
              <Ban class="w-3.5 h-3.5 mr-1" />
              Заблокировать
            </Button>
            <Button
              v-if="selectedComputer.enrollment_status === 'blocked'"
              variant="outline"
              size="sm"
              @click="handleResetPending(selectedComputer)"
            >
              <RotateCcw class="w-3.5 h-3.5 mr-1" />
              В статус заявки
            </Button>
          </div>

          <div class="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              :disabled="scanning"
              @click="handleTriggerScan(selectedComputer, false)"
            >
              <Radio class="w-3.5 h-3.5 mr-1 text-emerald-600" />
              {{ scanning ? 'Отправка...' : 'Запустить скан агента' }}
            </Button>
            <Button
              variant="outline"
              size="sm"
              :disabled="scanning"
              @click="handleTriggerScan(selectedComputer, true)"
            >
              <RefreshCw class="w-3.5 h-3.5 mr-1 text-blue-600" />
              {{ scanning ? 'Отправка...' : 'Глубокий скан (реестр)' }}
            </Button>
          </div>
        </div>

        <!-- Переключатель вкладок карточки ПК -->
        <div class="flex items-center gap-2 border-b border-slate-200 pb-2">
          <button
            type="button"
            :class="[
              'px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer flex items-center gap-1.5',
              detailsTab === 'software'
                ? 'bg-blue-50 text-blue-700'
                : 'text-slate-600 hover:text-slate-900',
            ]"
            @click="detailsTab = 'software'"
          >
            <Layers class="w-3.5 h-3.5" />
            <span>Установленное ПО ({{ selectedComputer.installed_software?.length || 0 }})</span>
          </button>

          <button
            type="button"
            :class="[
              'px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer flex items-center gap-1.5',
              detailsTab === 'vulnerabilities'
                ? 'bg-red-50 text-red-700'
                : 'text-slate-600 hover:text-slate-900',
            ]"
            @click="detailsTab = 'vulnerabilities'"
          >
            <Bug class="w-3.5 h-3.5" />
            <span>Уязвимости БДУ ФСТЭК</span>
            <span
              v-if="vulnReport && vulnReport.total_vulnerabilities > 0"
              class="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-red-100 text-red-700 font-bold ml-0.5"
            >
              {{ vulnReport.total_vulnerabilities }}
            </span>
          </button>
        </div>

        <!-- Вкладка 1: Раздел установленного ПО -->
        <div v-if="detailsTab === 'software'">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-bold text-slate-900 text-sm">
              Список установленного ПО на данном ПК
            </h4>
            <Button variant="outline" size="sm" @click="openAddSoftware(selectedComputer)">
              <PlusCircle class="w-3.5 h-3.5 mr-1 text-blue-600" />
              Добавить факт установки
            </Button>
          </div>

          <div class="overflow-x-auto border border-slate-200 rounded-lg">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold text-[11px]">
                  <th class="py-2.5 px-3">Наименование ПО / Процесс</th>
                  <th class="py-2.5 px-3">Издатель</th>
                  <th class="py-2.5 px-3">Версия</th>
                  <th class="py-2.5 px-3">Каталог (Мэтчинг)</th>
                  <th class="py-2.5 px-3">Последний запуск</th>
                  <th class="py-2.5 px-3 text-right">Действия</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr
                  v-for="soft in selectedComputer.installed_software"
                  :key="soft.id"
                  class="hover:bg-slate-50"
                >
                  <td class="py-2.5 px-3 font-medium text-slate-900">
                    {{ soft.raw_display_name }}
                  </td>
                  <td class="py-2.5 px-3 text-slate-600">
                    {{ soft.raw_publisher || '—' }}
                  </td>
                  <td class="py-2.5 px-3 font-mono text-slate-600">
                    {{ soft.raw_version || '—' }}
                  </td>
                  <td class="py-2.5 px-3">
                    <span v-if="soft.catalog_software_name" class="text-emerald-700 font-semibold flex items-center gap-1">
                      <CheckCircle2 class="w-3.5 h-3.5 text-emerald-600" />
                      {{ soft.catalog_software_name }}
                    </span>
                    <span v-else class="text-amber-600 flex items-center gap-1 text-[11px]">
                      Не сопоставлен
                    </span>
                  </td>
                  <td class="py-2.5 px-3 text-slate-500 text-[11px] font-mono">
                    {{ soft.last_launched_at ? new Date(soft.last_launched_at).toLocaleDateString('ru-RU') : '—' }}
                  </td>
                  <td class="py-2.5 px-3 text-right">
                    <button
                      type="button"
                      title="Удалить установку"
                      class="p-1 hover:bg-red-50 text-red-600 rounded transition cursor-pointer"
                      @click="removeSoftware(soft.id)"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Вкладка 2: Отчёт об уязвимостях БДУ ФСТЭК для хоста -->
        <div v-else-if="detailsTab === 'vulnerabilities'" class="space-y-4">
          <div v-if="loadingVulns" class="text-center py-8 text-xs text-slate-500">
            Загрузка и сопоставление с базой БДУ ФСТЭК России...
          </div>
          <div v-else-if="vulnReport" class="space-y-4">
            <!-- Сводные метрики хоста -->
            <div class="grid grid-cols-3 gap-3">
              <div class="p-3 rounded-lg bg-red-50 border border-red-200">
                <span class="text-[10px] uppercase font-bold text-red-600 block">Критических</span>
                <span class="text-xl font-extrabold text-red-700 font-mono">{{ vulnReport.critical_count }}</span>
              </div>
              <div class="p-3 rounded-lg bg-amber-50 border border-amber-200">
                <span class="text-[10px] uppercase font-bold text-amber-600 block">Высоких</span>
                <span class="text-xl font-extrabold text-amber-700 font-mono">{{ vulnReport.high_count }}</span>
              </div>
              <div class="p-3 rounded-lg bg-purple-50 border border-purple-200">
                <span class="text-[10px] uppercase font-bold text-purple-600 block">Эксплойты</span>
                <span class="text-xl font-extrabold text-purple-700 font-mono">
                  {{ vulnReport.has_exploits ? 'Обнаружены' : 'Нет' }}
                </span>
              </div>
            </div>

            <!-- Список уязвимого софта на хосте -->
            <div class="space-y-3">
              <div
                v-for="app in vulnReport.affected_software"
                :key="app.installed_software_id"
                class="border border-slate-200 rounded-lg p-3 bg-white space-y-2 text-xs"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <span class="font-bold text-slate-900 text-sm">{{ app.software_name }}</span>
                    <span class="font-mono text-slate-500 text-[11px]">{{ app.version || 'версия не указана' }}</span>
                  </div>
                  <Badge variant="destructive" size="sm">
                    Уязвимостей: {{ app.vulnerabilities_count }}
                  </Badge>
                </div>

                <div class="space-y-1.5 pt-1">
                  <div
                    v-for="v in app.vulnerabilities"
                    :key="v.id"
                    class="p-2.5 rounded bg-slate-50 border border-slate-200 flex flex-col gap-1"
                  >
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-2 font-mono">
                        <span class="font-bold text-slate-900">{{ v.bdu_id }}</span>
                        <span v-if="v.cve_id" class="text-blue-600 text-[11px]">{{ v.cve_id }}</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <span v-if="v.cvss_score" class="font-mono font-bold text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-800">
                          CVSS {{ v.cvss_score }}
                        </span>
                        <span v-if="v.exploit_status && v.exploit_status.includes('существ')" class="text-red-700 text-[10px] font-bold flex items-center gap-0.5">
                          <Flame class="w-3 h-3 text-red-600" />
                          Эксплойт
                        </span>
                      </div>
                    </div>
                    <div class="text-[11px] text-slate-700">{{ v.name }}</div>
                    <div v-if="v.solution" class="text-[10px] text-emerald-800 bg-emerald-50/60 p-1.5 rounded mt-0.5 border border-emerald-100">
                      <strong>Мера:</strong> {{ v.solution }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-6 text-xs text-slate-400">
            Для данного хоста не зафиксировано уязвимостей в базе БДУ ФСТЭК.
          </div>
        </div>
      </div>
      <template #footer>
        <Button variant="outline" size="sm" @click="isDetailsModalOpen = false">Закрыть</Button>
      </template>
    </Modal>

    <!-- Модальное окно ручного добавления софта -->
    <Modal
      v-model="isAddSoftwareModalOpen"
      title="Ручное добавление софта на ПК"
      maxWidth="md"
    >
      <form class="space-y-4" @submit.prevent="saveManualSoftware">
        <Select
          v-model="softForm.catalog_software_id"
          label="Выбрать из Каталога разрешённого ПО"
          :options="catalog.map(c => ({ label: `${c.name} (${c.vendor})`, value: c.id }))"
        />
        <Input
          v-model="softForm.raw_display_name"
          label="Отображаемое имя (Display Name)"
          placeholder="Microsoft Visual Studio 2022"
          required
        />
        <Input
          v-model="softForm.raw_publisher"
          label="Издатель (Publisher)"
          placeholder="Microsoft Corporation"
        />
        <Input
          v-model="softForm.raw_version"
          label="Версия ПО"
          placeholder="17.8.0"
        />
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" type="button" @click="isAddSoftwareModalOpen = false">Отмена</Button>
          <Button variant="primary" size="sm" type="submit">Добавить</Button>
        </div>
      </form>
    </Modal>
  </div>
</template>
