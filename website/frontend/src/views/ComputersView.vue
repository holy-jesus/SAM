<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { Computer, Employee, InstalledSoftware, SoftwareCatalogItem } from '@/types';
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
} from 'lucide-vue-next';

const computers = ref<Computer[]>([]);
const employees = ref<Employee[]>([]);
const catalog = ref<SoftwareCatalogItem[]>([]);
const loading = ref(false);
const searchQuery = ref('');
const onlineFilter = ref<string>('all');

// Модальные окна
const isCreateModalOpen = ref(false);
const isDetailsModalOpen = ref(false);
const isAddSoftwareModalOpen = ref(false);
const editingComputer = ref<Partial<Computer> | null>(null);
const selectedComputer = ref<Computer | null>(null);

const compForm = ref({
  hostname: '',
  serial_number: '',
  ip_address: '',
  mac_address: '',
  os_name: '',
  os_version: '',
  cpu_info: '',
  ram_mb: 0,
  employee_id: '' as string | null,
});

const softForm = ref({
  catalog_software_id: '',
  raw_display_name: '',
  raw_publisher: '',
  raw_version: '',
});

onMounted(async () => {
  await Promise.all([loadComputers(), loadEmployees(), loadCatalog()]);
});

async function loadComputers() {
  loading.value = true;
  try {
    computers.value = await api.getComputers();
  } finally {
    loading.value = false;
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

    return matchSearch && matchOnline;
  });
});

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

async function openDetails(comp: Computer) {
  const details = await api.getComputer(comp.id);
  selectedComputer.value = details;
  isDetailsModalOpen.value = true;
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
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Компьютеры и рабочие станции</h1>
        <p class="text-xs text-slate-500 mt-1">
          Реестр оборудования, синхронизация с Go-агентом и привязка к сотрудникам
        </p>
      </div>

      <Button variant="primary" size="sm" @click="openCreate">
        <Plus class="w-4 h-4 mr-1.5" />
        Добавить ПК вручную
      </Button>
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
                  <button
                    type="button"
                    title="Установленное ПО на хосте"
                    class="p-1.5 rounded-md hover:bg-blue-50 text-blue-600 transition cursor-pointer"
                    @click="openDetails(comp)"
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
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs">
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
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Статус сети</span>
            <span :class="selectedComputer.is_online ? 'text-emerald-600' : 'text-slate-500'" class="font-semibold flex items-center gap-1">
              <span :class="selectedComputer.is_online ? 'bg-emerald-500' : 'bg-slate-400'" class="w-2 h-2 rounded-full"></span>
              {{ selectedComputer.is_online ? 'Онлайн' : 'Офлайн' }}
            </span>
          </div>
        </div>

        <!-- Раздел установленного ПО -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-bold text-slate-900 text-sm">
              Установленное ПО на данном ПК ({{ selectedComputer.installed_software?.length || 0 }})
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
