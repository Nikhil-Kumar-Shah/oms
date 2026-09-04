/**
 * User & Organization Canonical Models
 * Matches backend database entity models exactly.
 */

export type CanonicalRole =
  | 'ADMIN'
  | 'SPORTS_CORE'
  | 'DEPUTY_CORE'
  | 'SUPER_COORDINATOR'
  | 'COORDINATOR'
  | 'VOLUNTEER'
  | 'EVENT_TEAM';

export type AccountStatus = 'ACTIVE' | 'SUSPENDED' | 'DISABLED';

export interface RoleSummary {
  id: string;
  name: CanonicalRole;
  description?: string;
}

export interface PermissionSummary {
  id: string;
  code: string;
  description: string;
  category: string;
}

export interface RoleDetail {
  id: string;
  name: CanonicalRole;
  description: string;
  is_system: boolean;
  permissions?: PermissionSummary[];
  role_permissions?: {
    permission_id: string;
    permission: PermissionSummary;
  }[];
}

export type UserAvailability = 'AVAILABLE' | 'BUSY' | 'ON_LEAVE' | 'EMERGENCY_ONLY';

export interface UserOperationalProfile {
  id: string;
  user_id: string;
  username?: string;
  full_name?: string;
  email?: string;
  phone_number?: string;
  specialization?: string;
  operational_capability?: string;
  certifications?: string[];
  availability: UserAvailability;
  profile_notes?: string;
  created_at: string;
  updated_at: string;
}

export interface UserOperationalProfileUpdate {
  phone_number?: string;
  specialization?: string;
  operational_capability?: string;
  certifications?: string[];
  availability?: UserAvailability;
  profile_notes?: string;
}

export interface VerticalMembership {
  id: string;
  name: string;
  is_primary: boolean;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  full_name: string;
  account_status: AccountStatus;
  roles: (RoleSummary | CanonicalRole)[];
  verticals: VerticalMembership[];
  effective_permissions?: string[];
  created_at?: string;
  updated_at?: string;
  last_login_at?: string;
}

export interface UserResponse {
  id: string;
  username: string;
  full_name: string;
  email?: string;
  account_status: AccountStatus;
  roles: RoleSummary[];
  verticals: VerticalMembership[];
  last_login_at?: string;
  disabled_at?: string;
  created_at: string;
  updated_at: string;
}

export interface UserListResponse {
  total: number;
  items: UserResponse[];
}

export interface UserCreateInput {
  username: string;
  full_name: string;
  email?: string;
  password: string;
  role_ids?: string[];
  vertical_ids?: string[];
}

export interface UserUpdateInput {
  full_name?: string;
  email?: string;
}

export interface EventTeamUserCreateInput extends UserCreateInput {
  event_id: string;
  team_name: string;
  head_name?: string;
  head_phone?: string;
  head_email?: string;
  notes?: string;
}
