/**
 * Meetings & Actions TypeScript Interfaces
 * Matches backend schemas and database models exactly.
 */

export type MeetingType =
  | 'INTERNAL_SYNC'
  | 'VERTICAL_REVIEW'
  | 'CORE_COORDINATION'
  | 'CROSS_VERTICAL'
  | 'EVENT_BRIEFING'
  | 'DEBRIEF'
  | 'EMERGENCY'
  | 'EVENT_TEAM_SYNC'
  | 'ORIENTING'
  | 'OTHER';

export type MeetingStatus = 'SCHEDULED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export type RSVPStatus = 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'TENTATIVE';

export interface MeetingParticipant {
  id: string;
  meeting_id: string;
  user_id: string;
  username?: string;
  full_name?: string;
  rsvp_status: RSVPStatus;
  invited_at: string;
  responded_at?: string;
  notes?: string;
}

export interface MeetingActionItem {
  id: string;
  meeting_id: string;
  description: string;
  assignee_id?: string;
  assignee_username?: string;
  assignee_full_name?: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  due_date?: string;
  is_converted: boolean;
  converted_task_id?: string;
  converted_at?: string;
  converted_by_id?: string;
  created_at: string;
  updated_at: string;
}

export interface MeetingResponse {
  id: string;
  title: string;
  description?: string;
  meeting_type: MeetingType;
  status: MeetingStatus;
  meeting_date: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  meeting_url?: string;
  minutes?: string;
  remarks?: string;
  vertical_id?: string;
  vertical_name?: string;
  event_id?: string;
  event_title?: string;
  organizer_id: string;
  organizer_username?: string;
  organizer_name?: string;
  created_at: string;
  updated_at: string;
  participants: MeetingParticipant[];
  action_items: MeetingActionItem[];
}

export interface MeetingListResponse {
  total: number;
  items: MeetingResponse[];
}

export interface MeetingCreate {
  title: string;
  description?: string;
  meeting_type?: MeetingType;
  meeting_date: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  meeting_url?: string;
  remarks?: string;
  vertical_id?: string;
  event_id?: string;
  participant_ids?: string[];
  include_all_organization?: boolean;
  target_vertical_ids?: string[];
  target_roles?: string[];
  target_role_vertical_pairs?: any[];
}

export interface MeetingUpdate {
  title?: string;
  description?: string;
  meeting_type?: MeetingType;
  status?: MeetingStatus;
  meeting_date?: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  meeting_url?: string;
  minutes?: string;
  remarks?: string;
}

export interface MeetingRSVPRequest {
  rsvp_status: RSVPStatus;
  notes?: string;
}

export interface MeetingActionItemCreate {
  description: string;
  assignee_id?: string;
  priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  due_date?: string;
}

export interface MeetingActionConvertToTaskRequest {
  vertical_id?: string;
  assigned_to_id?: string;
  title?: string;
  priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  deadline?: string;
}
