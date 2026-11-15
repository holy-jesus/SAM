<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { useSamStore } from '@/stores/sam';
import { InstalledSoftware, SoftwareCategory, Computer, SoftwareCatalogItem } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import Select from '@/components/ui/Select.vue';
import Modal from '@/components/ui/Modal.vue';
import {
  Laptop,
  Search,
  Filter,
  Wand2,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Plus,
  Tag,
} from 'lucide-vue-next';

const samStore = useSamStore();

const softwareList = ref<InstalledSoftware[]>([]);
const categories = ref<SoftwareCategory[]>([]);
const computers = ref<Computer[]>([]);
const catalog = ref<SoftwareCatalogItem[]>([]);
const loading = ref(false);
const searchQuery = ref('');
const categoryFilter = ref<string>('all');

// Модальные окна
const isCategoryModalOpen = ref(false);
const isAddModalOpen = ref(false);
const selectedItem = ref<InstalledSoftware | null>(null);
const targetCategoryId = ref<number>(1);

const addForm = ref({
  computer_id: '',
  catalog_software_id: '',
  raw_display_name: '',
  raw_publisher: '',
  raw_version: '',
});

onMounted(async () => {
  await Promise.all([loadSoftware(), loadCategories(), loadComputers(), loadCatalog()]);
});

async function loadSoftware() {
  loading.value = true;
  try {
    softwareList.value = await api.getInstalledSoftware();
  } finally {
    loading.value = false;
  }
}

async function loadCategories() {
  categories.value = await api.getCategories();
}

async function loadComputers() {
  computers.value = await api.getComputers();
}

async function loadCatalog() {
  catalog.value = await api.getCatalog();
}

const filteredSoftware = computed(() => {
  return softwareList.value.filter((item) => {
    const matchSearch =
      !searchQuery.value ||
      item.raw_display_name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      item.computer_hostname?.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      item.raw_publisher?.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      item.computer_serial?.toLowerCase().includes(searchQuery.value.toLowerCase());

    const matchCat =
      categoryFilter.value === 'all' ||
      item.category_id?.toString() === categoryFilter.value;

    return matchSearch && matchCat;
  });
});

function openChangeCategory(item: InstalledSoftware) {
  selectedItem.value = item;
  targetCategoryId.value = item.category_id || 1;
  isCategoryModalOpen.value = true;
}

async function saveCategory() {
  if (!selectedItem.value) return;
  await api.updateSoftwareCategory(selectedItem.value.id, Number(targetCategoryId.value));
  isCategoryModalOpen.value = false;
  await loadSoftware();
}

function openAdd() {
  addForm.value = {
    computer_id: computers.value[0]?.id || '',
    catalog_software_id: catalog.value[0]?.id || '',
    raw_display_name: catalog.value[0]?.name || '',
    raw_publisher: catalog.value[0]?.vendor || '',
    raw_version: '',
  };
  isAddModalOpen.value = true;
}

function openSmartMatchForUnverified() {
  const unverified = softwareList.value.find(s => !s.catalog_software_name);
  if (unverified) {
    samStore.triggerSmartMatch(unverified.raw_display_name);
  } else if (softwareList.value.length > 0) {
    samStore.triggerSmartMatch(softwareList.value[0].raw_display_name);
  } else {
    samStore.triggerSmartMatch('');
  }
}

async function saveAdd() {
  if (!addForm.value.computer_id) return;
  await api.addSoftwareToComputer(addForm.value.computer_id, addForm.value);
  isAddModalOpen.value = false;
  await loadSoftware();
}

