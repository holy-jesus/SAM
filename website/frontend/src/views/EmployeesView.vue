<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { api } from '@/services/api';
import { Employee, Computer, EmployeeStatus } from '@/types';
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
} from 'lucide-vue-next';

const employees = ref<Employee[]>([]);
const loading = ref(false);
const searchQuery = ref('');
const statusFilter = ref('all');

// Модальные окна
const isCreateModalOpen = ref(false);
const isViewModalOpen = ref(false);
const editingEmployee = ref<Partial<Employee> | null>(null);
const selectedEmployeeDetails = ref<(Employee & { computers: Computer[] }) | null>(null);

const form = ref({
  full_name: '',
  email: '',
  department: '',
  position: '',
  status: 'active' as EmployeeStatus,
});

onMounted(() => {
  loadEmployees();
});

async function loadEmployees() {
  loading.value = true;
  try {
    employees.value = await api.getEmployees();
  } finally {
    loading.value = false;
  }
}

const filteredEmployees = computed(() => {
  return employees.value.filter((emp) => {
    const matchSearch =
      !searchQuery.value ||
      emp.full_name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      emp.email?.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      emp.department?.toLowerCase().includes(searchQuery.value.toLowerCase());
    const matchStatus = statusFilter.value === 'all' || emp.status === statusFilter.value;
    return matchSearch && matchStatus;
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
  await loadEmployees();
}

async function deleteEmployee(id: string) {
  if (confirm('Вы действительно хотите удалить данного сотрудника?')) {
    await api.deleteEmployee(id);
    await loadEmployees();
  }
}

async function viewEmployee(emp: Employee) {
  const details = await api.getEmployee(emp.id);
  selectedEmployeeDetails.value = details;
  isViewModalOpen.value = true;
}
</script>

<template>
  <div class="space-y-6">
    <!-- Заголовок страницы -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Сотрудники компании</h1>
        <p class="text-xs text-slate-500 mt-1">
          Учёт персонала, закрепление рабочих станций и контроль прав на использование софта
        </p>
      </div>

      <Button variant="primary" size="sm" @click="openCreate">
        <Plus class="w-4 h-4 mr-1.5" />
        Добавить сотрудника
      </Button>
    </div>

    <!-- Панель фильтров -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
      <div class="w-full sm:w-80">
        <Input
          v-model="searchQuery"
          placeholder="Поиск по ФИО, email, отделу..."
        />
      </div>

      <div class="flex items-center gap-2">
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

    <!-- Модальное окно создания / редактирования -->
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
  </div>
</template>
