<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { SoftwareCatalogItem, SoftwareClassifier, SoftwareCategory, LicenseType } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import Select from '@/components/ui/Select.vue';
import Modal from '@/components/ui/Modal.vue';
import {
  CheckCircle2,
  Plus,
  Search,
  Edit,
  Trash2,
  ShieldCheck,
  Building2,
  FolderTree,
  User,
  AlertCircle,
  Landmark,
} from 'lucide-vue-next';

const catalog = ref<SoftwareCatalogItem[]>([]);
const classifiers = ref<SoftwareClassifier[]>([]);
const categories = ref<SoftwareCategory[]>([]);
const loading = ref(false);
const searchQuery = ref('');
const licenseTypeFilter = ref('all');

// Modals
const isModalOpen = ref(false);
const editingItem = ref<Partial<SoftwareCatalogItem> | null>(null);

const form = ref({
  name: '',
  vendor: '',
  description: '',
  classifier_id: null as number | null,
  category_id: 1,
  license_type: 'Commercial' as LicenseType,
  max_installations: 100,
  responsible_person: 'Сидоров К. (ИТ-отдел)',
  approval_status: 'approved' as 'approved' | 'review' | 'rejected',
});

onMounted(async () => {
  await Promise.all([loadCatalog(), loadClassifiers(), loadCategories()]);
});

async function loadCatalog() {
  loading.value = true;
  try {
    catalog.value = await api.getCatalog();
  } finally {
    loading.value = false;
  }
}

async function loadClassifiers() {
  classifiers.value = await api.getClassifiers();
}

async function loadCategories() {
  categories.value = await api.getCategories();
}

const filteredCatalog = computed(() => {
  return catalog.value.filter((item) => {
    const matchSearch =
      !searchQuery.value ||
      item.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      item.vendor?.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      item.responsible_person?.toLowerCase().includes(searchQuery.value.toLowerCase());

    const matchType =
      licenseTypeFilter.value === 'all' ||
      item.license_type === licenseTypeFilter.value;

    return matchSearch && matchType;
  });
});

function openCreate() {
  editingItem.value = null;
  form.value = {
    name: '',
    vendor: 'Microsoft Corporation',
    description: 'Корпоративное программное обеспечение',
    classifier_id: classifiers.value[0]?.id || null,
    category_id: 1,
    license_type: 'Commercial',
    max_installations: 50,
    responsible_person: 'Сидоров К. (ИТ-отдел)',
    approval_status: 'approved',
  };
  isModalOpen.value = true;
}

function openEdit(item: SoftwareCatalogItem) {
  editingItem.value = item;
  form.value = {
    name: item.name,
    vendor: item.vendor || '',
    description: item.description || '',
    classifier_id: item.classifier_id || null,
    category_id: item.category_id || 1,
    license_type: item.license_type,
    max_installations: item.max_installations,
    responsible_person: item.responsible_person || '',
    approval_status: item.approval_status || 'approved',
  };
  isModalOpen.value = true;
}

async function saveCatalogItem() {
  if (!form.value.name.trim()) return;
  if (editingItem.value?.id) {
    await api.updateCatalogItem(editingItem.value.id, form.value);
  } else {
    await api.createCatalogItem(form.value);
  }
  isModalOpen.value = false;
  await loadCatalog();
}

