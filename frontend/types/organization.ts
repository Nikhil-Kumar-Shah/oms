/**
 * Organization & Vertical Types
 * Aligned with backend app/schemas/organization.py and app/schemas/user.py
 */

export interface Vertical {
  id: string;
  name: string;
  description?: string;
  organization_id?: string;
  status: 'ACTIVE' | 'INACTIVE';
  lead_coordinator_id?: string;
  lead_coordinator_name?: string;
  created_at?: string;
}

export interface VerticalListResponse {
  total: number;
  items: Vertical[];
}

export interface OrganizationResponse {
  id: string;
  name: string;
  code: string;
  description?: string;
  created_at: string;
  updated_at: string;
  verticals: Vertical[];
}

export interface UserSummary {
  id: string;
  username: string;
  full_name: string;
  email?: string;
  account_status: string;
}

export interface UserListResponse {
  total: number;
  items: UserSummary[];
}

export interface SelectorOptionItem {
  id: string;
  type: 'USER' | 'MULTI_USER' | 'VERTICAL' | 'ROLE' | 'ROLE_IN_VERTICAL' | 'ALL_USERS' | 'EVENT_TEAM';
  label: string;
  sublabel?: string;
  badge?: string;
  member_count?: number;
  metadata?: Record<string, any>;
}

export interface SelectorGroupItem {
  type: string;
  id: string;
  name: string;
  member_count: number;
  vertical_id?: string;
  role?: string;
  metadata?: Record<string, any>;
}

export interface SelectorUserItem {
  id: string;
  username: string;
  full_name?: string;
  email?: string;
  role?: { name: string };
  vertical?: { id: string; name: string };
  account_status?: string;
}

export interface SelectorResponse {
  selection_type: string;
  total: number;
  items: SelectorOptionItem[];
  groups?: SelectorGroupItem[];
  users?: SelectorUserItem[];
}

export interface UniversalAudienceSelection {
  scope?: 'ALL' | 'VERTICAL' | 'ROLE' | 'ROLE_VERTICAL' | 'USER' | 'EVENT_TEAM';
  include_all?: boolean;
  vertical_ids?: string[];
  role_ids?: string[];
  role_vertical_pairs?: { role: string; vertical_id: string; label?: string; member_count?: number }[];
  user_ids?: string[];
  event_team_ids?: string[];
  exclude_user_ids?: string[];
}

export interface AudienceResolveRequest {
  all_users?: boolean;
  vertical_ids?: string[];
  role_ids?: string[];
  user_ids?: string[];
  event_id?: string;
  usage?: 'assignment' | 'audience' | 'general';
}

export interface ResolvedUserSummary {
  id: string;
  username: string;
  full_name?: string;
  email?: string;
  account_status: string;
  roles: string[];
  verticals: string[];
}

export interface AudienceResolveResponse {
  total_count: number;
  user_ids: string[];
  users: ResolvedUserSummary[];
  audience_summary: string;
  is_all_users?: boolean;
}


