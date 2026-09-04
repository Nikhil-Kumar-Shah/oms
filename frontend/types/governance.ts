/**
 * Governance Domain Types
 * Matches backend schemas in app/schemas/governance.py and app/schemas/audit.py
 */

export type TransferResourceType = 'ACCOUNT' | 'TASK' | 'EVENT' | 'REQUIREMENT';
export type TransferStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED' | 'COMPLETED';

export type ConfigValueType = 'STRING' | 'INTEGER' | 'FLOAT' | 'BOOLEAN' | 'JSON';

export interface OwnershipTransferCreate {
  resource_type: TransferResourceType;
  resource_id: string;
  requested_owner_id: string;
  reason: string;
}

export interface SuccessionUserSummary {
  id: string;
  username: string;
  full_name: string;
  email?: string | null;
  account_status: string;
  role_name?: string | null;
}

export interface SuccessionTaskSummary {
  id: string;
  title: string;
  priority: string;
  status: string;
  vertical_name?: string | null;
}

export interface SuccessionEventSummary {
  id: string;
  name: string;
  status: string;
  role: string;
}

export interface SuccessionVerticalSummary {
  id: string;
  name: string;
  is_primary: boolean;
}

export interface AccountSuccessionPreviewResponse {
  previous_user: SuccessionUserSummary;
  successor_user: SuccessionUserSummary;
  active_tasks_count: number;
  active_tasks: SuccessionTaskSummary[];
  active_events_count: number;
  active_events: SuccessionEventSummary[];
  active_requirements_count: number;
  assigned_verticals: SuccessionVerticalSummary[];
  historical_preservation_note: string;
}

export interface AccountSuccessionCreate {
  previous_user_id: string;
  successor_user_id: string;
  reason: string;
}

export interface OwnershipTransferReviewRequest {
  status: TransferStatus;
  remarks?: string;
}

export interface OwnershipTransferResponse {
  id: string;
  resource_type: TransferResourceType;
  resource_id: string;
  resource_name?: string | null;
  current_owner_id: string;
  current_owner_username?: string | null;
  requested_owner_id: string;
  requested_owner_username?: string | null;
  requested_by_id: string;
  requested_by_username?: string | null;
  reviewed_by_id?: string | null;
  reviewed_by_username?: string | null;
  reason: string;
  status: TransferStatus;
  remarks?: string | null;
  created_at: string;
  reviewed_at?: string | null;
  completed_at?: string | null;
}

export interface OwnershipTransferListResponse {
  total: number;
  items: OwnershipTransferResponse[];
}

export interface SystemConfigCreate {
  key: string;
  value: string;
  value_type?: ConfigValueType;
  description?: string;
  is_active?: boolean;
}

export interface SystemConfigUpdate {
  value: string;
  description?: string;
  is_active?: boolean;
}

export interface SystemConfigResponse {
  id: string;
  key: string;
  value: string;
  value_type: ConfigValueType;
  description?: string | null;
  is_active: boolean;
  updated_by_id?: string | null;
  updated_by_username?: string | null;
  updated_at: string;
}

export interface SystemConfigListResponse {
  total: number;
  items: SystemConfigResponse[];
}

export interface AuditLogResponse {
  id: string;
  timestamp: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  actor_id?: string | null;
  actor_username?: string | null;
  correlation_id?: string | null;
  ip_address?: string | null;
  outcome: string;
  details?: Record<string, unknown> | null;
  created_at?: string;
}

export interface AuditLogListResponse {
  total: number;
  items: AuditLogResponse[];
}
