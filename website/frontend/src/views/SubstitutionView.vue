<script setup lang="ts">
import { ref, onMounted, computed, watch, onBeforeUnmount } from 'vue';
import { api } from '@/services/api';
import { ImportSubstitutionItem } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import Modal from '@/components/ui/Modal.vue';
import {
  ArrowLeftRight,
  Search,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  Building2,
  ShieldCheck,
  Plus,
  Sparkles,
  Globe,
  DownloadCloud,
  Check,
  AlertCircle,
} from 'lucide-vue-next';

// Список соответствий зарубежного и отечественного ПО
const substitutions = ref<ImportSubstitutionItem[]>([]);
const loading = ref(false);
const searchQuery = ref('');
const activeCategoryFilter = ref('all');
const forceFetch = ref(false);

// Состояние онлайн-запроса к сервису Минцифры РФ
const fetchingOnline = ref(false);
const syncMessage = ref<string | null>(null);
const syncMessageType = ref<'success' | 'error'>('success');

// Подсказки автодополнения названий ПО (Bitrix AJAX API reestr.digital.gov.ru)
const suggestions = ref<string[]>([]);
const isSuggestionsOpen = ref(false);
const loadingSuggestions = ref(false);
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
const searchContainerRef = ref<HTMLElement | null>(null);

// Модальное окно добавления аналога в каталог разрешённого ПО
const isAddModalOpen = ref(false);
const selectedSub = ref<ImportSubstitutionItem | null>(null);
const addingToCatalog = ref(false);
const addSuccessMessage = ref<string | null>(null);

// Пресеты популярных категорий программного обеспечения
const categoriesPresets = [
  { label: 'Все категории', value: 'all' },
  { label: 'Офис и документы', value: '05.02', query: 'Office' },
  { label: 'Графика и САПР', value: '06', query: 'AutoCAD' },
  { label: 'СУБД и данные', value: '02.09', query: 'Oracle' },
  { label: 'Операционные системы', value: '01.01', query: 'Windows' },
  { label: 'Виртуализация', value: '02.05', query: 'VMware' },
  { label: 'Управление проектами', value: '05.13', query: 'Jira' },
  { label: 'ВКС и коммуникации', value: '05.07', query: 'Zoom' },
];

onMounted(() => {
  loadSubstitutions();
  document.addEventListener('click', handleClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside);
  if (debounceTimer) clearTimeout(debounceTimer);
});

// Закрытие выпадающего списка подсказок при клике вне контейнера
function handleClickOutside(event: MouseEvent) {
  if (searchContainerRef.value && !searchContainerRef.value.contains(event.target as Node)) {
    isSuggestionsOpen.value = false;
  }
}

// Загрузка отечественных аналогов с учётом поискового запроса и флага принудительного онлайн-запроса
async function loadSubstitutions(query?: string, isForce?: boolean) {
  loading.value = true;
  isSuggestionsOpen.value = false;
  try {
    const q = query !== undefined ? query : searchQuery.value;
    const res = await api.searchSubstitutions(q || '', isForce !== undefined ? isForce : forceFetch.value);
    substitutions.value = res.items || [];
  } catch (error) {
    console.error('Ошибка загрузки аналогов импортозамещения:', error);
  } finally {
    loading.value = false;
  }
}

// Поиск по кнопке или Enter
async function handleSearch() {
  await loadSubstitutions(searchQuery.value);
}

// Обработка ввода в поле поиска: получение подсказок автодополнения (Bitrix AJAX API)
function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer);
  const q = searchQuery.value.trim();

  if (q.length < 2) {
    suggestions.value = [];
    isSuggestionsOpen.value = false;
    return;
  }

  debounceTimer = setTimeout(async () => {
    loadingSuggestions.value = true;
    try {
      const list = await api.getProductSuggestions(q);
      suggestions.value = list || [];
      isSuggestionsOpen.value = list.length > 0;
    } catch {
      suggestions.value = [];
    } finally {
      loadingSuggestions.value = false;
    }
  }, 220);
}

// Выбор подсказки из автодополнения
function selectSuggestion(item: string) {
  searchQuery.value = item;
  isSuggestionsOpen.value = false;
  loadSubstitutions(item);
}

// Выбор категории-пресета
function selectPreset(preset: typeof categoriesPresets[0]) {
  activeCategoryFilter.value = preset.value;
  if (preset.value === 'all') {
    searchQuery.value = '';
    loadSubstitutions('');
  } else if (preset.query) {
    searchQuery.value = preset.query;
    loadSubstitutions(preset.query);
  }
}

