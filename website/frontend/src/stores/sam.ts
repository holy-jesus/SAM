import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  DashboardSummary,
  ComplianceAlert,
  ComplianceBalanceItem,
  Computer,
  Employee,
  SoftwareCatalogItem,
  InstalledSoftware,
  SoftwareCategory,
  RegistryStatus,
} from '@/types';
import { api } from '@/services/api';

export const useSamStore = defineStore('sam', () => {
  // Основные реактивные сущности системы
  const summary = ref<DashboardSummary | null>(null);
  const alerts = ref<ComplianceAlert[]>([]);
  const balance = ref<ComplianceBalanceItem[]>([]);
  const computers = ref<Computer[]>([]);
  const employees = ref<Employee[]>([]);
  const catalog = ref<SoftwareCatalogItem[]>([]);
  const categories = ref<SoftwareCategory[]>([]);
  const installedSoftware = ref<InstalledSoftware[]>([]);
  const registryStatus = ref<RegistryStatus | null>(null);
  const loading = ref(false);

  // Управление глобальными модальными окнами и диалогами
  const smartMatchModalOpen = ref(false);
  const smartMatchProcessTarget = ref<string>('');
  const eulaModalOpen = ref(false);
  const eulaModalLicenseId = ref<string | undefined>(undefined);
  const aiChatWidgetOpen = ref(false);

  // Загрузка всех данных сводного дашборда из API
  async function loadDashboard() {
    loading.value = true;
    try {
      const [sum, al, bal, comps, soft, reg] = await Promise.all([
        api.getDashboardSummary(),
        api.getComplianceAlerts(),
        api.getComplianceBalance(),
        api.getComputers(),
        api.getInstalledSoftware(),
        api.getRegistryStatus(),
      ]);
      summary.value = sum;
      alerts.value = al;
      balance.value = bal;
      computers.value = comps;
      installedSoftware.value = soft;
      registryStatus.value = reg;
    } finally {
      loading.value = false;
    }
  }

  // Загрузка категорий софта
  async function loadCategories() {
    categories.value = await api.getCategories();
  }

  // Запуск модального окна умного мэтчинга
  function triggerSmartMatch(processName: string) {
    smartMatchProcessTarget.value = processName;
    smartMatchModalOpen.value = true;
  }

  // Запуск модального окна AI-анализа EULA
  function triggerEulaAnalysis(licenseId?: string) {
    eulaModalLicenseId.value = licenseId;
    eulaModalOpen.value = true;
  }

  // Переключение видимости плавающего чата ИТ-директора
  function toggleAIChat() {
    aiChatWidgetOpen.value = !aiChatWidgetOpen.value;
  }

  return {
    summary,
    alerts,
    balance,
    computers,
    employees,
    catalog,
    categories,
    installedSoftware,
    registryStatus,
    loading,
    smartMatchModalOpen,
    smartMatchProcessTarget,
    eulaModalOpen,
    eulaModalLicenseId,
    aiChatWidgetOpen,
    loadDashboard,
    loadCategories,
    triggerSmartMatch,
    triggerEulaAnalysis,
    toggleAIChat,
  };
});
