/**
 * Operational Workspace Types
 * Aligned with backend GET /api/v1/workspace/my-work contract.
 */

export type TaskPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type TaskStatus = 'NOT_STARTED' | 'TODO' | 'IN_PROGRESS' | 'BLOCKED' | 'COMPLETED' | 'CANCELLED';
export type TaskHealth = 'ON_TRACK' | 'AT_RISK' | 'OVERDUE' | 'BLOCKED' | 'COMPLETE';
export type TaskType = 'ROUTINE' | 'EVENT' | 'MILESTONE' | 'DOCUMENTATION' | 'MEETING_FOLLOW_UP';

export type DirectivePriority = 'STANDARD' | 'URGENT' | 'CRITICAL';
export type MeetingType = 'TEAM_SYNC' | 'EXECUTIVE' | 'PLANNING' | 'EMERGENCY';
export type RSVPStatus = 'INVITED' | 'ACCEPTED' | 'DECLINED' | 'TENTATIVE';
export type EventType = 'TOURNAMENT' | 'TRAINING_CAMP' | 'WORKSHOP' | 'COMPETITION';
export type EventStatus = 'DRAFT' | 'PLANNED' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
export type EventMemberRole = 'LEAD' | 'LOGISTICS' | 'VOLUNTEER' | 'MEDIC' | 'MEDIA';

export interface MyWorkTaskItem {
  id: string;
  title: string;
  description?: string;
  vertical_id: string;
  vertical_name?: string;
  task_type?: TaskType;
  priority: TaskPriority;
  status: TaskStatus;
  health: TaskHealth;
  progress_percentage: number;
  deadline?: string;
  blocker_reason?: string;
  assigned_to_id?: string;
  assigned_to_name?: string;
  assigned_to_username?: string;
  assigned_by_id?: string;
  assigned_by_name?: string;
  assigned_by_username?: string;
  event_id?: string;
  event_title?: string;
  created_at: string;
}

export interface MyWorkDirectiveItem {
  id: string;
  directive_id: string;
  title: string;
  summary: string;
  priority: DirectivePriority;
  issued_by_name?: string;
  deadline?: string;
  issued_at: string;
}

export interface MyWorkMeetingItem {
  id: string;
  title: string;
  meeting_type: MeetingType;
  meeting_date: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  meeting_url?: string;
  rsvp_status: RSVPStatus;
  organizer_name?: string;
}

export interface MyWorkEventDutyItem {
  event_id: string;
  title: string;
  event_type: EventType;
  event_status: EventStatus;
  planned_date: string;
  role: EventMemberRole;
  location?: string;
}

export interface MyWorkFormItem {
  id: string;
  form_id: string;
  form_title: string;
  purpose: string;
  category?: string;
  status: string;
  deadline?: string;
  vertical_name?: string;
  instructions?: string;
  created_at?: string;
}

export interface MyWorkReviewItem {
  id: string;
  item_type: 'FORM_REVIEW' | 'TRANSFER_APPROVAL' | string;
  title: string;
  submitted_by_name?: string;
  submitted_at?: string;
  status: string;
  urgency: 'NORMAL' | 'HIGH' | 'CRITICAL' | string;
  target_entity_id?: string;
  link: string;
}

export interface MyWorkIssueItem {
  id: string;
  title: string;
  status: string;
  sensitivity: string;
  vertical_name?: string;
  event_reference?: string;
  raised_by_name?: string;
  assigned_to_name?: string;
  deadline?: string;
  escalation_target?: string;
  action_required?: string;
  created_at: string;
}

export interface MyWorkPriorityItem {
  id: string;
  item_type: 'TASK' | 'ISSUE' | 'FORM' | 'REVIEW' | 'APPROVAL' | string;
  title: string;
  urgency: 'OVERDUE' | 'CRITICAL' | 'APPROVAL_NEEDED' | 'DEADLINE_SOON' | 'ACTION_REQUIRED' | string;
  urgency_label: string;
  due_date?: string;
  detail?: string;
  action_link: string;
  action_label: string;
}

export interface MyWorkEventTeamProfile {
  team_name: string;
  head_name?: string;
  head_email?: string;
  head_phone?: string;
  event_id?: string;
  event_name?: string;
  members_count: number;
}

export interface MyWorkUserContext {
  primary_role: string;
  operational_level?: number;
  responsibilities: string[];
  verticals: string[];
  event_team_profile?: MyWorkEventTeamProfile;
  attention_summary: string;
  requires_immediate_attention: boolean;
}

export interface MyWorkStats {
  active_tasks: number;
  completed_tasks: number;
  created_by_me_tasks: number;
  pending_directives: number;
  upcoming_meetings: number;
  event_duties: number;
  blocked_tasks: number;
  overdue_tasks: number;
  active_issues?: number;
  pending_forms?: number;
  pending_reviews?: number;
  pending_approvals?: number;
}

export interface UnifiedMyWorkResponse {
  user_id: string;
  username: string;
  full_name: string;
  context?: MyWorkUserContext;
  stats: MyWorkStats;
  priority_queue?: MyWorkPriorityItem[];
  tasks: MyWorkTaskItem[];
  completed_tasks: MyWorkTaskItem[];
  created_by_me_tasks: MyWorkTaskItem[];
  pending_forms?: MyWorkFormItem[];
  pending_reviews?: MyWorkReviewItem[];
  active_issues?: MyWorkIssueItem[];
  pending_directives: MyWorkDirectiveItem[];
  meetings: MyWorkMeetingItem[];
  event_duties: MyWorkEventDutyItem[];
  blockers: MyWorkTaskItem[];
  overdue: MyWorkTaskItem[];
}
