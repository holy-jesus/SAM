<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { Employee, Computer, EmployeeStatus, EmployeeCategory } from '@/types';
import Card from '@/components/ui/Card.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Input from '@/components/ui/Input.vue';
import Select from '@/components/ui/Select.vue';
import Modal from '@/components/ui/Modal.vue';
import {
  Users,
  Plus,
  Search,
  Edit,
  Trash2,
  Monitor,
  AlertTriangle,
  Mail,
  Briefcase,
  Building,
  CheckCircle2,
  Eye,
  Shield,
  ShieldCheck,
  Check,
  RotateCcw,
  RefreshCw,
} from 'lucide-vue-next';

const employees = ref<Employee[]>([]);
const categories = ref<EmployeeCategory[]>([]);
const loading = ref(false);
const searchQuery = ref('');
const statusFilter = ref('all');
const categoryFilter = ref('all');

// Модальные окна
const isCreateModalOpen = ref(false);
const isViewModalOpen = ref(false);
const isCategoriesModalOpen = ref(false);
const editingEmployee = ref<Partial<Employee> | null>(null);
const editingCategory = ref<Partial<EmployeeCategory> | null>(null);
const selectedEmployeeDetails = ref<(Employee & { computers: Computer[] }) | null>(null);

const form = ref<{
  full_name: string;
  email: string;
  department: string;
  position: string;
  status: EmployeeStatus;
  user_category: string;
}>({
  full_name: '',
  email: '',
  department: '',
  position: '',
  status: 'active',
  user_category: '',
});

const categoryForm = ref({
  name: '',
  description: '',
  allowed_software_list: '',
});

onMounted(async () => {
  await Promise.all([loadEmployees(), loadCategories()]);
});

async function loadEmployees() {
  loading.value = true;
  try {
    employees.value = await api.getEmployees();
  } finally {
    loading.value = false;
  }
}

async function loadCategories() {
  try {
    categories.value = await api.getEmployeeCategories();
  } catch (err) {
    console.error('Ошибка загрузки категорий сотрудников:', err);
  }
}

const filteredEmployees = computed(() => {
  return employees.value.filter((emp) => {
    const matchSearch =
      !searchQuery.value ||
      emp.full_name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      emp.email?.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      emp.department?.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      (emp.user_category && emp.user_category.toLowerCase().includes(searchQuery.value.toLowerCase()));

    const matchStatus = statusFilter.value === 'all' || emp.status === statusFilter.value;
    const matchCategory =
      categoryFilter.value === 'all' ||
      (categoryFilter.value === 'none' && !emp.user_category) ||
      emp.user_category === categoryFilter.value;

    return matchSearch && matchStatus && matchCategory;
  });
});

function openCreate() {
  editingEmployee.value = null;
  form.value = {
    full_name: '',
    email: '',
    department: '',
    position: '',
    status: 'active',
    user_category: categories.value[0]?.name || '',
  };
  isCreateModalOpen.value = true;
}

function openEdit(emp: Employee) {
  editingEmployee.value = emp;
  form.value = {
    full_name: emp.full_name,
    email: emp.email || '',
    department: emp.department || '',
    position: emp.position || '',
    status: emp.status,
    user_category: emp.user_category || '',
  };
  isCreateModalOpen.value = true;
}

async function saveEmployee() {
  if (!form.value.full_name.trim()) return;
  if (editingEmployee.value?.id) {
    await api.updateEmployee(editingEmployee.value.id, form.value);
  } else {
    await api.createEmployee(form.value);
  }
  isCreateModalOpen.value = false;
  await Promise.all([loadEmployees(), loadCategories()]);
}

async function deleteEmployee(id: string) {
  if (confirm('Вы действительно хотите удалить данного сотрудника?')) {
    await api.deleteEmployee(id);
    await Promise.all([loadEmployees(), loadCategories()]);
  }
}

async function viewEmployee(emp: Employee) {
  const details = await api.getEmployee(emp.id);
  selectedEmployeeDetails.value = details;
  isViewModalOpen.value = true;
}

