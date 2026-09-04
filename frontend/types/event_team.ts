/**
 * Event Team Account & Profile Types
 * Aligned with backend app/schemas/event_team.py and app/models/event.py
 */

export interface EventTeamCredentialsCreate {
  username: string;
  password: string;
  email?: string;
  team_name?: string;
}

export interface EventTeamActivate {
  team_name: string;
  head_name: string;
  head_phone: string;
  head_email: string;
  user_id: string;
  head_poc_id: string;
  additional_poc_ids: string[];
  event_id: string;
  notes?: string;
}

export interface UnactivatedAccountResponse {
  id: string;
  username: string;
  email?: string;
  full_name?: string;
  account_status: string;
  created_at: string;
}

export interface EventTeamCreate {
  username: string;
  password: string;
  email?: string;
  full_name?: string;
  event_id?: string;
  team_name?: string;
  head_name?: string;
  head_email?: string;
  head_phone?: string;
  members_summary?: Array<{
    name: string;
    role: string;
    contact?: string;
  }>;
  contact_info?: Record<string, unknown>;
  event_metadata?: Record<string, unknown>;
  notes?: string;
}

export interface EventTeamUpdate {
  event_id?: string;
  team_name?: string;
  head_name?: string;
  head_email?: string;
  head_phone?: string;
  members_summary?: Array<{
    name: string;
    role: string;
    contact?: string;
  }>;
  contact_info?: Record<string, unknown>;
  event_metadata?: Record<string, unknown>;
  notes?: string;
}

export interface EventTeamProfileResponse {
  id: string;
  user_id: string;
  username?: string;
  account_status?: string;
  is_activated?: boolean;
  event_id?: string | null;
  event_name?: string | null;
  event_date?: string | null;
  event_status?: string | null;
  team_name: string;
  head_name?: string;
  head_email?: string;
  head_phone?: string;
  head_poc_id?: string | null;
  head_poc_name?: string | null;
  head_poc_username?: string | null;
  additional_pocs?: Array<{
    id: string;
    name: string;
    username: string;
    email?: string;
  }>;
  members_summary: Array<{
    name: string;
    role: string;
    contact?: string;
  }>;
  contact_info: Record<string, unknown>;
  event_metadata: Record<string, unknown>;
  notes?: string;

  requirements_count?: number;
  issues_count?: number;
  meetings_count?: number;
  members_count?: number;

  created_at: string;
  updated_at: string;
}

export interface EventTeamListResponse {
  total: number;
  items: EventTeamProfileResponse[];
}
