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
} from '@/types';
import { api } from '@/services/api';

export const useSamStore = defineStore('sam', () => {
  const summary = ref<DashboardSummary | null>(null);
  const alerts = ref<ComplianceAlert[]>([]);
  const balance = ref<ComplianceBalanceItem[]>([]);
  const computers = ref<Computer[]>([]);
  const employees = ref<Employee[]>([]);
  const catalog = ref<SoftwareCatalogItem[]>([]);
  const categories = ref<SoftwareCategory[]>([]);
  const loading = ref(false);

  // Global modals control
  const smartMatchModalOpen = ref(false);
  const smartMatchProcessTarget = ref<string>('');
  const eulaModalOpen = ref(false);
  const eulaModalLicenseId = ref<string | undefined>(undefined);
  const aiChatWidgetOpen = ref(false);

  async function loadDashboard() {
    loading.value = true;
    try {
      const [sum, al, bal] = await Promise.all([
        api.getDashboardSummary(),
        api.getComplianceAlerts(),
        api.getComplianceBalance(),
      ]);
      summary.value = sum;
      alerts.value = al;
      balance.value = bal;
    } finally {
      loading.value = false;
    }
  }

  async function loadCategories() {
    categories.value = await api.getCategories();
  }

  function triggerSmartMatch(processName: string) {
    smartMatchProcessTarget.value = processName;
    smartMatchModalOpen.value = true;
  }

  function triggerEulaAnalysis(licenseId?: string) {
    eulaModalLicenseId.value = licenseId;
    eulaModalOpen.value = true;
  }

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
