<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { useSamStore } from '@/stores/sam';
import { License, SoftwareCatalogItem, LicenseModel } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import Select from '@/components/ui/Select.vue';
import Modal from '@/components/ui/Modal.vue';
import {
  KeyRound,
  Plus,
  Search,
  Edit,
  Trash2,
  FileText,
  DollarSign,
  Calendar,
  Sparkles,
} from 'lucide-vue-next';

const samStore = useSamStore();

const licenses = ref<License[]>([]);
const catalog = ref<SoftwareCatalogItem[]>([]);
const loading = ref(false);
const searchQuery = ref('');

// Модальные окна
const isModalOpen = ref(false);
const editingItem = ref<Partial<License> | null>(null);

const form = ref({
  software_id: '',
  license_name: '',
  license_type: 'Платный',
  license_model: 'per_device' as LicenseModel,
  total_purchased: 1,
  unit_cost: 0,
  currency: 'RUB',
  valid_from: '',
  valid_to: '',
  eula_text: '',
});

onMounted(async () => {
  await Promise.all([loadLicenses(), loadCatalog()]);
});

async function loadLicenses() {
  loading.value = true;
  try {
    licenses.value = await api.getLicenses();
  } finally {
    loading.value = false;
  }
}

async function loadCatalog() {
  catalog.value = await api.getCatalog();
}

function formatRub(val?: number) {
  if (val === undefined || val === null) return '0 ₽';
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(val);
}

const filteredLicenses = computed(() => {
  return licenses.value.filter((lic) => {
    return (
      !searchQuery.value ||
      lic.license_name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      lic.software_name?.toLowerCase().includes(searchQuery.value.toLowerCase())
    );
  });
});

function openCreate() {
  editingItem.value = null;
  form.value = {
    software_id: catalog.value[0]?.id || '',
    license_name: '',
    license_type: 'Платный',
    license_model: 'per_device',
    total_purchased: 1,
    unit_cost: 0,
    currency: 'RUB',
    valid_from: '',
    valid_to: '',
    eula_text: '',
  };
  isModalOpen.value = true;
}

function openEdit(lic: License) {
  editingItem.value = lic;
  form.value = {
    software_id: lic.software_id,
    license_name: lic.license_name,
    license_type: lic.license_type,
    license_model: lic.license_model,
    total_purchased: lic.total_purchased,
    unit_cost: lic.unit_cost,
    currency: lic.currency,
    valid_from: lic.valid_from || '',
    valid_to: lic.valid_to || '',
    eula_text: lic.eula_text || '',
  };
  isModalOpen.value = true;
}

async function saveLicense() {
  if (!form.value.license_name.trim()) return;
  if (editingItem.value?.id) {
    await api.updateLicense(editingItem.value.id, form.value);
  } else {
    await api.createLicense(form.value);
  }
  isModalOpen.value = false;
  await loadLicenses();
}