// Прямой онлайн-запрос к reestr.digital.gov.ru с парсингом HTML и сохранением в базу
async function handleFetchOnline(overrideQuery?: string) {
  const targetQuery = (overrideQuery || searchQuery.value).trim();
  if (!targetQuery) {
    syncMessageType.value = 'error';
    syncMessage.value = 'Пожалуйста, укажите название зарубежного ПО для онлайн-поиска.';
    return;
  }

  fetchingOnline.value = true;
  syncMessage.value = null;

  try {
    const res = await api.fetchOnlineSubstitution(targetQuery);
    syncMessageType.value = res.success ? 'success' : 'error';
    syncMessage.value = res.message;
    await loadSubstitutions(targetQuery, false);
    setTimeout(() => {
      syncMessage.value = null;
    }, 5000);
  } catch (error: any) {
    syncMessageType.value = 'error';
    syncMessage.value = error?.response?.data?.detail || 'Не удалось выполнить запрос к сервису Минцифры РФ.';
  } finally {
    fetchingOnline.value = false;
  }
}

// Фильтрованный список позиций с учётом выбранного класса ПО
const filteredList = computed(() => {
  let list = substitutions.value;
  if (activeCategoryFilter.value !== 'all') {
    list = list.filter((it) => it.class_code && it.class_code.startsWith(activeCategoryFilter.value));
  }
  return list;
});

// Открытие окна добавления отечественного аналога в корпоративный каталог ПО
function openAddToCatalog(item: ImportSubstitutionItem) {
  selectedSub.value = item;
  addSuccessMessage.value = null;
  isAddModalOpen.value = true;
}

