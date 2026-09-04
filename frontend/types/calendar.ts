/**
 * Master & Personal Calendar Types
 * Aligned with backend app/schemas/calendar.py and app/models/calendar.py
 */

export type ActivityCategory =
  | 'ACTIVITY'
  | 'MILESTONE'
  | 'REVIEW_MEETING'
  | 'INTERVIEW'
  | 'REPORT_DEADLINE'
  | 'ONBOARDING'
  | 'ORIENTATION'
  | 'EVENT'
  | 'MEETING';

export type CalendarPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type CalendarStatus = 'PLANNED' | 'UPCOMING' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED' | 'RESCHEDULED';
export type DeadlineType = 'HARD_DEADLINE' | 'SOFT_DEADLINE' | 'INFORMATIONAL';
export type CalendarAudience = 'ALL' | 'ORGANIZATION' | 'VERTICAL' | 'SPECIFIC_USERS';
export type RecurrenceFrequency = 'NONE' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
export type CalendarEntityType = 'CALENDAR_ENTRY' | 'TASK' | 'MEETING' | 'EVENT';

export interface CalendarResponse {
  id: string;
  title: string;
  description?: string;
  activity_date: string;
  start_time?: string;
  end_time?: string;
  category: ActivityCategory;
  priority: CalendarPriority;
  status: CalendarStatus;
  deadline_type: DeadlineType;
  audience: CalendarAudience;
  vertical_id?: string;
  vertical_name?: string;
  event_reference?: string;
  resource_link?: string;
  remarks?: string;
  recurrence?: RecurrenceFrequency;
  recurrence_end_date?: string;
  entity_type?: CalendarEntityType | string;
  entity_id?: string;
  is_personal?: boolean;
  task_id?: string;
  event_id?: string;
  meeting_id?: string;
  requirement_id?: string;
  created_by_id: string;
  created_by_username?: string;
  target_user_ids?: string[];
  created_at: string;
  updated_at: string;
  original_date?: string;
  rescheduled_at?: string;
  is_user_completed?: boolean;
  user_completed_at?: string;
}

export interface CalendarActionPayload {
  action: 'mark_completed_for_me' | 'complete' | 'in_progress' | 'cancel';
  remarks?: string;
}

export interface CalendarReschedulePayload {
  new_date: string;
  new_start_time?: string;
  new_end_time?: string;
  reason?: string;
}

export interface CalendarListResponse {
  total: number;
  items: CalendarResponse[];
}

export interface CalendarCreate {
  title: string;
  description?: string;
  activity_date: string;
  start_time?: string;
  end_time?: string;
  category?: ActivityCategory;
  priority?: CalendarPriority;
  status?: CalendarStatus;
  deadline_type?: DeadlineType;
  audience?: CalendarAudience;
  vertical_id?: string;
  event_reference?: string;
  resource_link?: string;
  remarks?: string;
  is_personal?: boolean;
  user_ids?: string[];
  vertical_ids?: string[];
  role_ids?: string[];
  all_users?: boolean;
  entity_type?: string;
  entity_id?: string;
  recurrence?: RecurrenceFrequency;
  recurrence_end_date?: string;
  task_id?: string;
  event_id?: string;
  meeting_id?: string;
  requirement_id?: string;
}

export interface CalendarUpdate {
  title?: string;
  description?: string;
  activity_date?: string;
  start_time?: string;
  end_time?: string;
  category?: ActivityCategory;
  priority?: CalendarPriority;
  status?: CalendarStatus;
  deadline_type?: DeadlineType;
  audience?: CalendarAudience;
  vertical_id?: string;
  event_reference?: string;
  resource_link?: string;
  remarks?: string;
  entity_type?: string;
  entity_id?: string;
  recurrence?: RecurrenceFrequency;
  recurrence_end_date?: string;
  task_id?: string;
  event_id?: string;
  meeting_id?: string;
  requirement_id?: string;
}
