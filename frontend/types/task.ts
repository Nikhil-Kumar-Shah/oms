/**
 * Master Tasks & Comments Types
 * Aligned with backend app/schemas/task.py and app/models/task.py
 */

export type TaskType =
  | 'ROUTINE'
  | 'EVENT'
  | 'MILESTONE'
  | 'DOCUMENTATION'
  | 'MEETING_FOLLOW_UP';

export type TaskPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type TaskStatus = 'NOT_STARTED' | 'TODO' | 'IN_PROGRESS' | 'BLOCKED' | 'COMPLETED' | 'CANCELLED';
export type TaskHealth = 'ON_TRACK' | 'AT_RISK' | 'OVERDUE' | 'BLOCKED' | 'COMPLETE' | 'CRITICAL';

export interface TaskResponse {
  id: string;
  vertical_id: string;
  vertical_name?: string;
  assigned_to_id?: string;
  assigned_to_username?: string;
  assigned_to_name?: string;
  assigned_by_id: string;
  assigned_by_username?: string;
  title: string;
  description?: string;
  task_type: TaskType;
  priority: TaskPriority;
  status: TaskStatus;
  completion_percentage: number;
  health: TaskHealth;
  date_assigned: string;
  deadline?: string;
  completed_on?: string;
  blockers?: string;
  remarks?: string;
  latest_update?: string;
  evidence_link?: string;
  deficiency?: string;
  is_escalated: boolean;
  escalated_to_id?: string;
  escalated_to_username?: string;
  escalation_reason?: string;
  escalated_at?: string;
  escalation_status?: string;
  escalation_resolution?: string;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  total: number;
  items: TaskResponse[];
}

export interface TaskCreate {
  vertical_id?: string;
  assigned_to_id?: string;
  is_self_task?: boolean;
  vertical_ids?: string[];
  user_ids?: string[];
  role_ids?: string[];
  include_all?: boolean;
  audience?: any;
  title: string;
  description?: string;
  task_type?: TaskType;
  priority?: TaskPriority;
  deadline?: string;
  blockers?: string;
  remarks?: string;
  evidence_link?: string;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  task_type?: TaskType;
  priority?: TaskPriority;
  deadline?: string;
  completion_percentage?: number;
  blockers?: string;
  remarks?: string;
  latest_update?: string;
  evidence_link?: string;
  deficiency?: string;
}

export interface TaskTransitionRequest {
  status: TaskStatus;
  completion_percentage?: number;
  blockers?: string;
  remarks?: string;
}

export interface TaskAssignRequest {
  assigned_to_id?: string;
}

export interface TaskReassignRequest {
  new_assigned_to_id: string;
  remarks?: string;
}

export interface TaskEscalateRequest {
  reason: string;
  escalated_to_id?: string;
  remarks?: string;
}

export interface TaskResolveEscalationRequest {
  resolution: string;
  remarks?: string;
}

export interface TaskBlockRequest {
  blocker_description: string;
}

export interface TaskUnblockRequest {
  resolution?: string;
}

export interface TaskCommentCreate {
  content: string;
}

export interface TaskCommentResponse {
  id: string;
  task_id: string;
  author_id: string;
  author_username?: string;
  author_name?: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface TaskHistoryResponse {
  id: string;
  task_id: string;
  actor_id?: string;
  actor_username?: string;
  action: string;
  previous_value?: Record<string, unknown>;
  new_value?: Record<string, unknown>;
  timestamp: string;
  correlation_id?: string;
}