// Подтверждение внесения ПО в каталог
async function confirmAddToCatalog() {
  if (!selectedSub.value) return;
  addingToCatalog.value = true;
  try {
    await api.createCatalogItem({
      name: selectedSub.value.russian_software_name,
      vendor: selectedSub.value.owner_name || 'Отечественный разработчик',
      description: `Рекомендованный аналог для ${selectedSub.value.foreign_software_name}. Единый реестр ПО РФ №${selectedSub.value.russian_reg_number || 'б/н'}.`,
      license_type: 'Commercial',
      max_installations: 0,
      responsible_person: 'Служба импортозамещения ИТ',
      approval_status: 'approved',
    });
    addSuccessMessage.value = `ПО «${selectedSub.value.russian_software_name}» успешно добавлено в белый список Каталога!`;
    setTimeout(() => {
      isAddModalOpen.value = false;
      addSuccessMessage.value = null;
    }, 1500);
  } finally {
    addingToCatalog.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Импортозамещение ПО</h1>
          <span class="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs font-bold border border-blue-200">
            Минцифры РФ / АРПП
          </span>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Подбор отечественных аналогов для зарубежного программного обеспечения на основе данных Единого реестра и онлайн-сервиса reestr.digital.gov.ru
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          :loading="fetchingOnline"
          @click="handleFetchOnline()"
          title="Выполнить прямой парсинг страницы reestr.digital.gov.ru/import-substitution"
        >
          <Globe class="w-3.5 h-3.5 mr-1 text-blue-600" />
          Запросить онлайн в Минцифры
        </Button>
      </div>
    </div>

    <!-- Уведомление о результатах онлайн-запроса -->
    <div
      v-if="syncMessage"
      :class="[
        'p-3 rounded-lg text-xs flex items-center gap-2 transition-all',
        syncMessageType === 'success'
          ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
          : 'bg-amber-50 border border-amber-200 text-amber-800',
      ]"
    >
      <CheckCircle2 v-if="syncMessageType === 'success'" class="w-4 h-4 text-emerald-600 shrink-0" />
      <AlertCircle v-else class="w-4 h-4 text-amber-600 shrink-0" />
      <span class="font-medium">{{ syncMessage }}</span>
    </div>

    <!-- Информационные плашки -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
          <ArrowLeftRight class="w-5 h-5" />
        </div>
        <div>
          <span class="text-slate-400 block text-[11px] font-semibold uppercase">База замен Минцифры</span>
          <span class="font-extrabold text-slate-900 text-lg">{{ filteredList.length }} позиций</span>
        </div>
      </div>

      <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
          <ShieldCheck class="w-5 h-5" />
        </div>
        <div>
          <span class="text-slate-400 block text-[11px] font-semibold uppercase">Единый реестр отечественного ПО</span>
          <span class="font-extrabold text-emerald-700 text-lg">100% совместимость</span>
        </div>
      </div>

      <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center shrink-0">
          <Sparkles class="w-5 h-5" />
        </div>
        <div>
          <span class="text-slate-400 block text-[11px] font-semibold uppercase">Интеграция с каталогом</span>
          <span class="font-extrabold text-purple-700 text-lg">В 1 клик</span>
        </div>
      </div>
    </div>

    <!-- Панель поиска, автодополнения и фильтров -->
    <div class="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
      <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div ref="searchContainerRef" class="flex-1 relative">
          <Input
            v-model="searchQuery"
            placeholder="Введите зарубежное ПО (например: Photoshop, AutoCAD, Oracle, Windows, VMware, Jira, Zoom)..."
            @input="onSearchInput"
            @focus="onSearchInput"
            @keyup.enter="handleSearch"
          />

          <!-- Выпадающий список AJAX-подсказок (Bitrix API reestr.digital.gov.ru) -->
          <div
            v-if="isSuggestionsOpen && suggestions.length > 0"
            class="absolute left-0 right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-30 overflow-hidden text-xs max-h-60 overflow-y-auto"
          >
            <div class="px-3 py-1.5 bg-slate-50 border-b border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span class="font-semibold uppercase tracking-wider text-[10px]">Подсказки reestr.digital.gov.ru</span>
              <span v-if="loadingSuggestions" class="text-blue-600 flex items-center gap-1 text-[10px]">
                <RefreshCw class="w-3 h-3 animate-spin" /> поиск...
              </span>
            </div>
            <button
              v-for="(suggestion, idx) in suggestions"
              :key="idx"
              type="button"
              class="w-full text-left px-3 py-2 hover:bg-blue-50 text-slate-800 hover:text-blue-700 font-medium transition-colors border-b border-slate-50 last:border-b-0 flex items-center justify-between cursor-pointer"
              @click="selectSuggestion(suggestion)"
            >
              <span>{{ suggestion }}</span>
              <span class="text-[10px] text-slate-400">выбрать</span>
            </button>
          </div>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <label class="flex items-center gap-1.5 text-xs text-slate-600 select-none cursor-pointer bg-slate-50 px-2.5 py-2 rounded-lg border border-slate-200 hover:bg-slate-100 transition-colors">
            <input
              type="checkbox"
              v-model="forceFetch"
              class="rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5 cursor-pointer"
            />
            <span title="При поиске принудительно опрашивать онлайн-сервис Минцифры">Принудительно онлайн</span>
          </label>

          <Button variant="primary" size="sm" :loading="loading" @click="handleSearch">
            <Search class="w-4 h-4 mr-1.5" />
            Найти аналоги
          </Button>
        </div>
      </div>

      <!-- Быстрые фильтры по категориям -->
      <div class="flex flex-wrap items-center gap-1.5 pt-1">
        <button
          v-for="preset in categoriesPresets"
          :key="preset.value"
          type="button"
          :class="[
            'px-2.5 py-1 text-xs rounded-lg transition-colors cursor-pointer',
            activeCategoryFilter === preset.value
              ? 'bg-blue-600 text-white font-medium shadow-2xs'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
          ]"
          @click="selectPreset(preset)"
        >
          {{ preset.label }}
        </button>
      </div>
    </div>

    <!-- Таблица соответствий зарубежного и отечественного ПО -->
    <Card noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Зарубежный продукт</th>
              <th class="py-3 px-4">Рекомендуемый российский аналог</th>
              <th class="py-3 px-4">Правообладатель</th>
              <th class="py-3 px-4">Класс ПО</th>
              <th class="py-3 px-4 text-center">№ в Реестре РФ</th>
              <th class="py-3 px-4 text-center">Источник</th>
              <th class="py-3 px-4 text-right">Действие</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr
              v-for="item in filteredList"
              :key="item.id"
              class="hover:bg-slate-50/80 transition-colors"
            >
              <td class="py-3 px-4 font-semibold text-slate-800">
                <span class="inline-flex items-center gap-1.5 text-slate-900 font-bold">
                  {{ item.foreign_software_name }}
                </span>
              </td>
              <td class="py-3 px-4">
                <div class="font-bold text-blue-700 flex items-center gap-1.5">
                  <CheckCircle2 class="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>{{ item.russian_software_name }}</span>
                </div>
              </td>
              <td class="py-3 px-4 text-slate-600">
                <div class="flex items-center gap-1.5">
                  <Building2 class="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span>{{ item.owner_name || '—' }}</span>
                </div>
              </td>
              <td class="py-3 px-4 text-slate-600">
                <span v-if="item.class_name" class="inline-block max-w-[200px] truncate" :title="item.class_name">
                  <code class="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded font-mono mr-1">{{ item.class_code }}</code>
                  {{ item.class_name }}
                </span>
                <span v-else class="text-slate-400">—</span>
              </td>
              <td class="py-3 px-4 text-center">
                <a
                  v-if="item.russian_reg_number"
                  :href="item.registry_url || `https://reestr.digital.gov.ru/reestr/?q=${item.russian_reg_number}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-mono font-bold text-xs bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
                  title="Открыть карточку в Едином реестре Минцифры"
                >
                  <span>№ {{ item.russian_reg_number }}</span>
                  <ExternalLink class="w-3 h-3 text-blue-500" />
                </a>
                <span v-else class="text-slate-400 font-mono text-[11px]">—</span>
              </td>
              <td class="py-3 px-4 text-center">
                <Badge
                  :variant="item.source === 'registry' ? 'success' : 'secondary'"
                  size="sm"
                >
                  {{ item.source === 'registry' ? 'Реестр РФ' : 'Каталог АРПП' }}
                </Badge>
              </td>
              <td class="py-3 px-4 text-right">
                <Button
                  variant="outline"
                  size="sm"
                  class="text-xs"
                  @click="openAddToCatalog(item)"
                >
                  <Plus class="w-3.5 h-3.5 mr-1 text-emerald-600" />
                  В каталог
                </Button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Пустое состояние -->
        <div v-if="filteredList.length === 0" class="text-center py-10 px-4 text-slate-500 space-y-3">
          <ArrowLeftRight class="w-8 h-8 text-slate-400 mx-auto" />
          <div>
            <p class="font-medium text-sm text-slate-800">
              По запросу «{{ searchQuery || 'все категории' }}» аналогов в локальной базе не найдено
            </p>
            <p class="text-xs text-slate-400 mt-1 max-w-md mx-auto">
              Вы можете запросить актуальные сведения напрямую из сервиса импортозамещения reestr.digital.gov.ru в режиме реального времени.
            </p>
          </div>

          <div v-if="searchQuery" class="pt-2">
            <Button
              variant="primary"
              size="sm"
              :loading="fetchingOnline"
              @click="handleFetchOnline(searchQuery)"
            >
              <Globe class="w-4 h-4 mr-1.5" />
              Запросить «{{ searchQuery }}» онлайн в reestr.digital.gov.ru
            </Button>
          </div>
        </div>
      </div>
    </Card>

    <!-- Модальное окно добавления в белый список каталога -->
    <Modal
      v-model="isAddModalOpen"
      title="Добавить отечественный аналог в каталог"
      maxWidth="md"
    >
      <div v-if="selectedSub" class="space-y-4">
        <div v-if="addSuccessMessage" class="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
          <CheckCircle2 class="w-4 h-4 text-emerald-600" />
          <span>{{ addSuccessMessage }}</span>
        </div>

        <div class="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-2 text-xs">
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Отечественное ПО</span>
            <span class="font-bold text-slate-900 text-sm">{{ selectedSub.russian_software_name }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Заменяемый зарубежный продукт</span>
            <span class="font-semibold text-slate-700">{{ selectedSub.foreign_software_name }}</span>
          </div>
          <div class="grid grid-cols-2 gap-2 pt-1 border-t border-slate-200">
            <div>
              <span class="text-slate-400 block text-[10px] uppercase font-bold">Правообладатель</span>
              <span class="font-medium text-slate-800">{{ selectedSub.owner_name || '—' }}</span>
            </div>
            <div>
              <span class="text-slate-400 block text-[10px] uppercase font-bold">Номер в Реестре ПО РФ</span>
              <span class="font-mono font-bold text-blue-700">№ {{ selectedSub.russian_reg_number || 'б/н' }}</span>
            </div>
          </div>
        </div>

        <p class="text-xs text-slate-600 leading-relaxed">
          Программа будет зарегистрирована в корпоративном <strong>Каталоге разрешённого ПО</strong> со статусом <em>«Одобрено»</em>. При последующих инвентаризациях хостов рабочие станции с этой программой будут считаться соответствующими требованиям комплаенса и импортозамещения.
        </p>

        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" @click="isAddModalOpen = false">Отмена</Button>
          <Button variant="primary" size="sm" :loading="addingToCatalog" @click="confirmAddToCatalog">
            Подтвердить добавление
          </Button>
        </div>
      </div>
    </Modal>
  </div>
</template>
