<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '@/services/api';
import { SoftwareCategory } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import Select from '@/components/ui/Select.vue';
import Modal from '@/components/ui/Modal.vue';
import {
  Tags,
  Plus,
  Edit,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
} from 'lucide-vue-next';

const categories = ref<SoftwareCategory[]>([]);
const loading = ref(false);

// Модальные окна
const isModalOpen = ref(false);
const editingCategory = ref<SoftwareCategory | null>(null);

const form = ref({
  name: '',
  description: '',
  is_problematic: false,
  risk_level: 'none' as 'none' | 'low' | 'medium' | 'critical',
  color_hex: '#10b981',
});

onMounted(() => {
  loadCategories();
});

async function loadCategories() {
  loading.value = true;
  try {
    categories.value = await api.getCategories();
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingCategory.value = null;
  form.value = {
    name: '',
    description: '',
    is_problematic: false,
    risk_level: 'none',
    color_hex: '#3b82f6',
  };
  isModalOpen.value = true;
}

function openEdit(cat: SoftwareCategory) {
  editingCategory.value = cat;
  form.value = {
    name: cat.name,
    description: cat.description || '',
    is_problematic: cat.is_problematic,
    risk_level: cat.risk_level,
    color_hex: cat.color_hex || '#3b82f6',
  };
  isModalOpen.value = true;
}

async function saveCategory() {
  if (!form.value.name.trim()) return;
  if (editingCategory.value) {
    await api.updateCategory(editingCategory.value.id, form.value);
  } else {
    await api.createCategory(form.value);
  }
  isModalOpen.value = false;
  await loadCategories();
}

async function deleteCategory(id: number) {
  if (confirm('Вы уверены, что хотите удалить эту категорию?')) {
    await api.deleteCategory(id);
    await loadCategories();
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Категории программного обеспечения</h1>
        <p class="text-xs text-slate-500 mt-1">
          Политика классификации софта: Актуальный, Устаревший, Запрещенный к использованию и уровень риска
        </p>
      </div>

      <Button variant="primary" size="sm" @click="openCreate">
        <Plus class="w-4 h-4 mr-1.5" />
        Создать категорию
      </Button>
    </div>

    <!-- Сетка категорий -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <Card
        v-for="cat in categories"
        :key="cat.id"
        :class="[
          'relative transition-all',
          cat.is_problematic ? 'border-red-200 bg-red-50/10' : 'border-slate-200',
        ]"
      >
        <div class="space-y-3">
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-2.5">
              <span
                class="w-3.5 h-3.5 rounded-full shrink-0 shadow-2xs"
                :style="{ backgroundColor: cat.color_hex || '#6B7280' }"
              ></span>
              <h3 class="font-bold text-slate-900 text-sm">{{ cat.name }}</h3>
            </div>

            <div class="flex items-center gap-1">
              <button
                type="button"
                class="p-1 hover:bg-slate-100 rounded text-slate-500 transition cursor-pointer"
                @click="openEdit(cat)"
              >
                <Edit class="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                class="p-1 hover:bg-red-50 rounded text-red-600 transition cursor-pointer"
                @click="deleteCategory(cat.id)"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <p class="text-xs text-slate-600 leading-relaxed min-h-[38px]">
            {{ cat.description || 'Описание не заполнено.' }}
          </p>

          <div class="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <div class="flex items-center gap-1.5">
              <span class="text-slate-400">Проблемная:</span>
              <Badge :variant="cat.is_problematic ? 'destructive' : 'success'" size="sm">
                {{ cat.is_problematic ? 'Да (Флаг проблемы)' : 'Нет (Норма)' }}
              </Badge>
            </div>

            <div class="flex items-center gap-1">
              <span class="text-slate-400">Уровень риска:</span>
              <span class="font-semibold uppercase text-[10px]" :class="cat.risk_level === 'critical' ? 'text-red-600 font-bold' : cat.risk_level === 'medium' ? 'text-amber-600' : 'text-slate-600'">
                {{ cat.risk_level }}
              </span>
            </div>
          </div>
        </div>
      </Card>
    </div>

    <!-- Модальное окно создания / редактирования -->
    <Modal
      v-model="isModalOpen"
      :title="editingCategory ? 'Редактирование категории' : 'Новая категория софта'"
      maxWidth="md"
    >
      <form class="space-y-4" @submit.prevent="saveCategory">
        <Input
          v-model="form.name"
          label="Наименование категории"
          placeholder="например: Запрещенный к использованию"
          required
        />
        <div>
          <label class="block text-xs font-medium text-slate-700 mb-1">Описание категории</label>
          <textarea
            v-model="form.description"
            rows="3"
            placeholder="Опишите правила и политику для данного софта..."
            class="w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>

        <div class="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between">
          <div>
            <span class="text-xs font-semibold text-slate-800 block">Флаг проблемной категории</span>
            <span class="text-[11px] text-slate-500">Подсвечивать на главном дашборде и вызывать комплаенс-алерты</span>
          </div>
          <input
            v-model="form.is_problematic"
            type="checkbox"
            class="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 cursor-pointer"
          />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <Select
            v-model="form.risk_level"
            label="Уровень комплаенс-риска"
            :options="[
              { label: 'None (Без риска)', value: 'none' },
              { label: 'Low (Низкий)', value: 'low' },
              { label: 'Medium (Средний)', value: 'medium' },
              { label: 'Critical (Критический)', value: 'critical' },
            ]"
          />
          <Input
            v-model="form.color_hex"
            label="Цвет метки (HEX)"
            placeholder="#ef4444"
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
