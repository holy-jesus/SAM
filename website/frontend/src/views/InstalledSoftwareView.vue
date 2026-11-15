<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
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
  Globe,
  Sparkles,
  ShieldCheck,
  Hash,
  Database,
  BookOpen,
  Link2,
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
  window.addEventListener('software-matched', loadSoftware);
  await Promise.all([loadSoftware(), loadCategories(), loadComputers(), loadCatalog()]);
});

onUnmounted(() => {
  window.removeEventListener('software-matched', loadSoftware);
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

function getCleanName(item: InstalledSoftware): string {
  return item.catalog_software_name || item.normalized_name || item.raw_display_name;
}

function hasCustomCleanName(item: InstalledSoftware): boolean {
  const clean = getCleanName(item);
  return clean.toLowerCase().trim() !== item.raw_display_name.toLowerCase().trim();
}

function getSourceBadge(source?: string | null) {
  switch (source) {
    case 'wikimedia':
      return {
        label: 'Wikimedia',
        fullLabel: 'Wikimedia Semantic Search',
        bg: 'bg-cyan-50',
        text: 'text-cyan-700',
        border: 'border-cyan-200',
        icon: Globe,
      };
    case 'ru_registry':
      return {
        label: 'Реестр РФ',
        fullLabel: 'Единый реестр отечественного ПО',
        bg: 'bg-emerald-50',
        text: 'text-emerald-700',
        border: 'border-emerald-200',
        icon: ShieldCheck,
      };
    case 'openai':
      return {
        label: 'Нейросеть LLM',
        fullLabel: 'Нейросетевая нормализация (OpenAI LLM)',
        bg: 'bg-indigo-50',
        text: 'text-indigo-700',
        border: 'border-indigo-200',
        icon: Sparkles,
      };
    case 'hash':
      return {
        label: 'SHA-256',
        fullLabel: 'Контрольная сумма файла SHA-256',
        bg: 'bg-purple-50',
        text: 'text-purple-700',
        border: 'border-purple-200',
        icon: Hash,
      };
    case 'path_heuristic':
      return {
        label: 'Эвристика',
        fullLabel: 'Эвристика пути установки и .exe',
        bg: 'bg-amber-50',
        text: 'text-amber-800',
        border: 'border-amber-200',
        icon: Laptop,
      };
    case 'embedding':
      return {
        label: 'pgvector',
        fullLabel: 'Векторный поиск (pgvector)',
        bg: 'bg-blue-50',
        text: 'text-blue-700',
        border: 'border-blue-200',
        icon: Database,
      };
    case 'process_signatures':
      return {
        label: 'База сигнатур',
        fullLabel: 'Самообучающаяся база сигнатур',
        bg: 'bg-slate-100',
        text: 'text-slate-700',
        border: 'border-slate-300',
        icon: BookOpen,
      };
    case 'admin':
      return {
        label: 'Администратор',
        fullLabel: 'Ручная экспертная верификация',
        bg: 'bg-teal-50',
        text: 'text-teal-700',
        border: 'border-teal-200',
        icon: CheckCircle2,
      };
    case 'catalog':
    case 'fuzzy_catalog':
      return {
        label: 'Каталог ПО',
        fullLabel: 'Каталог разрешённого ПО',
        bg: 'bg-slate-100',
        text: 'text-slate-700',
        border: 'border-slate-200',
        icon: BookOpen,
      };
    default:
      return null;
  }
}

const filteredSoftware = computed(() => {
  return softwareList.value.filter((item) => {
    const q = searchQuery.value.toLowerCase().trim();
    const cleanName = getCleanName(item).toLowerCase();
    const rawName = item.raw_display_name.toLowerCase();
    const host = item.computer_hostname?.toLowerCase() || '';
    const pub = item.raw_publisher?.toLowerCase() || '';
    const sn = item.computer_serial?.toLowerCase() || '';

    const matchSearch =
      !q ||
      cleanName.includes(q) ||
      rawName.includes(q) ||
      host.includes(q) ||
      pub.includes(q) ||
      sn.includes(q);

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
          Единый сквозной реестр инсталляций, распознавание процессов конвейером ИИ, привязка категорий и контроль Shadow IT
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
              <!-- Колонка 1: Красивое имя ПО + имя процесса -->
              <td class="py-3 px-4 text-slate-900">
                <div class="flex items-start gap-2.5">
                  <div class="p-1.5 rounded-lg bg-slate-100 text-slate-600 shrink-0 mt-0.5">
                    <Laptop class="w-4 h-4" />
                  </div>
                  <div class="min-w-0">
                    <div class="font-semibold text-slate-900 text-sm leading-snug">
                      {{ getCleanName(item) }}
                    </div>
                    <div v-if="hasCustomCleanName(item)" class="flex items-center gap-1.5 mt-1 text-[11px] text-slate-500 font-mono">
                      <span class="text-slate-400 font-sans text-[10px] uppercase font-medium">Процесс:</span>
                      <span class="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200 text-slate-700 truncate max-w-[220px]" :title="item.raw_display_name">
                        {{ item.raw_display_name }}
                      </span>
                    </div>
                    <div v-if="item.install_path" class="text-[10px] text-slate-400 font-mono truncate max-w-xs mt-1" :title="item.install_path">
                      {{ item.install_path }}
                    </div>
                  </div>
                </div>
              </td>

              <!-- Колонка 2: ПК / Серийный номер -->
              <td class="py-3 px-4">
                <span class="font-mono font-semibold text-slate-800">{{ item.computer_hostname }}</span>
                <span class="text-[10px] text-slate-400 block font-mono">SN: {{ item.computer_serial }}</span>
              </td>

              <!-- Колонка 3: Издатель и Версия -->
              <td class="py-3 px-4 text-slate-600">
                <div>{{ item.raw_publisher || '—' }}</div>
                <div class="text-[11px] font-mono text-slate-500">{{ item.raw_version || '—' }}</div>
              </td>

              <!-- Колонка 4: Категория -->
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

              <!-- Колонка 5: Каталог / Мэтчинг (Источник конвейера) -->
              <td class="py-3 px-4">
                <!-- Вариант 1: Связано с эталонным каталогом ПО -->
                <div v-if="item.catalog_software_name" class="space-y-1">
                  <div class="flex items-center gap-1.5 text-emerald-700 font-medium text-xs">
                    <CheckCircle2 class="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span class="truncate max-w-[170px]" :title="item.catalog_software_name">{{ item.catalog_software_name }}</span>
                  </div>

                  <div v-if="getSourceBadge(item.match_source)" class="flex items-center gap-1">
                    <span
                      class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border"
                      :class="[getSourceBadge(item.match_source)?.bg, getSourceBadge(item.match_source)?.text, getSourceBadge(item.match_source)?.border]"
                      :title="getSourceBadge(item.match_source)?.fullLabel"
                    >
                      <component :is="getSourceBadge(item.match_source)?.icon" class="w-2.5 h-2.5 shrink-0" />
                      {{ getSourceBadge(item.match_source)?.label }}
                    </span>
                    <span v-if="item.match_confidence" class="text-[10px] text-slate-400 font-mono">
                      {{ Math.round(item.match_confidence * 100) }}%
                    </span>
                  </div>

                  <div v-if="item.is_domestic" class="text-[10px] text-emerald-600 font-medium flex items-center gap-1">
                    <ShieldCheck class="w-3 h-3 text-emerald-600" />
                    ПО РФ (Реестр)
                  </div>
                  <div v-else-if="item.has_substitution" class="text-[10px] text-blue-600 font-medium">
                    Есть аналог РФ ({{ item.substitutions_count }})
                  </div>
                </div>

                <!-- Вариант 2: Распознано через Wikimedia / LLM / Реестр, но пока не привязано к белому списку каталога (Shadow IT) -->
                <div v-else-if="item.normalized_name" class="space-y-1.5">
                  <div class="flex items-center gap-1">
                    <span
                      class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border"
                      :class="[
                        getSourceBadge(item.match_source)?.bg || 'bg-cyan-50',
                        getSourceBadge(item.match_source)?.text || 'text-cyan-700',
                        getSourceBadge(item.match_source)?.border || 'border-cyan-200'
                      ]"
                      :title="getSourceBadge(item.match_source)?.fullLabel || 'Распознано через внешний сервис'"
                    >
                      <component :is="getSourceBadge(item.match_source)?.icon || Globe" class="w-3 h-3 shrink-0" />
                      <span>{{ getSourceBadge(item.match_source)?.label || 'Распознано' }}:</span>
                      <strong class="font-semibold truncate max-w-[120px]" :title="item.normalized_name">{{ item.normalized_name }}</strong>
                    </span>
                  </div>

                  <div class="flex items-center gap-2 text-[10px]">
                    <span class="text-amber-600 font-medium">Shadow IT (вне каталога)</span>
                    <button
                      type="button"
                      class="text-indigo-600 hover:text-indigo-800 underline font-medium cursor-pointer"
                      title="Связать с официальным каталогом компании"
                      @click="samStore.triggerSmartMatch(item.raw_display_name)"
                    >
                      Связать
                    </button>
                  </div>
                </div>

                <!-- Вариант 3: Полностью не распознано -->
                <div v-else>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 transition-colors cursor-pointer"
                    title="Запустить семантический подбор сопоставления через ИИ и конвейер нормализации"
                    @click="samStore.triggerSmartMatch(item.raw_display_name)"
                  >
                    <Wand2 class="w-3.5 h-3.5 text-indigo-600" />
                    <span>Подобрать сопоставление</span>
                  </button>
                </div>
              </td>

              <!-- Колонка 6: Последний запуск -->
              <td class="py-3 px-4 text-slate-600 font-mono text-[11px]">
                <div v-if="item.last_launched_at">
                  {{ new Date(item.last_launched_at).toLocaleDateString('ru-RU') }}
                </div>
                <span v-else class="text-slate-400 italic">Не зафиксирован</span>
              </td>

              <!-- Колонка 7: Действия -->
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
      :subtitle="selectedItem ? getCleanName(selectedItem) : ''"
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