function openCategoriesManager() {
  editingCategory.value = null;
  categoryForm.value = {
    name: '',
    description: '',
    allowed_software_list: '',
  };
  isCategoriesModalOpen.value = true;
}

function startEditCategory(cat: EmployeeCategory) {
  editingCategory.value = cat;
  categoryForm.value = {
    name: cat.name,
    description: cat.description || '',
    allowed_software_list: cat.allowed_software_list || '',
  };
}

function cancelEditCategory() {
  editingCategory.value = null;
  categoryForm.value = {
    name: '',
    description: '',
    allowed_software_list: '',
  };
}

async function saveCategory() {
  if (!categoryForm.value.name.trim()) return;
  if (editingCategory.value?.id) {
    await api.updateEmployeeCategory(editingCategory.value.id, categoryForm.value);
  } else {
    await api.createEmployeeCategory(categoryForm.value);
  }
  cancelEditCategory();
  await loadCategories();
}

async function deleteCategory(id: number) {
  if (confirm('Удалить категорию персонала? Связанные сотрудники потеряют привязку к политике ПО.')) {
    await api.deleteEmployeeCategory(id);
    await loadCategories();
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Сотрудники компании</h1>
        <p class="text-xs text-slate-500 mt-1">
          Учёт персонала, закрепление рабочих станций, категории ролей и политики разрешённого ПО
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" @click="openCategoriesManager">
          <ShieldCheck class="w-4 h-4 mr-1.5 text-blue-600" />
          Категории и политики ПО
        </Button>
        <Button variant="primary" size="sm" @click="openCreate">
          <Plus class="w-4 h-4 mr-1.5" />
          Добавить сотрудника
        </Button>
      </div>
    </div>

    <!-- Панель фильтров -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
      <div class="w-full sm:w-80">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по ФИО, email, отделу, роли..."
        />
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <Select
          v-model="categoryFilter"
          placeholder="Все категории"
          :options="[
            { label: 'Все категории', value: 'all' },
            { label: 'Без категории', value: 'none' },
            ...categories.map(c => ({ label: c.name, value: c.name }))
          ]"
        />
        <Select
          v-model="statusFilter"
          placeholder="Все статусы"
          :options="[
            { label: 'Все статусы', value: 'all' },
            { label: 'Активен', value: 'active' },
            { label: 'Уволен', value: 'dismissed' },
            { label: 'В отпуске', value: 'on_leave' },
          ]"
        />
      </div>
    </div>

    <!-- Таблица сотрудников -->
    <Card noPadding>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3 px-4">Сотрудник</th>
              <th class="py-3 px-4">Отдел и Должность</th>
              <th class="py-3 px-4">Категория / Политика ПО</th>
              <th class="py-3 px-4 text-center">Привязанные ПК</th>
              <th class="py-3 px-4 text-center">Статус</th>
              <th class="py-3 px-4 text-right">Действия</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="emp in filteredEmployees" :key="emp.id" class="hover:bg-slate-50/80 transition-colors">
              <td class="py-3 px-4">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-full bg-slate-100 text-slate-700 font-bold flex items-center justify-center text-xs border border-slate-200">
                    {{ emp.full_name.charAt(0) }}
                  </div>
                  <div>
                    <span class="font-semibold text-slate-900 block">{{ emp.full_name }}</span>
                    <span class="text-[11px] text-slate-400 flex items-center gap-1">
                      <Mail class="w-3 h-3 text-slate-400" />
                      {{ emp.email || '—' }}
                    </span>
                  </div>
                </div>
              </td>
              <td class="py-3 px-4 text-slate-700">
                <div class="font-medium text-slate-900">{{ emp.department || '—' }}</div>
                <div class="text-[11px] text-slate-500">{{ emp.position || '—' }}</div>
              </td>
              <td class="py-3 px-4">
                <span
                  v-if="emp.user_category"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-800 border border-blue-200"
                >
                  <Shield class="w-3.5 h-3.5 text-blue-600 shrink-0" />
                  {{ emp.user_category }}
                </span>
                <span v-else class="text-slate-400 italic text-[11px]">
                  Не назначена
                </span>
              </td>
              <td class="py-3 px-4 text-center">
                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 font-medium text-xs transition cursor-pointer"
                  @click="viewEmployee(emp)"
                >
                  <Monitor class="w-3.5 h-3.5" />
                  <span>{{ emp.computers_count ?? (emp.computers?.length ?? 0) }} ПК</span>
                </button>
                <div v-if="emp.status === 'dismissed' && (emp.computers_count ?? (emp.computers?.length ?? 0)) > 0" class="mt-1">
                  <Badge variant="warning" size="sm" class="text-[10px]">Риск: Зомби-софт</Badge>
                </div>
              </td>
              <td class="py-3 px-4 text-center">
                <Badge
                  :variant="emp.status === 'active' ? 'success' : emp.status === 'dismissed' ? 'destructive' : 'warning'"
                  size="sm"
                >
                  {{ emp.status === 'active' ? 'Активен' : emp.status === 'dismissed' ? 'Уволен' : 'В отпуске' }}
                </Badge>
              </td>
              <td class="py-3 px-4 text-right">
                <div class="flex items-center justify-end gap-1">
                  <button
                    type="button"
                    title="Карточка сотрудника и ПК"
                    class="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                    @click="viewEmployee(emp)"
                  >
                    <Eye class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Редактировать"
                    class="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                    @click="openEdit(emp)"
                  >
                    <Edit class="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title="Удалить"
                    class="p-1.5 rounded-md hover:bg-red-50 text-red-600 transition cursor-pointer"
                    @click="deleteEmployee(emp.id)"
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

    <!-- Модальное окно создания / редактирования сотрудника -->
    <Modal
      v-model="isCreateModalOpen"
      :title="editingEmployee ? 'Редактирование сотрудника' : 'Новый сотрудник'"
      maxWidth="md"
    >
      <form class="space-y-4" @submit.prevent="saveEmployee">
        <Input
          v-model="form.full_name"
          label="ФИО сотрудника"
          placeholder="Иванов Иван Иванович"
          required
        />
        <Input
          v-model="form.email"
          label="Рабочий Email"
          placeholder="ivanov@company.ru"
          type="email"
        />
        <Input
          v-model="form.department"
          label="Отдел / Подразделение"
          placeholder="Отдел разработки"
        />
        <Input
          v-model="form.position"
          label="Должность"
          placeholder="Ведущий инженер"
        />
        <Select
          v-model="form.user_category"
          label="Категория сотрудника (Политика ПО)"
          placeholder="Выберите категорию..."
          :options="[
            { label: '— Без категории —', value: '' },
            ...categories.map(c => ({ label: `${c.name} (${c.description || 'без описания'})`, value: c.name }))
          ]"
        />
        <Select
          v-model="form.status"
          label="Статус сотрудника"
          :options="[
            { label: 'Активен (Active)', value: 'active' },
            { label: 'Уволен (Dismissed)', value: 'dismissed' },
            { label: 'В отпуске (On Leave)', value: 'on_leave' },
          ]"
        />
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" type="button" @click="isCreateModalOpen = false">Отмена</Button>
          <Button variant="primary" size="sm" type="submit">Сохранить</Button>
        </div>
      </form>
    </Modal>

    <!-- Модальное окно детальной информации о сотруднике и ПК -->
    <Modal
      v-model="isViewModalOpen"
      :title="selectedEmployeeDetails?.full_name || 'Карточка сотрудника'"
      subtitle="Закреплённое оборудование и установленные программы"
      maxWidth="2xl"
    >
      <div v-if="selectedEmployeeDetails" class="space-y-5">
        <!-- Профиль сотрудника -->
        <div class="flex items-start justify-between bg-slate-50 p-4 rounded-xl border border-slate-200">
          <div>
            <h4 class="font-bold text-slate-900 text-base">{{ selectedEmployeeDetails.full_name }}</h4>
            <p class="text-xs text-slate-600 mt-0.5">
              {{ selectedEmployeeDetails.position }} • {{ selectedEmployeeDetails.department }}
            </p>
            <p class="text-xs text-slate-400 mt-1">{{ selectedEmployeeDetails.email }}</p>
          </div>
          <Badge
            :variant="selectedEmployeeDetails.status === 'active' ? 'success' : 'destructive'"
            size="md"
          >
            {{ selectedEmployeeDetails.status === 'active' ? 'В штате' : 'Уволен' }}
          </Badge>
        </div>

        <!-- Блок категории и политики софта -->
        <div class="bg-blue-50/60 p-3.5 rounded-xl border border-blue-200/80 text-xs space-y-1.5">
          <div class="flex items-center justify-between">
            <span class="font-bold text-blue-950 flex items-center gap-1.5">
              <ShieldCheck class="w-4 h-4 text-blue-600" />
              Категория и политика ПО: {{ selectedEmployeeDetails.user_category || 'Не назначена' }}
            </span>
            <span v-if="selectedEmployeeDetails.user_category" class="text-[10px] text-blue-700 font-medium">
              Аудит комплаенса активен
            </span>
          </div>
          <div v-if="selectedEmployeeDetails.user_category" class="text-slate-700 text-[11px]">
            <strong>Разрешённый перечень софта:</strong>
            <span class="text-slate-600 ml-1 font-mono text-[10px]">
              {{ categories.find(c => c.name.toLowerCase() === selectedEmployeeDetails?.user_category?.toLowerCase())?.allowed_software_list || 'Не задан' }}
            </span>
          </div>
          <div v-else class="text-slate-500 italic text-[11px]">
            Категория сотрудника не задана. Установка платного ПО вне разрешённых ролей может порождать комплаенс-алерты.
          </div>
        </div>

        <!-- Предупреждение об увольнении -->
        <div
          v-if="selectedEmployeeDetails.status === 'dismissed'"
          class="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-lg flex items-start gap-2"
        >
          <AlertTriangle class="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div>
            <strong>Внимание: сотрудник уволен!</strong> Закреплённые за ним компьютеры и лицензионное ПО создают риск «зомби-софта». Необходимо отозвать лицензии и переназначить рабочие станции.
          </div>
        </div>

        <!-- Список рабочих станций -->
        <div>
          <h5 class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
            Привязанные рабочие станции ({{ selectedEmployeeDetails.computers?.length || 0 }})
          </h5>

          <div v-if="selectedEmployeeDetails.computers && selectedEmployeeDetails.computers.length" class="space-y-2">
            <div
              v-for="cmp in selectedEmployeeDetails.computers"
              :key="cmp.id"
              class="p-3 bg-white rounded-lg border border-slate-200 flex items-center justify-between text-xs"
            >
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Monitor class="w-4 h-4" />
                </div>
                <div>
                  <div class="font-semibold text-slate-900">{{ cmp.hostname }}</div>
                  <div class="text-[11px] text-slate-400 font-mono">
                    SN: {{ cmp.serial_number }} • IP: {{ cmp.ip_address }} • {{ cmp.os_name }}
                  </div>
                </div>
              </div>

              <div class="flex items-center gap-2">
                <span :class="cmp.is_online ? 'text-emerald-600' : 'text-slate-400'" class="font-medium text-[11px] flex items-center gap-1">
                  <span :class="cmp.is_online ? 'bg-emerald-500' : 'bg-slate-300'" class="w-2 h-2 rounded-full"></span>
                  {{ cmp.is_online ? 'В сети' : 'Офлайн' }}
                </span>
              </div>
            </div>
          </div>
          <div v-else class="text-xs text-slate-400 italic py-3 text-center bg-slate-50 rounded-lg">
            У данного сотрудника пока нет привязанных ПК.
          </div>
        </div>
      </div>
      <template #footer>
        <Button variant="outline" size="sm" @click="isViewModalOpen = false">Закрыть</Button>
      </template>
    </Modal>

    <!-- Модальное окно управления категориями персонала и политиками ПО -->
    <Modal
      v-model="isCategoriesModalOpen"
      title="Категории персонала и политики разрешённого ПО"
      subtitle="Настройка списков разрешённого софта для аудита комплаенса ролей сотрудников"
      maxWidth="4xl"
    >
      <div class="space-y-5">
        <!-- Форма добавления / редактирования категории -->
        <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
          <h4 class="font-bold text-slate-900 text-xs uppercase tracking-wider flex items-center gap-1.5">
            <ShieldCheck class="w-4 h-4 text-blue-600" />
            {{ editingCategory ? `Редактирование: ${editingCategory.name}` : 'Добавить новую категорию' }}
          </h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Input
              v-model="categoryForm.name"
              label="Наименование категории"
              placeholder="Разработка и ИТ"
              required
            />
            <Input
              v-model="categoryForm.description"
              label="Описание"
              placeholder="Инженеры, разработчики, DevOps"
            />
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">
              Разрешённые программы (через запятую)
            </label>
            <textarea
              v-model="categoryForm.allowed_software_list"
              rows="2"
              class="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
              placeholder="Visual Studio, VS Code, Git, Docker, Python, Node.js"
            ></textarea>
            <p class="text-[10px] text-slate-500 mt-0.5">
              Подстроки названий ПО. При обнаружении платного софта вне этого списка система SAM создаёт комплаенс-алерт.
            </p>
          </div>
          <div class="flex justify-end gap-2 pt-1">
            <Button v-if="editingCategory" variant="outline" size="sm" type="button" @click="cancelEditCategory">
              Отмена
            </Button>
            <Button variant="primary" size="sm" type="button" @click="saveCategory">
              <Check class="w-3.5 h-3.5 mr-1" />
              {{ editingCategory ? 'Сохранить изменения' : 'Создать категорию' }}
            </Button>
          </div>
        </div>

        <!-- Список существующих категорий -->
        <div class="overflow-x-auto border border-slate-200 rounded-lg">
          <table class="w-full text-left text-xs border-collapse">
            <thead>
              <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold text-[11px]">
                <th class="py-2.5 px-3">Категория</th>
                <th class="py-2.5 px-3">Описание</th>
                <th class="py-2.5 px-3">Разрешённое ПО</th>
                <th class="py-2.5 px-3 text-center">Сотрудников</th>
                <th class="py-2.5 px-3 text-right">Действия</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="cat in categories" :key="cat.id" class="hover:bg-slate-50">
                <td class="py-2.5 px-3 font-semibold text-slate-900 whitespace-nowrap">
                  {{ cat.name }}
                </td>
                <td class="py-2.5 px-3 text-slate-600">
                  {{ cat.description || '—' }}
                </td>
                <td class="py-2.5 px-3 font-mono text-slate-600 max-w-xs truncate" :title="cat.allowed_software_list">
                  {{ cat.allowed_software_list || '—' }}
                </td>
                <td class="py-2.5 px-3 text-center font-bold text-slate-700">
                  {{ cat.employees_count || 0 }}
                </td>
                <td class="py-2.5 px-3 text-right">
                  <div class="flex items-center justify-end gap-1">
                    <button
                      type="button"
                      title="Редактировать категорию"
                      class="p-1 hover:bg-slate-100 text-slate-600 rounded transition cursor-pointer"
                      @click="startEditCategory(cat)"
                    >
                      <Edit class="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      title="Удалить категорию"
                      class="p-1 hover:bg-red-50 text-red-600 rounded transition cursor-pointer"
                      @click="deleteCategory(cat.id)"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <template #footer>
        <Button variant="outline" size="sm" @click="isCategoriesModalOpen = false">Закрыть</Button>
      </template>
    </Modal>
  </div>
</template>