async function deleteInstalled(item: InstalledSoftware) {
  if (confirm(`Удалить установку "${item.raw_display_name}" с ПК ${item.computer_hostname}?`)) {
    await api.removeSoftwareFromComputer(item.computer_id, item.id);
    await loadSoftware();
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Установленное ПО на предприятии</h1>
        <p class="text-xs text-slate-500 mt-1">
          Единый сквозной реестр инсталляций, привязка категорий и контроль неавторизованного софта
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" @click="openSmartMatchForUnverified">
          <Wand2 class="w-3.5 h-3.5 mr-1 text-blue-600" />
          Умный мэтчинг ИИ
        </Button>
        <Button variant="primary" size="sm" @click="openAdd">
          <Plus class="w-4 h-4 mr-1.5" />
          Добавить факт установки
        </Button>
      </div>
    </div>

    <!-- Панель фильтров -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
      <div class="w-full sm:w-80">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по названию софта, хосту, издателю..."
        />
      </div>

      <div class="flex items-center gap-2">
        <Select
          v-model="categoryFilter"
          placeholder="Все категории"
          :options="[
            { label: 'Все категории', value: 'all' },
            ...categories.map(c => ({ label: c.name, value: c.id.toString() }))
          ]"
        />
      </div>
    </div>

    <!-- Таблица установленного ПО -->
    <Card noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Наименование ПО / Имя процесса</th>
              <th class="py-3 px-4">Рабочая станция (Хост)</th>
              <th class="py-3 px-4">Издатель и Версия</th>
              <th class="py-3 px-4">Категория софта</th>
              <th class="py-3 px-4">Каталог (Мэтчинг)</th>
              <th class="py-3 px-4">Последний запуск</th>
              <th class="py-3 px-4 text-right">Действия</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="item in filteredSoftware" :key="item.id" class="hover:bg-slate-50/80 transition-colors">
              <td class="py-3 px-4 font-semibold text-slate-900">
                <div class="flex items-center gap-2">
                  <Laptop class="w-4 h-4 text-slate-400 shrink-0" />
                  <span>{{ item.raw_display_name }}</span>
                </div>
                <div v-if="item.install_path" class="text-[10px] text-slate-400 font-mono truncate max-w-xs mt-0.5" :title="item.install_path">
                  {{ item.install_path }}
                </div>
              </td>
              <td class="py-3 px-4">
                <span class="font-mono font-semibold text-slate-800">{{ item.computer_hostname }}</span>
                <span class="text-[10px] text-slate-400 block font-mono">SN: {{ item.computer_serial }}</span>
              </td>
              <td class="py-3 px-4 text-slate-600">
                <div>{{ item.raw_publisher || '—' }}</div>
                <div class="text-[11px] font-mono text-slate-500">{{ item.raw_version || '—' }}</div>
              </td>
              <td class="py-3 px-4">
                <button
                  type="button"
                  class="cursor-pointer"
                  title="Нажмите, чтобы изменить категорию"
                  @click="openChangeCategory(item)"
                >
                  <Badge
                    :variant="item.category_id === 3 ? 'destructive' : item.category_id === 2 ? 'warning' : item.category_id === 1 ? 'success' : 'default'"
                    size="sm"
                  >
                    {{ item.category_name || 'Не указана' }}
                  </Badge>
                </button>
              </td>
              <td class="py-3 px-4">
                <div v-if="item.catalog_software_name" class="space-y-1">
                  <div class="flex items-center gap-1.5 text-emerald-700 font-medium">
                    <CheckCircle2 class="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span class="truncate max-w-[150px]" :title="item.catalog_software_name">{{ item.catalog_software_name }}</span>
                  </div>
                  <div v-if="item.is_domestic" class="text-[10px] text-emerald-600 font-normal">
                    ПО РФ (Реестр)
                  </div>
                  <div v-else-if="item.has_substitution" class="text-[10px] text-blue-600 font-normal">
                    Есть аналог РФ ({{ item.substitutions_count }})
                  </div>
                </div>
                <div v-else class="flex items-center gap-1.5 text-indigo-600 text-[11px]">
                  <button
                    type="button"
                    class="hover:underline flex items-center gap-1 font-semibold cursor-pointer"
                    @click="samStore.triggerSmartMatch(item.raw_display_name)"
                  >
                    <Wand2 class="w-3 h-3 text-indigo-600" />
                    Мэтчинг ИИ
                  </button>
                </div>
              </td>
              <td class="py-3 px-4 text-slate-600 font-mono text-[11px]">
                <div v-if="item.last_launched_at">
                  {{ new Date(item.last_launched_at).toLocaleDateString('ru-RU') }}
                </div>
                <span v-else class="text-slate-400 italic">Не зафиксирован</span>
              </td>
              <td class="py-3 px-4 text-right">
                <div class="flex items-center justify-end gap-1">
                  <button
                    type="button"
                    title="Сменить категорию"
                    class="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                    @click="openChangeCategory(item)"
                  >
                    <Tag class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Удалить установку"
                    class="p-1.5 rounded-md hover:bg-red-50 text-red-600 transition cursor-pointer"
                    @click="deleteInstalled(item)"
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

    <!-- Модальное окно смены категории ПО -->
    <Modal
      v-model="isCategoryModalOpen"
      title="Назначить категорию ПО"
      :subtitle="selectedItem?.raw_display_name"
      maxWidth="sm"
    >
      <div class="space-y-4">
        <Select
          v-model="targetCategoryId"
          label="Категория соответствия политике"
          :options="categories.map(c => ({ label: `${c.name} ${c.is_problematic ? '(Проблемная)' : ''}`, value: c.id }))"
        />
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" @click="isCategoryModalOpen = false">Отмена</Button>
          <Button variant="primary" size="sm" @click="saveCategory">Сохранить</Button>
        </div>
      </div>
    </Modal>

    <!-- Модальное окно ручного добавления софта -->
    <Modal
      v-model="isAddModalOpen"
      title="Добавить факт установки ПО на хост"
      maxWidth="md"
    >
      <form class="space-y-4" @submit.prevent="saveAdd">
        <Select
          v-model="addForm.computer_id"
          label="Рабочая станция (Хост)"
          :options="computers.map(c => ({ label: `${c.hostname} (SN: ${c.serial_number})`, value: c.id }))"
        />
        <Select
          v-model="addForm.catalog_software_id"
          label="Эталонное ПО из Каталога"
          :options="catalog.map(c => ({ label: `${c.name} (${c.vendor})`, value: c.id }))"
        />
        <Input
          v-model="addForm.raw_display_name"
          label="Наименование (Display Name)"
          placeholder="Microsoft Visual Studio 2022"
          required
        />
        <Input
          v-model="addForm.raw_publisher"
          label="Издатель (Publisher)"
          placeholder="Microsoft Corporation"
        />
        <Input
          v-model="addForm.raw_version"
          label="Версия"
          placeholder="17.8.0"
        />
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" type="button" @click="isAddModalOpen = false">Отмена</Button>
          <Button variant="primary" size="sm" type="submit">Добавить</Button>
        </div>
      </form>
    </Modal>
  </div>
</template>
