/**
 * Issues & Escalations Types
 * Aligned with backend app/schemas/issue.py
 */

export type IssueSensitivity = 'NORMAL' | 'SENSITIVE' | 'CONFIDENTIAL';
export type IssueStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED' | 'ESCALATED';

export interface IssueResponse {
  id: string;
  date_raised: string;
  vertical_id: string;
  vertical_name?: string;
  event_reference?: string;
  title: string;
  description: string;
  raised_by_id: string;
  raised_by_username?: string;
  assigned_to_id?: string;
  assigned_to_username?: string;
  assignee_ids?: string[];
  assignees?: { id: string; username: string; full_name?: string }[];
  sensitivity: IssueSensitivity;
  status: IssueStatus;
  action_required?: string;
  deadline?: string;
  escalation_target?: string;
  escalation_action?: string;
  resolution?: string;
  resolution_date?: string;
  evidence_link?: string;
  remarks?: string;
  created_at: string;
  updated_at: string;
}

export interface IssueListResponse {
  total: number;
  items: IssueResponse[];
}

export interface IssueCreate {
  title: string;
  description: string;
  vertical_id?: string;
  vertical_ids?: string[];
  all_users?: boolean;
  assigned_to_id?: string | null;
  assignee_user_ids?: string[];
  assignee_role_ids?: string[];
  assignee_vertical_ids?: string[];
  assignee_all_users?: boolean;
  sensitivity?: IssueSensitivity;
  action_required?: string | null;
  deadline?: string | null;
  evidence_link?: string | null;
  event_reference?: string | null;
  remarks?: string | null;
}

export interface IssueUpdate {
  title?: string;
  description?: string;
  event_reference?: string;
  assigned_to_id?: string;
  sensitivity?: IssueSensitivity;
  action_required?: string;
  deadline?: string;
  evidence_link?: string;
  remarks?: string;
}

export interface IssueTransitionRequest {
  status: IssueStatus;
  resolution?: string;
  remarks?: string;
}

export interface IssueEscalateRequest {
  escalation_target: string;
  escalation_action: string;
  deadline?: string;
  remarks?: string;
}

export interface IssueHistoryResponse {
  id: string;
  issue_id: string;
  actor_id?: string;
  actor_username?: string;
  action: string;
  details?: Record<string, unknown>;
  timestamp: string;
  correlation_id?: string;
}

export interface IssueCommentCreate {
  content: string;
}

export interface IssueCommentResponse {
  id: string;
  issue_id: string;
  author_id: string;
  author_username?: string;
  author_name?: string;
  content: string;
  created_at: string;
  updated_at: string;
}
