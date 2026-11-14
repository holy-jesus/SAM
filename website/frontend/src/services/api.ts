import axios, { AxiosError } from 'axios';
import {
  User,
  Employee,
  Computer,
  SoftwareCategory,
  SoftwareClassifier,
  RuSoftwareRegistryItem,
  SoftwareCatalogItem,
  License,
  InstalledSoftware,
  ComplianceAlert,
  ComplianceBalanceItem,
  DashboardSummary,
  ImportHistoryItem,
  SmartMatchResult,
  EulaAnalysisResult,
  AIChatMessage,
} from '@/types';
import * as mock from './mockData';

// Экземпляр Axios с автоматическим добавлением Bearer-токена
export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 5000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('sam_auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Локальное состояние для автономного режима (fallback при отсутствии бэкенда)
let isInitializedState = true;
let employeesState: Employee[] = [...mock.mockEmployees];
let computersState: Computer[] = [...mock.mockComputers];
let softwareCatalogState: SoftwareCatalogItem[] = [...mock.mockSoftwareCatalog];
let licensesState: License[] = [...mock.mockLicenses];
let categoriesState: SoftwareCategory[] = [...mock.mockCategories];
let installedSoftwareState: InstalledSoftware[] = [...mock.mockInstalledSoftware];
let complianceAlertsState: ComplianceAlert[] = [...mock.mockComplianceAlerts];
let importHistoryState: ImportHistoryItem[] = [...mock.mockImportHistory];

// Вспомогательная задержка для плавности интерфейса в демо-режиме
const delay = (ms = 150) => new Promise((resolve) => setTimeout(resolve, ms));

export const api = {
  // === Настройка и авторизация ===
  async getSetupStatus(): Promise<{ is_initialized: boolean }> {
    try {
      const res = await apiClient.get('/setup/status');
      return res.data;
    } catch {
      await delay();
      return { is_initialized: isInitializedState };
    }
  },

  async initAdmin(data: { username: string; password: string; full_name?: string }): Promise<{ success: boolean; token: string }> {
    try {
      const res = await apiClient.post('/setup/init-admin', data);
      return res.data;
    } catch {
      await delay();
      isInitializedState = true;
      const fakeToken = 'mock-jwt-token-admin-' + Date.now();
      localStorage.setItem('sam_auth_token', fakeToken);
      localStorage.setItem('sam_user_role', 'admin');
      return { success: true, token: fakeToken };
    }
  },

  async login(data: { username: string; password: string }): Promise<{ access_token: string; token_type: string }> {
    try {
      const res = await apiClient.post('/auth/login', data);
      return res.data;
    } catch {
      await delay();
      const fakeToken = 'mock-jwt-token-' + Date.now();
      localStorage.setItem('sam_auth_token', fakeToken);
      localStorage.setItem('sam_user_role', 'admin');
      return { access_token: fakeToken, token_type: 'bearer' };
    }
  },

  async getMe(): Promise<User> {
    try {
      const res = await apiClient.get('/auth/me');
      return res.data;
    } catch {
      await delay();
      return mock.mockUsers[0];
    }
  },

  // === Сводный дашборд ===
  async getDashboardSummary(): Promise<DashboardSummary> {
    try {
      const res = await apiClient.get('/dashboard/summary');
      return res.data;
    } catch {
      await delay();
      const online = computersState.filter((c) => c.is_online).length;
      return {
        ...mock.mockDashboardSummary,
        total_computers: computersState.length,
        online_computers: online,
        offline_computers: computersState.length - online,
        total_employees: employeesState.length,
        total_installed_software_count: installedSoftwareState.length,
        active_compliance_issues_count: complianceAlertsState.filter((a) => a.status === 'active').length,
      };
    }
  },

  // === Комплаенс-контроль ===
  async getComplianceBalance(): Promise<ComplianceBalanceItem[]> {
    try {
      const res = await apiClient.get('/compliance/balance');
      return res.data;
    } catch {
      await delay();
      return mock.mockComplianceBalance;
    }
  },

  async getComplianceAlerts(severity?: string): Promise<ComplianceAlert[]> {
    try {
      const res = await apiClient.get('/compliance/alerts', { params: { severity } });
      return res.data;
    } catch {
      await delay();
      if (!severity || severity === 'all') return complianceAlertsState;
      return complianceAlertsState.filter((a) => a.severity === severity);
    }
  },

  async recalculateCompliance(): Promise<{ success: boolean; recalculated_count: number }> {
    try {
      const res = await apiClient.post('/compliance/recalculate');
      return res.data;
    } catch {
      await delay(400);
      return { success: true, recalculated_count: complianceAlertsState.length };
    }
  },

  // === Сотрудники ===
  async getEmployees(params?: { search?: string; department?: string; status?: string }): Promise<Employee[]> {
    try {
      const res = await apiClient.get('/employees', { params });
      return res.data;
    } catch {
      await delay();
      let list = [...employeesState];
      if (params?.search) {
        const q = params.search.toLowerCase();
        list = list.filter((e) => e.full_name.toLowerCase().includes(q) || e.email?.toLowerCase().includes(q) || e.department?.toLowerCase().includes(q));
      }
      if (params?.status && params.status !== 'all') {
        list = list.filter((e) => e.status === params.status);
      }
      if (params?.department && params.department !== 'all') {
        list = list.filter((e) => e.department === params.department);
      }
      return list;
    }
  },

  async getEmployee(id: string): Promise<Employee & { computers: Computer[] }> {
    try {
      const res = await apiClient.get(`/employees/${id}`);
      return res.data;
    } catch {
      await delay();
      const emp = employeesState.find((e) => e.id === id) || employeesState[0];
      const comps = computersState.filter((c) => c.employee_id === id);
      return { ...emp, computers: comps };
    }
  },

  async createEmployee(data: Partial<Employee>): Promise<Employee> {
    try {
      const res = await apiClient.post('/employees', data);
      return res.data;
    } catch {
      await delay();
      const newEmp: Employee = {
        id: 'emp-' + Date.now().toString(36),
        full_name: data.full_name || 'Новый Сотрудник',
        email: data.email || '',
        department: data.department || 'Общий отдел',
        position: data.position || 'Специалист',
        status: data.status || 'active',
        computers_count: 0,
        created_at: new Date().toISOString(),
      };
      employeesState.unshift(newEmp);
      return newEmp;
    }
  },

  async updateEmployee(id: string, data: Partial<Employee>): Promise<Employee> {
    try {
      const res = await apiClient.put(`/employees/${id}`, data);
      return res.data;
    } catch {
      await delay();
      const idx = employeesState.findIndex((e) => e.id === id);
      if (idx !== -1) {
        employeesState[idx] = { ...employeesState[idx], ...data, updated_at: new Date().toISOString() };
        return employeesState[idx];
      }
      throw new Error('Employee not found');
    }
  },

  async deleteEmployee(id: string): Promise<{ success: boolean }> {
    try {
      const res = await apiClient.delete(`/employees/${id}`);
      return res.data;
    } catch {
      await delay();
      employeesState = employeesState.filter((e) => e.id !== id);
      return { success: true };
    }
  },

  // === Компьютеры и хосты ===
  async getComputers(params?: { search?: string; is_online?: boolean }): Promise<Computer[]> {
    try {
      const res = await apiClient.get('/computers', { params });
      return res.data;
    } catch {
      await delay();
      let list = [...computersState];
      if (params?.search) {
        const q = params.search.toLowerCase();
        list = list.filter((c) => c.hostname.toLowerCase().includes(q) || c.serial_number.toLowerCase().includes(q) || c.ip_address?.toLowerCase().includes(q));
      }
      if (params?.is_online !== undefined) {
        list = list.filter((c) => c.is_online === params.is_online);
      }
      return list;
    }
  },

  async getComputer(id: string): Promise<Computer> {
    try {
      const res = await apiClient.get(`/computers/${id}`);
      return res.data;
    } catch {
      await delay();
      const comp = computersState.find((c) => c.id === id) || computersState[0];
      const soft = installedSoftwareState.filter((s) => s.computer_id === id);
      return { ...comp, installed_software: soft };
    }
  },

  async createComputer(data: Partial<Computer>): Promise<Computer> {
    try {
      const res = await apiClient.post('/computers', data);
      return res.data;
    } catch {
      await delay();
      const newComp: Computer = {
        id: 'cmp-' + Date.now().toString(36),
        serial_number: data.serial_number || 'SN-' + Math.floor(1000 + Math.random() * 9000),
        hostname: data.hostname || 'NEW-HOST',
        ip_address: data.ip_address || '192.168.1.100',
        mac_address: data.mac_address || '00:11:22:33:44:55',
        os_name: data.os_name || 'Windows 11 Pro',
        os_version: data.os_version || '23H2',
        cpu_info: data.cpu_info || 'Intel Core i5',
        ram_mb: data.ram_mb || 16384,
        is_online: true,
        last_seen_at: new Date().toISOString(),
        employee_id: data.employee_id || null,
        employee: employeesState.find((e) => e.id === data.employee_id),
        installed_count: 0,
        created_at: new Date().toISOString(),
      };
      computersState.unshift(newComp);
      return newComp;
    }
  },

  async updateComputer(id: string, data: Partial<Computer>): Promise<Computer> {
    try {
      const res = await apiClient.put(`/computers/${id}`, data);
      return res.data;
    } catch {
      await delay();
      const idx = computersState.findIndex((c) => c.id === id);
      if (idx !== -1) {
        const emp = employeesState.find((e) => e.id === data.employee_id);
        computersState[idx] = { ...computersState[idx], ...data, employee: emp, updated_at: new Date().toISOString() };
        return computersState[idx];
      }
      throw new Error('Computer not found');
    }
  },

  async deleteComputer(id: string): Promise<{ success: boolean }> {
    try {
      const res = await apiClient.delete(`/computers/${id}`);
      return res.data;
    } catch {
      await delay();
      computersState = computersState.filter((c) => c.id !== id);
      return { success: true };
    }
  },

  async addSoftwareToComputer(computerId: string, softwareData: Partial<InstalledSoftware>): Promise<InstalledSoftware> {
    try {
      const res = await apiClient.post(`/computers/${computerId}/software`, softwareData);
      return res.data;
    } catch {
      await delay();
      const comp = computersState.find((c) => c.id === computerId);
      const cat = softwareCatalogState.find((s) => s.id === softwareData.catalog_software_id);
      const newInst: InstalledSoftware = {
        id: 'inst-' + Date.now().toString(36),
        computer_id: computerId,
        computer_hostname: comp?.hostname,
        computer_serial: comp?.serial_number,
        raw_display_name: softwareData.raw_display_name || cat?.name || 'Manual Install',
        raw_publisher: softwareData.raw_publisher || cat?.vendor,
        raw_version: softwareData.raw_version || '1.0',
        install_path: softwareData.install_path || 'C:\\Program Files\\Manual',
        last_launched_at: new Date().toISOString(),
        source: 'manual',
        catalog_software_id: cat?.id || null,
        catalog_software_name: cat?.name,
        category_id: cat?.category_id || 1,
        category_name: 'Актуальный',
        match_confidence: 1.0,
        is_verified_by_admin: true,
        is_deleted: false,
        first_seen_at: new Date().toISOString(),
      };
      installedSoftwareState.unshift(newInst);
      if (comp) comp.installed_count = (comp.installed_count || 0) + 1;
      return newInst;
    }
  },

  async removeSoftwareFromComputer(computerId: string, installedSoftwareId: string): Promise<{ success: boolean }> {
    try {
      const res = await apiClient.delete(`/computers/${computerId}/software/${installedSoftwareId}`);
      return res.data;
    } catch {
      await delay();
      installedSoftwareState = installedSoftwareState.filter((s) => s.id !== installedSoftwareId);
      const comp = computersState.find((c) => c.id === computerId);
      if (comp && comp.installed_count && comp.installed_count > 0) comp.installed_count -= 1;
      return { success: true };
    }
  },

  // === Установленное ПО ===
  async getInstalledSoftware(params?: { search?: string; category_id?: number }): Promise<InstalledSoftware[]> {
    try {
      const res = await apiClient.get('/installed-software', { params });
      return res.data;
    } catch {
      await delay();
      let list = [...installedSoftwareState];
      if (params?.search) {
        const q = params.search.toLowerCase();
        list = list.filter((s) => s.raw_display_name.toLowerCase().includes(q) || s.computer_hostname?.toLowerCase().includes(q) || s.computer_serial?.toLowerCase().includes(q));
      }
      if (params?.category_id) {
        list = list.filter((s) => s.category_id === params.category_id);
      }
      return list;
    }
  },

  async updateSoftwareCategory(installedId: string, categoryId: number): Promise<InstalledSoftware> {
    try {
      const res = await apiClient.put(`/installed-software/${installedId}/category`, { category_id: categoryId });
      return res.data;
    } catch {
      await delay();
      const idx = installedSoftwareState.findIndex((s) => s.id === installedId);
      if (idx !== -1) {
        const cat = categoriesState.find((c) => c.id === categoryId);
        installedSoftwareState[idx].category_id = categoryId;
        installedSoftwareState[idx].category_name = cat?.name;
        installedSoftwareState[idx].is_problematic = cat?.is_problematic;
        return installedSoftwareState[idx];
      }
      throw new Error('Installed software not found');
    }
  },

  // === Каталог разрешённого ПО (Белый список) ===
  async getCatalog(): Promise<SoftwareCatalogItem[]> {
    try {
      const res = await apiClient.get('/catalog');
      return res.data;
    } catch {
      await delay();
      return softwareCatalogState;
    }
  },

  async createCatalogItem(data: Partial<SoftwareCatalogItem>): Promise<SoftwareCatalogItem> {
    try {
      const res = await apiClient.post('/catalog', data);
      return res.data;
    } catch {
      await delay();
      const newItem: SoftwareCatalogItem = {
        id: 'cat-' + Date.now().toString(36),
        name: data.name || 'Новое ПО',
        vendor: data.vendor || 'Корпоративный вендор',
        description: data.description || '',
        classifier_id: data.classifier_id || null,
        ru_registry_id: data.ru_registry_id || null,
        category_id: data.category_id || 1,
        license_type: data.license_type || 'Commercial',
        max_installations: data.max_installations || 0,
        active_installations_count: 0,
        responsible_person: data.responsible_person || 'Администратор SAM',
        approval_status: data.approval_status || 'approved',
        created_at: new Date().toISOString(),
      };
      softwareCatalogState.unshift(newItem);
      return newItem;
    }
  },

  async updateCatalogItem(id: string, data: Partial<SoftwareCatalogItem>): Promise<SoftwareCatalogItem> {
    try {
      const res = await apiClient.put(`/catalog/${id}`, data);
      return res.data;
    } catch {
      await delay();
      const idx = softwareCatalogState.findIndex((s) => s.id === id);
      if (idx !== -1) {
        softwareCatalogState[idx] = { ...softwareCatalogState[idx], ...data, updated_at: new Date().toISOString() };
        return softwareCatalogState[idx];
      }
      throw new Error('Catalog item not found');
    }
  },

  async deleteCatalogItem(id: string): Promise<{ success: boolean }> {
    try {
      const res = await apiClient.delete(`/catalog/${id}`);
      return res.data;
    } catch {
      await delay();
      softwareCatalogState = softwareCatalogState.filter((s) => s.id !== id);
      return { success: true };
    }
  },

  // === Лицензии ===
  async getLicenses(): Promise<License[]> {
    try {
      const res = await apiClient.get('/licenses');
      return res.data;
    } catch {
      await delay();
      return licensesState;
    }
  },

  async createLicense(data: Partial<License>): Promise<License> {
    try {
      const res = await apiClient.post('/licenses', data);
      return res.data;
    } catch {
      await delay();
      const soft = softwareCatalogState.find((s) => s.id === data.software_id);
      const newLic: License = {
        id: 'lic-' + Date.now().toString(36),
        software_id: data.software_id || softwareCatalogState[0].id,
        software_name: soft?.name,
        license_name: data.license_name || 'Лицензия на ПО',
        license_type: data.license_type || 'Платный',
        license_model: data.license_model || 'per_device',
        total_purchased: data.total_purchased || 1,
        unit_cost: data.unit_cost || 0,
        currency: data.currency || 'RUB',
        valid_from: data.valid_from,
        valid_to: data.valid_to,
        eula_text: data.eula_text || '',
        created_at: new Date().toISOString(),
      };
      licensesState.unshift(newLic);
      return newLic;
    }
  },

  async updateLicense(id: string, data: Partial<License>): Promise<License> {
    try {
      const res = await apiClient.put(`/licenses/${id}`, data);
      return res.data;
    } catch {
      await delay();
      const idx = licensesState.findIndex((l) => l.id === id);
      if (idx !== -1) {
        licensesState[idx] = { ...licensesState[idx], ...data, updated_at: new Date().toISOString() };
        return licensesState[idx];
      }
      throw new Error('License not found');
    }
  },

  async deleteLicense(id: string): Promise<{ success: boolean }> {
    try {
      const res = await apiClient.delete(`/licenses/${id}`);
      return res.data;
    } catch {
      await delay();
      licensesState = licensesState.filter((l) => l.id !== id);
      return { success: true };
    }
  },

  // === Категории ПО ===
  async getCategories(): Promise<SoftwareCategory[]> {
    try {
      const res = await apiClient.get('/categories');
      return res.data;
    } catch {
      await delay();
      return categoriesState;
    }
  },

  async createCategory(data: Partial<SoftwareCategory>): Promise<SoftwareCategory> {
    try {
      const res = await apiClient.post('/categories', data);
      return res.data;
    } catch {
      await delay();
      const newCat: SoftwareCategory = {
        id: Date.now(),
        name: data.name || 'Новая категория',
        description: data.description || '',
        is_problematic: !!data.is_problematic,
        risk_level: data.risk_level || 'none',
        color_hex: data.color_hex || '#6366f1',
      };
      categoriesState.push(newCat);
      return newCat;
    }
  },

  async updateCategory(id: number, data: Partial<SoftwareCategory>): Promise<SoftwareCategory> {
    try {
      const res = await apiClient.put(`/categories/${id}`, data);
      return res.data;
    } catch {
      await delay();
      const idx = categoriesState.findIndex((c) => c.id === id);
      if (idx !== -1) {
        categoriesState[idx] = { ...categoriesState[idx], ...data };
        return categoriesState[idx];
      }
      throw new Error('Category not found');
    }
  },

  async deleteCategory(id: number): Promise<{ success: boolean }> {
    try {
      const res = await apiClient.delete(`/categories/${id}`);
      return res.data;
    } catch {
      await delay();
      categoriesState = categoriesState.filter((c) => c.id !== id);
      return { success: true };
    }
  },

  // === Классификатор и Единый реестр отечественного ПО ===
  async getClassifiers(): Promise<SoftwareClassifier[]> {
    try {
      const res = await apiClient.get('/classifiers');
      return res.data;
    } catch {
      await delay();
      return mock.mockClassifiers;
    }
  },

  async getRegistry(params?: { search?: string; class_code?: string }): Promise<RuSoftwareRegistryItem[]> {
    try {
      const res = await apiClient.get('/registry', { params });
      return res.data;
    } catch {
      await delay();
      let list = [...mock.mockRuRegistry];
      if (params?.search) {
        const q = params.search.toLowerCase();
        list = list.filter((r) => r.name.toLowerCase().includes(q) || r.reg_number.includes(q) || r.vendor_name?.toLowerCase().includes(q));
      }
      return list;
    }
  },

  async getRegistryStatus(): Promise<{ last_updated_at: string; total_records: number }> {
    try {
      const res = await apiClient.get('/registry/status');
      return res.data;
    } catch {
      await delay();
      return {
        last_updated_at: new Date().toISOString(),
        total_records: mock.mockRuRegistry.length,
      };
    }
  },

  async syncRegistry(): Promise<{ success: boolean; message: string; updated_count: number }> {
    try {
      const res = await apiClient.post('/registry/sync');
      return res.data;
    } catch {
      await delay(800);
      return {
        success: true,
        message: 'Единый реестр отечественного ПО успешно синхронизирован с reestr.digital.gov.ru',
        updated_count: mock.mockRuRegistry.length,
      };
    }
  },

  // === Импорт дампов хостов и история загрузок ===
  async uploadDump(file: File): Promise<{
    filename: string;
    total_rows: number;
    computers_affected: number;
    software_rows_imported: number;
    matched_automatically: number;
  }> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await apiClient.post('/connector/import/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    } catch {
      await delay(600);
      const newItem: ImportHistoryItem = {
        id: 'imp-' + Date.now().toString(36),
        filename: file.name,
        total_rows: 142,
        computers_affected: 8,
        software_rows_imported: 142,
        matched_automatically: 138,
        status: 'success',
        created_at: new Date().toISOString(),
      };
      importHistoryState.unshift(newItem);
      return {
        filename: file.name,
        total_rows: newItem.total_rows,
        computers_affected: newItem.computers_affected,
        software_rows_imported: newItem.software_rows_imported,
        matched_automatically: newItem.matched_automatically,
      };
    }
  },

  async getImportHistory(): Promise<ImportHistoryItem[]> {
    try {
      const res = await apiClient.get('/connector/import/history');
      return res.data;
    } catch {
      await delay();
      return importHistoryState;
    }
  },

  // === Модули искусственного интеллекта (ИИ) ===
  async smartMatchSoftware(rawProcessName: string): Promise<SmartMatchResult> {
    try {
      const res = await apiClient.post('/ai/match-software', { raw_process_name: rawProcessName });
      return res.data;
    } catch {
      await delay(450);
      // Эвристическое сопоставление в автономном режиме
      const lower = rawProcessName.toLowerCase();
      if (lower.includes('visual') || lower.includes('studio') || lower.includes('devenv')) {
        return {
          raw_process_name: rawProcessName,
          matched_catalog_software_id: 'cat-04',
          matched_name: 'Microsoft Visual Studio 2022 Professional',
          vendor: 'Microsoft Corporation',
          confidence: 0.95,
          reasoning: 'Семантическое сопоставление имени процесса studio_visual с каталогом IDE через pgvector.',
        };
      }
      if (lower.includes('chrome')) {
        return {
          raw_process_name: rawProcessName,
          matched_catalog_software_id: 'cat-02',
          matched_name: 'Google Chrome',
          vendor: 'Google LLC',
          confidence: 0.99,
          reasoning: 'Прямое векторное совпадение с корпоративным браузером Google Chrome.',
        };
      }
      if (lower.includes('utorrent') || lower.includes('torrent')) {
        return {
          raw_process_name: rawProcessName,
          matched_catalog_software_id: 'cat-07',
          matched_name: 'BitTorrent / uTorrent Client',
          vendor: 'BitTorrent Inc.',
          confidence: 0.94,
          reasoning: 'Классификатор определил запрещённый P2P-клиент торрент.',
        };
      }
      return {
        raw_process_name: rawProcessName,
        matched_catalog_software_id: 'cat-01',
        matched_name: 'Microsoft Office 2021 Professional Plus',
        vendor: 'Microsoft Corporation',
        confidence: 0.82,
        reasoning: 'Эвристическое соответствие с офисным пакетом ПО.',
      };
    }
  },

  async batchNormalize(): Promise<{ normalized_count: number; matched_count: number }> {
    try {
      const res = await apiClient.post('/ai/batch-normalize');
      return res.data;
    } catch {
      await delay(900);
      return { normalized_count: 24, matched_count: 22 };
    }
  },

  async analyzeEula(eulaText: string, licenseId?: string): Promise<EulaAnalysisResult> {
    try {
      const res = await apiClient.post('/ai/analyze-eula', { eula_text: eulaText, license_id: licenseId });
      return res.data;
    } catch {
      await delay(700);
      const lower = eulaText.toLowerCase();
      const hasPersonalOnly = lower.includes('personal') || lower.includes('non-commercial') || lower.includes('личн') || lower.includes('некоммерческ');
      const hasAutoRenew = lower.includes('auto-renew') || lower.includes('subscription') || lower.includes('recurring') || lower.includes('подписк');

      return {
        commercial_use_allowed: !hasPersonalOnly,
        risk_level: hasPersonalOnly ? 'critical' : hasAutoRenew ? 'medium' : 'low',
        has_auto_renewal: hasAutoRenew,
        trial_period_days: lower.includes('trial') ? 30 : undefined,
        key_restrictions: [
          hasPersonalOnly
            ? 'Лицензия ограничена исключительно персональным некоммерческим использованием (Personal Use Only).'
            : 'Разрешено коммерческое использование юридическим лицом в рамках штатного расписания.',
          hasAutoRenew
            ? 'Обнаружен пункт автоматического продления и регулярного списания средств при отсутствии заблаговременного уведомления.'
            : 'Фиксированный срок действия без скрытых автоплатежей.',
          'Запрещена декомпиляция, реверс-инжиниринг и сублицензирование третьим лицам.',
        ],
        summary_ru: hasPersonalOnly
          ? 'ВНИМАНИЕ! Соглашение запрещает использование софта в коммерческих целях предприятия. Эксплуатация сотрудниками компании несёт высокий штрафной риск при проверке правообладателя.'
          : 'Лицензионное соглашение соответствует стандартным корпоративным требованиям. Рисков нарушения авторских прав не выявлено.',
        analyzed_at: new Date().toISOString(),
      };
    }
  },

  async askAIChat(query: string): Promise<AIChatMessage> {
    try {
      const res = await apiClient.post('/ai/chat', { query });
      return {
        id: 'msg-' + Date.now(),
        sender: 'assistant',
        text: res.data.answer,
        sql_executed: res.data.sql_executed,
        data: res.data.data,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
    } catch {
      await delay(500);
      const q = query.toLowerCase();

      if (q.includes('нелицензион') || q.includes('дефицит') || q.includes('штраф') || q.includes('перерасход')) {
        return {
          id: 'msg-' + Date.now(),
          sender: 'assistant',
          text: `Анализ выявил дефицит по 2 продуктам:
1. **Microsoft Office 2021**: куплено 100, установлено на 120 ПК (превышение на 20 шт.). Штрафной риск: **500 000 руб.**
2. **Oracle Java 8u201**: куплено 10, установлено на 18 ПК (превышение на 8 шт.). Риск: **144 000 руб.**
Общий финансовый риск дефицита лицензий составляет **644 000 руб.**`,
          sql_executed: `SELECT s.name, l.total_purchased, COUNT(i.id) AS installed, 
       (COUNT(i.id) - l.total_purchased) * l.unit_cost AS penalty_rub
FROM software_catalog s
JOIN licenses l ON l.software_id = s.id
JOIN installed_software i ON i.catalog_software_id = s.id
GROUP BY s.id, l.id
HAVING COUNT(i.id) > l.total_purchased;`,
          data: [
            { software: 'Microsoft Office 2021', purchased: 100, installed: 120, deficit: 20, penalty_rub: 500000 },
            { software: 'Oracle Java 8 Update 201', purchased: 10, installed: 18, deficit: 8, penalty_rub: 144000 },
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
      }

      if (q.includes('зомби') || q.includes('простаива') || q.includes('уволен')) {
        return {
          id: 'msg-' + Date.now(),
          sender: 'assistant',
          text: `Обнаружен 1 ПК уволенного сотрудника Соколова П.В. (DISMISSED-PC-SOKOLOV, серийный B1RG0S2). На нём заблокированы 2 лицензии общей стоимостью **43 000 руб.**, которые не использовались более 90 дней. Рекомендуется высвободить лицензии в пул свободных.`,
          sql_executed: `SELECT c.hostname, e.full_name, e.status, s.name, i.last_launched_at
FROM computers c
JOIN employees e ON c.employee_id = e.id
JOIN installed_software i ON i.computer_id = c.id
JOIN software_catalog s ON i.catalog_software_id = s.id
WHERE e.status = 'dismissed' OR i.last_launched_at < NOW() - INTERVAL '90 days';`,
          data: [
            { host: 'DISMISSED-PC-SOKOLOV', employee: 'Соколов П.В.', status: 'уволен', software: 'MS Office 2021', inactive_days: 96 },
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
      }

      if (q.includes('запрещ') || q.includes('торрент') || q.includes('shadow')) {
        return {
          id: 'msg-' + Date.now(),
          sender: 'assistant',
          text: `На хосте **WORKSTATION-SHADOW** (IP 192.168.10.105, сотрудник Михайлов А.И.) зафиксирована активность процесса **uTorrent Web 1.2.8**, отнесённого к категории «Запрещенный к использованию». Рекомендуется немедленно изолировать хост и удалить ПО.`,
          sql_executed: `SELECT c.hostname, c.ip_address, e.full_name, i.raw_display_name, cat.name as category
FROM installed_software i
JOIN computers c ON i.computer_id = c.id
LEFT JOIN employees e ON c.employee_id = e.id
JOIN software_categories cat ON i.category_id = cat.id
WHERE cat.is_problematic = true AND cat.risk_level = 'critical';`,
          data: [
            { host: 'WORKSTATION-SHADOW', ip: '192.168.10.105', user: 'Михайлов А.И.', process: 'uTorrent Web 1.2.8', risk: 'КРИТИЧЕСКИЙ' },
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
      }

      return {
        id: 'msg-' + Date.now(),
        sender: 'assistant',
        text: `В системе SAM числится 156 рабочих станций (128 онлайн), 142 сотрудника и 1 845 инсталляций ПО. Общий баланс комплаенса составляет 94%, выявлено 5 критических алертов на общую сумму потенциальных рисков 969 000 руб. Вы можете уточнить: «У кого стоит нелицензионный софт?», «Сколько лицензий простаивает?» или «Покажи ПК с запрещённым софтом».`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
    }
  },
};
