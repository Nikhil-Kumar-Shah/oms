/**
 * Cross-Vertical Requirements TypeScript Interfaces
 * Matches backend schemas and database models exactly.
 */

export type RequirementPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type RequirementStatus =
  | 'RAISED'
  | 'ACKNOWLEDGED'
  | 'IN_PROGRESS'
  | 'AWAITING_INFO'
  | 'FORWARDED'
  | 'ESCALATED'
  | 'RESOLVED'
  | 'CLOSED'
  | 'OPEN'
  | 'ASSIGNED'
  | 'BLOCKED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'REJECTED';

export interface ForwardHistoryItem {
  forwarded_by_id: string;
  forwarded_by_name: string;
  forwarded_to_id: string;
  forwarded_to_name: string;
  forwarded_to_type: 'USER' | 'VERTICAL';
  reason: string;
  timestamp: string;
}

export interface RequirementMessage {
  id: string;
  requirement_id: string;
  author_id: string;
  author_username?: string;
  author_full_name?: string;
  content: string;
  created_at: string;
}

export interface RequirementResponse {
  id: string;
  title: string;
  description: string;
  event_id?: string;
  event_name?: string;
  responsible_poc_id?: string;
  responsible_poc_username?: string;
  responsible_poc_full_name?: string;
  requesting_vertical_id?: string;
  requesting_vertical_name?: string;
  target_vertical_id?: string;
  target_vertical_name?: string;
  requester_id: string;
  requester_username?: string;
  requester_full_name?: string;
  assignee_id?: string;
  assignee_username?: string;
  assignee_full_name?: string;
  priority: RequirementPriority;
  status: RequirementStatus;
  deadline?: string;
  remarks?: string;
  reference_link?: string;
  forward_history: ForwardHistoryItem[];

  // Escalation fields
  is_escalated: boolean;
  escalated_to_id?: string;
  escalated_to_username?: string;
  escalated_to_full_name?: string;
  escalated_by_id?: string;
  escalated_by_username?: string;
  escalated_by_full_name?: string;
  escalated_at?: string;
  escalation_reason?: string;
  escalation_status?: string;
  escalation_resolved_at?: string;
  escalation_resolved_by_id?: string;
  escalation_resolution_notes?: string;

  created_at: string;
  updated_at: string;
  messages_count: number;
}

export interface RequirementListResponse {
  total: number;
  items: RequirementResponse[];
}

export interface RequirementCreate {
  title: string;
  description: string;
  priority?: RequirementPriority;
  deadline?: string;
  remarks?: string;
  reference_link?: string;
  requesting_vertical_id?: string;
  target_vertical_id?: string;
  assignee_id?: string;
  event_id?: string;
}

export interface RequirementUpdate {
  title?: string;
  description?: string;
  priority?: RequirementPriority;
  deadline?: string;
  remarks?: string;
}

export interface RequirementTransitionRequest {
  status: RequirementStatus;
  remarks?: string;
}

export interface RequirementForwardRequest {
  target_user_id?: string;
  target_vertical_id?: string;
  reason: string;
}

export interface RequirementAssignRequest {
  assignee_id?: string;
}

export interface RequirementEscalateRequest {
  escalated_to_id: string;
  reason: string;
}

export interface RequirementResolveEscalationRequest {
  resolution_notes: string;
}
