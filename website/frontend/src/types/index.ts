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
  created_at?: string;
  updated_at?: string;
  computers_count?: number;
  computers?: Computer[];
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
  max_installations: number; // 0 = unlimited
  active_installations_count?: number;
  responsible_person?: string;
  approval_status?: 'approved' | 'review' | 'rejected';
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
  category_id?: number | null;
  category_name?: string;
  is_problematic?: boolean;
  match_confidence: number;
  is_verified_by_admin: boolean;
  is_deleted: boolean;
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
  balance: number; // purchased - installed
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
  confidence: number;
  reasoning: string;
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
