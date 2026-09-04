/**
 * Event & Readiness Types
 * Aligned with backend app/schemas/event.py and app/models/event.py
 */

export type EventType =
  | 'TOURNAMENT'
  | 'MATCH'
  | 'WORKSHOP'
  | 'CEREMONY'
  | 'TRAINING'
  | 'MEETING'
  | 'OTHER';

export type EventStatus =
  | 'PLANNING'
  | 'NOT_STARTED'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'ARCHIVED';

export type EventMemberRole =
  | 'HEAD'
  | 'POC'
  | 'COORDINATOR'
  | 'VOLUNTEER'
  | 'MEMBER';

export type EventMemberStatus = 'ACTIVE' | 'INACTIVE' | 'REMOVED';

export type ReadinessCategory =
  | 'PLANNING'
  | 'COORDINATION'
  | 'DOCUMENTATION'
  | 'COMMUNICATIONS'
  | 'TECHNICAL_PREPARATION'
  | 'MOCK_TRIAL'
  | 'FINAL_APPROVAL'
  | 'EXECUTION_READINESS';

export type ReadinessStatus =
  | 'NOT_STARTED'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'BLOCKED'
  | 'NOT_APPLICABLE';

export interface EventBase {
  name: string;
  description?: string;
  event_type?: EventType;
  planned_date?: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  society_name?: string;
  resource_links?: Record<string, unknown>;
  remarks?: string;
}

export interface EventPOCContact {
  name: string;
  phone?: string;
  email?: string;
  designation?: string;
}

export interface EventCreate extends EventBase {
  vertical_id: string;
  event_team_user_id?: string;
  event_head_name?: string;
  event_head_phone?: string;
  event_head_email?: string;
  additional_pocs?: EventPOCContact[];
  event_head_id?: string;
  event_head_user_id?: string;
  poc_head_user_id?: string;
  primary_poc_id?: string;
  primary_poc_user_id?: string;
  additional_poc_user_ids?: string[];
}

export interface EventUpdate {
  name?: string;
  description?: string;
  event_type?: EventType;
  planned_date?: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  society_name?: string;
  resource_links?: Record<string, unknown>;
  remarks?: string;
}

export interface EventTransitionRequest {
  status: EventStatus;
  remarks?: string;
}

export interface EventAssignPOCRequest {
  event_head_id?: string;
  primary_poc_id?: string;
}

export interface EventResponse extends EventBase {
  id: string;
  vertical_id: string;
  vertical_name?: string;
  status: EventStatus;
  event_head_id?: string;
  event_head_username?: string;
  primary_poc_id?: string;
  primary_poc_username?: string;
  event_team_user_id?: string;
  event_team_username?: string;
  event_team_name?: string;
  created_by_id: string;
  created_by_username?: string;
  created_at: string;
  updated_at: string;
}

export interface EventListResponse {
  total: number;
  items: EventResponse[];
}

export interface EventMemberResponse {
  id: string;
  event_id: string;
  user_id: string;
  username?: string;
  full_name?: string;
  role_in_event: EventMemberRole;
  status: EventMemberStatus;
  assigned_by_id: string;
  assigned_at: string;
  notes?: string;
}

export interface EventMemberCreate {
  user_id: string;
  role_in_event?: EventMemberRole;
  notes?: string;
}

export interface EventMemberUpdate {
  role_in_event?: EventMemberRole;
  status?: EventMemberStatus;
  notes?: string;
}

export interface EventReadinessItemResponse {
  id: string;
  event_id: string;
  category: ReadinessCategory;
  title: string;
  description?: string;
  status: ReadinessStatus;
  assigned_user_id?: string;
  assigned_username?: string;
  deadline?: string;
  completed_at?: string;
  completed_by_id?: string;
  evidence_link?: string;
  remarks?: string;
  updated_at: string;
}

export interface EventReadinessUpdate {
  status: ReadinessStatus;
  assigned_user_id?: string;
  deadline?: string;
  evidence_link?: string;
  remarks?: string;
}

export interface POCMemberSummary {
  user_id: string;
  username?: string;
  full_name?: string;
  role_in_event: EventMemberRole;
  status: EventMemberStatus;
  notes?: string;
}

export interface POCGroupAssignRequest {
  head_poc_id: string;
  poc_member_ids?: string[];
  notes?: string;
}

export interface POCGroupResponse {
  event_id: string;
  event_name: string;
  vertical_id: string;
  head_poc?: POCMemberSummary;
  poc_members: POCMemberSummary[];
  total_poc_count: number;
}

export interface EventDashboardResponse {
  event: EventResponse;
  team_members: EventMemberResponse[];
  readiness_items: EventReadinessItemResponse[];
  readiness_summary: Record<string, number>;
  tasks_count: number;
  tasks: Array<{
    id: string;
    title: string;
    status: string;
    priority: string;
    assigned_to_username?: string;
    deadline?: string;
    completion_percentage: number;
    health: string;
    blockers?: string;
  }>;
  requirements_count: number;
  requirements: Array<{
    id: string;
    title: string;
    status: string;
    priority: string;
    source_vertical_name?: string;
    target_vertical_name?: string;
    deadline?: string;
  }>;
  meetings_count: number;
  meetings: Array<{
    id: string;
    title: string;
    meeting_date: string;
    start_time?: string;
    status: string;
    organizer_username?: string;
  }>;
  issues_count: number;
  issues: Array<{
    id: string;
    title: string;
    status: string;
    sensitivity: string;
    raised_by_username?: string;
    escalation_target?: string;
  }>;
}