async function deleteItem(id: string) {
  if (confirm('Удалить ПО из корпоративного каталога разрешённых?')) {
    await api.deleteCatalogItem(id);
    await loadCatalog();
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Каталог разрешённого ПО (Белый список)</h1>
          <span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold border border-emerald-200">
            Корпоративный эталон
          </span>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Официально согласованный стек ПО компании, лимиты лицензий, ответственные и статус одобрения
        </p>
      </div>

      <Button variant="primary" size="sm" @click="openCreate">
        <Plus class="w-4 h-4 mr-1.5" />
        Добавить ПО в каталог
      </Button>
    </div>

    <!-- Filters Bar -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
      <div class="w-full sm:w-80">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по названию, вендору, ответственному..."
        />
      </div>

      <div class="flex items-center gap-2">
        <Select
          v-model="licenseTypeFilter"
          placeholder="Тип лицензии"
          :options="[
            { label: 'Все типы лицензий', value: 'all' },
            { label: 'Commercial', value: 'Commercial' },
            { label: 'Open Source', value: 'Open Source' },
            { label: 'Freeware', value: 'Freeware' },
            { label: 'Trial', value: 'Trial' },
          ]"
        />
      </div>
    </div>

    <!-- Catalog Table -->
    <Card noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Наименование ПО и вендор</th>
              <th class="py-3 px-4">Тип лицензии</th>
              <th class="py-3 px-4 text-center">Доступно мест (Лимит)</th>
              <th class="py-3 px-4 text-center">Фактически уст.</th>
              <th class="py-3 px-4">Ответственный</th>
              <th class="py-3 px-4 text-center">Статус одобрения</th>
              <th class="py-3 px-4 text-right">Действия</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="item in filteredCatalog" :key="item.id" class="hover:bg-slate-50/80 transition-colors">
              <td class="py-3 px-4 font-semibold text-slate-900">
                <div class="flex items-center gap-2">
                  <ShieldCheck class="w-4 h-4 text-blue-600 shrink-0" />
                  <span>{{ item.name }}</span>
                </div>
                <div class="text-[11px] text-slate-500 font-normal mt-0.5">
                  {{ item.vendor }}
                </div>
              </td>
              <td class="py-3 px-4">
                <Badge
                  :variant="item.license_type === 'Commercial' ? 'info' : item.license_type === 'Open Source' ? 'success' : 'default'"
                  size="sm"
                >
                  {{ item.license_type }}
                </Badge>
              </td>
              <td class="py-3 px-4 text-center font-mono font-bold text-slate-700">
                {{ item.max_installations === 0 ? '∞ (Без огр.)' : item.max_installations }}
              </td>
              <td class="py-3 px-4 text-center font-mono font-bold">
                <span
                  :class="[
                    item.max_installations > 0 && (item.active_installations_count || 0) > item.max_installations
                      ? 'text-red-600 bg-red-50 px-2 py-0.5 rounded border border-red-200'
                      : 'text-slate-900',
                  ]"
                >
                  {{ item.active_installations_count || 0 }}
                </span>
              </td>
              <td class="py-3 px-4 text-slate-700">
                <div class="flex items-center gap-1.5">
                  <User class="w-3.5 h-3.5 text-slate-400" />
                  <span>{{ item.responsible_person || '—' }}</span>
                </div>
              </td>
              <td class="py-3 px-4 text-center">
                <Badge
                  :variant="item.approval_status === 'approved' ? 'success' : item.approval_status === 'review' ? 'warning' : 'destructive'"
                  size="sm"
                >
                  {{ item.approval_status === 'approved' ? 'Одобрено' : item.approval_status === 'review' ? 'На согласовании' : 'Отклонено' }}
                </Badge>
              </td>
              <td class="py-3 px-4 text-right">
                <div class="flex items-center justify-end gap-1">
                  <button
                    type="button"
                    title="Редактировать"
                    class="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                    @click="openEdit(item)"
                  >
                    <Edit class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Удалить"
                    class="p-1.5 rounded-md hover:bg-red-50 text-red-600 transition cursor-pointer"
                    @click="deleteItem(item.id)"
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

    <!-- Create/Edit Modal -->
    <Modal
      v-model="isModalOpen"
      :title="editingItem ? 'Редактирование ПО каталога' : 'Добавить ПО в белый список'"
      maxWidth="lg"
    >
      <form class="space-y-4" @submit.prevent="saveCatalogItem">
        <Input
          v-model="form.name"
          label="Официальное наименование ПО"
          placeholder="Microsoft Office 2021 Professional Plus"
          required
        />
        <Input
          v-model="form.vendor"
          label="Вендор / Правообладатель"
          placeholder="Microsoft Corporation"
          required
        />
        <div class="grid grid-cols-2 gap-3">
          <Select
            v-model="form.license_type"
            label="Тип лицензии"
            :options="[
              { label: 'Commercial (Коммерческая)', value: 'Commercial' },
              { label: 'Open Source (Открытая)', value: 'Open Source' },
              { label: 'Freeware (Бесплатная)', value: 'Freeware' },
              { label: 'Trial (Пробная)', value: 'Trial' },
            ]"
          />
          <Input
            v-model.number="form.max_installations"
            label="Доступно мест (0 = без ограничений)"
            type="number"
          />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <Input
            v-model="form.responsible_person"
            label="Ответственный сотрудник"
            placeholder="Сидоров К. (ИТ-отдел)"
          />
          <Select
            v-model="form.approval_status"
            label="Статус одобрения"
            :options="[
              { label: 'Одобрено (Approved)', value: 'approved' },
              { label: 'На рассмотрении (Review)', value: 'review' },
              { label: 'Отклонено (Rejected)', value: 'rejected' },
            ]"
          />
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" type="button" @click="isModalOpen = false">Отмена</Button>
          <Button variant="primary" size="sm" type="submit">Сохранить</Button>
        </div>
      </form>
    </Modal>
  </div>
</template>