async function deleteLicense(id: string) {
  if (confirm('Удалить данную лицензию?')) {
    await api.deleteLicense(id);
    await loadLicenses();
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Лицензии и соглашения</h1>
        <p class="text-xs text-slate-500 mt-1">
          Учёт приобретённых лицензий, стоимости, сроков действия и аудит условий соглашений (EULA)
        </p>
      </div>

      <Button variant="primary" size="sm" @click="openCreate">
        <Plus class="w-4 h-4 mr-1.5" />
        Зарегистрировать лицензию
      </Button>
    </div>

    <!-- Панель фильтров -->
    <div class="flex items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
      <div class="w-full sm:w-80">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по названию лицензии, ПО..."
        />
      </div>
    </div>

    <!-- Таблица лицензий -->
    <Card noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Наименование лицензии / ПО</th>
              <th class="py-3 px-4">Вид лицензии</th>
              <th class="py-3 px-4">Модель</th>
              <th class="py-3 px-4 text-center">Куплено мест</th>
              <th class="py-3 px-4 text-right">Стоимость 1 шт.</th>
              <th class="py-3 px-4 text-right">Общая сумма</th>
              <th class="py-3 px-4 text-center">Срок действия</th>
              <th class="py-3 px-4 text-right">Действия</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="lic in filteredLicenses" :key="lic.id" class="hover:bg-slate-50/80 transition-colors">
              <td class="py-3 px-4">
                <div class="font-semibold text-slate-900 flex items-center gap-2">
                  <KeyRound class="w-4 h-4 text-slate-400 shrink-0" />
                  <span>{{ lic.license_name }}</span>
                </div>
                <div class="text-[11px] text-blue-600 font-medium mt-0.5">
                  {{ lic.software_name }}
                </div>
              </td>
              <td class="py-3 px-4">
                <Badge
                  :variant="lic.license_type === 'Платный' ? 'info' : lic.license_type === 'Бесплатный' ? 'success' : 'warning'"
                  size="sm"
                >
                  {{ lic.license_type }}
                </Badge>
              </td>
              <td class="py-3 px-4 text-slate-600 font-mono">
                {{ lic.license_model === 'per_device' ? 'на устройство' : lic.license_model === 'per_user' ? 'на пользователя' : 'site license' }}
              </td>
              <td class="py-3 px-4 text-center font-mono font-bold text-slate-800">
                {{ lic.total_purchased }}
              </td>
              <td class="py-3 px-4 text-right font-mono text-slate-700">
                {{ formatRub(lic.unit_cost) }}
              </td>
              <td class="py-3 px-4 text-right font-mono font-bold text-slate-900">
                {{ formatRub(lic.unit_cost * lic.total_purchased) }}
              </td>
              <td class="py-3 px-4 text-center text-slate-500 font-mono text-[11px]">
                {{ lic.valid_to || 'Бессрочная' }}
              </td>
              <td class="py-3 px-4 text-right">
                <div class="flex items-center justify-end gap-1">
                  <button
                    type="button"
                    title="Запустить ИИ-анализ соглашения (EULA)"
                    class="p-1.5 rounded-md hover:bg-indigo-50 text-indigo-600 transition cursor-pointer"
                    @click="samStore.triggerEulaAnalysis(lic.id)"
                  >
                    <Sparkles class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Редактировать"
                    class="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                    @click="openEdit(lic)"
                  >
                    <Edit class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Удалить"
                    class="p-1.5 rounded-md hover:bg-red-50 text-red-600 transition cursor-pointer"
                    @click="deleteLicense(lic.id)"
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

    <!-- Модальное окно создания / редактирования -->
    <Modal
      v-model="isModalOpen"
      :title="editingItem ? 'Редактирование лицензии' : 'Регистрация лицензии'"
      maxWidth="lg"
    >
      <form class="space-y-4" @submit.prevent="saveLicense">
        <Select
          v-model="form.software_id"
          label="Связанное программное обеспечение"
          :options="catalog.map(c => ({ label: `${c.name} (${c.vendor})`, value: c.id }))"
        />
        <Input
          v-model="form.license_name"
          label="Наименование лицензии / договора"
          placeholder="Microsoft Volume Licensing Agreement"
          required
        />
        <div class="grid grid-cols-2 gap-3">
          <Select
            v-model="form.license_type"
            label="Вид лицензии"
            :options="[
              { label: 'Платный', value: 'Платный' },
              { label: 'Условно бесплатный', value: 'Условно бесплатный' },
              { label: 'Бесплатный', value: 'Бесплатный' },
            ]"
          />
          <Select
            v-model="form.license_model"
            label="Модель лицензирования"
            :options="[
              { label: 'На устройство (per_device)', value: 'per_device' },
              { label: 'На пользователя (per_user)', value: 'per_user' },
              { label: 'На всю компанию (site)', value: 'site' },
            ]"
          />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <Input
            v-model.number="form.total_purchased"
            label="Количество купленных лицензий"
            type="number"
            required
          />
          <Input
            v-model.number="form.unit_cost"
            label="Стоимость 1 лицензии (руб.)"
            type="number"
          />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <Input
            v-model="form.valid_from"
            label="Дата начала"
            type="date"
          />
          <Input
            v-model="form.valid_to"
            label="Дата окончания"
            type="date"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-700 mb-1">Текст соглашения EULA (для ИИ анализа)</label>
          <textarea
            v-model="form.eula_text"
            rows="3"
            placeholder="Вставьте фрагмент или полный текст условий лицензии..."
            class="w-full px-3 py-2 text-xs font-mono bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20"
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
