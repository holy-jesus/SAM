export type UserRole = 'admin' | 'operator' | 'viewer';

export interface User {
  id: string;
  username: string;
  full_name?: string;
  role: UserRole;
  created_at?: string;
}

export type EmployeeStatus = 'active' | 'dismissed' | 'on_leave';

export interface Employee {
  id: string;
  full_name: string;
  email?: string;
  department?: string;
  position?: string;
  status: EmployeeStatus;
  user_category?: string;
  created_at?: string;
  updated_at?: string;
  computers_count?: number;
  computers?: Computer[];
}

export interface EmployeeCategory {
  id: number;
  name: string;
  description?: string;
  allowed_software_list?: string;
  employees_count?: number;
}

export interface ComputerEnrollmentStats {
  total: number;
  pending: number;
  approved: number;
  blocked: number;
}

export interface Computer {
  id: string;
  serial_number: string;
  hostname: string;
  ip_address?: string;
  mac_address?: string;
  os_name?: string;
  os_version?: string;
  cpu_info?: string;
  ram_mb?: number;
  disk_info?: any;
  is_online: boolean;
  enrollment_status?: 'pending' | 'approved' | 'blocked';
  last_seen_at?: string;
  employee_id?: string | null;
  employee?: Employee;
  installed_software?: InstalledSoftware[];
  installed_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface SoftwareCategory {
  id: number;
  name: string;
  description?: string;
  is_problematic: boolean;
  risk_level: 'none' | 'low' | 'medium' | 'critical';
  color_hex?: string;
}

export interface SoftwareClassifier {
  id: number;
  code: string;
  section_code: string;
  section_name: string;
  class_name: string;
}

export interface RuSoftwareRegistryItem {
  id: number;
  reg_number: string;
  name: string;
  alternative_names?: string;
  software_class?: string;
  vendor_name?: string;
  vendor_inn?: string;
  documentation_url?: string;
  is_ai?: boolean;
  excluded_at?: string | null;
  updated_at?: string;
}

export interface RegistryStatus {
  last_updated_at: string;
  total_records: number;
}

export type LicenseType = 'Commercial' | 'Open Source' | 'Freeware' | 'Trial' | 'Платный' | 'Бесплатный' | 'Условно бесплатный';

export interface SoftwareCatalogItem {
  id: string;
  name: string;
  vendor?: string;
  description?: string;
  classifier_id?: number | null;
  classifier?: SoftwareClassifier;
  ru_registry_id?: number | null;
  ru_registry?: RuSoftwareRegistryItem;
  category_id?: number | null;
  category?: SoftwareCategory;
  license_type: LicenseType;
  max_installations: number; // 0 = без ограничений
  active_installations_count?: number;
  responsible_person?: string;
  approval_status?: 'approved' | 'review' | 'rejected';
  has_substitution?: boolean | null;
  substitutions_count?: number;
  is_domestic?: boolean;
  substitution_status?: 'domestic' | 'has_substitutes' | 'no_substitutes' | 'pending' | 'error';
  created_at?: string;
  updated_at?: string;
}

export type LicenseModel = 'per_device' | 'per_user' | 'site';

export interface License {
  id: string;
  software_id: string;
  software_name?: string;
  license_name: string;
  license_type: string;
  license_model: LicenseModel;
  total_purchased: number;
  unit_cost: number;
  currency: string;
  valid_from?: string;
  valid_to?: string;
  eula_text?: string;
  eula_analysis?: EulaAnalysisResult;
  created_at?: string;
  updated_at?: string;
}

export interface InstalledSoftware {
  id: string;
  computer_id: string;
  computer_hostname?: string;
  computer_serial?: string;
  raw_display_name: string;
  raw_publisher?: string;
  raw_version?: string;
  install_path?: string;
  binary_hash?: string;
  last_launched_at?: string;
  source: 'agent' | 'automatic' | 'manual';
  catalog_software_id?: string | null;
  catalog_software_name?: string;
  normalized_name?: string | null;
  match_source?: string | null;
  category_id?: number | null;
  category_name?: string;
  is_problematic?: boolean;
  match_confidence: number;
  is_verified_by_admin: boolean;
  is_deleted: boolean;
  has_substitution?: boolean | null;
  substitutions_count?: number;
  is_domestic?: boolean;
  first_seen_at?: string;
  last_seen_at?: string;
}

export type AlertSeverity = 'info' | 'warning' | 'critical';
export type AlertType = 'license_overuse' | 'zombie_software' | 'prohibited_software' | 'shadow_it' | 'commercial_risk';
export type AlertStatus = 'active' | 'acknowledged' | 'resolved';

export interface ComplianceAlert {
  id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  computer_id?: string | null;
  computer_hostname?: string;
  software_id?: string | null;
  software_name?: string;
  title: string;
  description: string;
  financial_risk_amount: number;
  status: AlertStatus;
  created_at: string;
  resolved_at?: string | null;
}

export interface ComplianceBalanceItem {
  software_id: string;
  software_name: string;
  vendor?: string;
  license_type: string;
  purchased_count: number;
  installed_count: number;
  balance: number; // куплено минус установлено (отрицательное число = дефицит)
  unit_cost: number;
  total_penalty_risk_rub: number;
  status: 'normal' | 'critical_overuse' | 'underutilized';
  is_prohibited?: boolean;
}

export interface DashboardSummary {
  total_computers: number;
  online_computers: number;
  offline_computers: number;
  total_employees: number;
  total_installed_software_count: number;
  active_compliance_issues_count: number;
  total_financial_risk_rub: number;
  licenses_purchased_count?: number;
  prohibited_count?: number;
  zombie_count?: number;
}

export interface ImportHistoryItem {
  id: string;
  filename: string;
  total_rows: number;
  computers_affected: number;
  software_rows_imported: number;
  matched_automatically: number;
  status: 'processing' | 'success' | 'failed';
  error_message?: string;
  created_at: string;
}

export interface SmartMatchResult {
  raw_process_name: string;
  matched_catalog_software_id?: string;
  matched_name: string;
  vendor?: string;
  matched_version?: string;
  confidence: number;
  reasoning: string;
  match_source?: string;
}

// === Модуль импортозамещения ПО (Раздел 4.7) ===
export interface ImportSubstitutionItem {
  id: string;
  foreign_software_name: string;
  russian_software_name: string;
  russian_reg_number?: string;
  source: string; // 'registry' | 'arppsoft'
  owner_name?: string;
  class_code?: string;
  class_name?: string;
  registration_date?: string;
  registry_url?: string;
  ru_registry_id?: number | null;
  catalog_software_id?: string | null;
  created_at?: string;
}

export interface SubstitutionSearchResponse {
  query: string;
  total_found: number;
  items: ImportSubstitutionItem[];
}

export interface SubstitutionSyncResponse {
  success: boolean;
  imported_count: number;
  message: string;
}

// === Модуль учёта уязвимостей безопасности БДУ ФСТЭК (Раздел 4.8) ===
export interface VulnerabilityItem {
  id: string;
  bdu_id: string;
  name: string;
  description?: string;
  vendor: string;
  software_name: string;
  software_version?: string;
  software_type?: string;
  vuln_class?: string;
  severity: string; // 'Критический' | 'Высокий' | 'Средний' | 'Низкий'
  cvss_score?: number | null;
  solution?: string;
  status?: string;
  exploit_status?: string;
  cve_id?: string;
  publish_date?: string;
  created_at?: string;
}

export interface VulnerabilitiesListResponse {
  total: number;
  page: number;
  limit: number;
  items: VulnerabilityItem[];
}

export interface VulnerabilitiesSummary {
  total_in_db: number;
  critical_count: number;
  high_count: number;
  exploitable_count: number;
}

export interface SoftwareVulnerabilityDetail {
  installed_software_id: string;
  software_name: string;
  publisher?: string;
  version?: string;
  vulnerabilities_count: number;
  vulnerabilities: VulnerabilityItem[];
}

export interface ComputerVulnerabilitiesResponse {
  computer_id: string;
  hostname: string;
  serial_number: string;
  total_vulnerabilities: number;
  critical_count: number;
  high_count: number;
  has_exploits?: boolean;
  affected_software: SoftwareVulnerabilityDetail[];
}

export interface VulnerabilitySyncResponse {
  success: boolean;
  imported_count: number;
  message: string;
}

export interface EulaAnalysisResult {
  commercial_use_allowed: boolean;
  risk_level: 'none' | 'low' | 'medium' | 'high' | 'critical';
  has_auto_renewal: boolean;
  trial_period_days?: number;
  key_restrictions: string[];
  summary_ru: string;
  analyzed_at?: string;
}

export interface AIChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  sql_executed?: string;
  data?: any[];
  timestamp: string;
}
