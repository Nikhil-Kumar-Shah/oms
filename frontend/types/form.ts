/**
 * Forms Domain Types
 * Matches backend schemas in app/schemas/form.py
 * Paradox Sports OMS - Phase 11 Form & Response Workflow System
 */

export type FormStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
export type FormAudience = 'ALL' | 'ORGANIZATION' | 'VERTICAL' | 'SPECIFIC_ROLES' | 'EVENT' | 'EVENT_TEAM';
export type FormFieldType =
  | 'TEXT'
  | 'LONG_TEXT'
  | 'NUMBER'
  | 'BOOLEAN'
  | 'DATE'
  | 'DATETIME'
  | 'SELECT'
  | 'MULTI_SELECT'
  | 'CHECKBOX'
  | 'RADIO'
  | 'YES_NO'
  | 'REFERENCE_LINK'
  | 'URL'
  | 'EMAIL'
  | 'PHONE'
  | 'USER_REFERENCE'
  | 'VERTICAL_REFERENCE';

export type FormResponseStatus =
  | 'DRAFT'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'RETURNED'
  | 'RESUBMITTED'
  | 'APPROVED'
  | 'REJECTED'
  | 'CANCELLED';

// Backward compatibility alias
export type FormSubmissionStatus = FormResponseStatus;

export type ChecklistStatus = 'PENDING' | 'PASSED' | 'FAILED' | 'WAIVED';

export interface FormFieldSchema {
  id?: string;
  key: string;
  label: string;
  type: FormFieldType;
  required?: boolean;
  default_value?: unknown;
  placeholder?: string;
  options?: string[];
  validation_rules?: Record<string, unknown>;
  ordering?: number;
  help_text?: string;
}


export interface FormSectionSchema {
  id?: string;
  title: string;
  description?: string;
  ordering?: number;
  fields: FormFieldSchema[];
}

export interface FormChecklistConfigItem {
  phase_number: number;
  phase_name: string;
  title: string;
  description?: string;
  role_label?: string;
}

export interface FormTransformationConfig {
  target_entity: 'TASK' | 'REQUIREMENT' | 'EVENT';
  field_mappings: Record<string, string>;
}

export interface FormVersionCreate {
  sections?: FormSectionSchema[];
  schema_fields?: FormFieldSchema[];
  review_config?: FormChecklistConfigItem[];
  transformation_config?: FormTransformationConfig;
}

export interface FormVersionResponse {
  id: string;
  form_id: string;
  version_number: number;
  sections?: FormSectionSchema[];
  schema_fields?: FormFieldSchema[];
  schema?: FormFieldSchema[];
  review_config?: FormChecklistConfigItem[] | null;
  transformation_config?: FormTransformationConfig | null;
  is_published: boolean;
  published_at?: string | null;
  published_by_id?: string | null;
  published_by_username?: string | null;
  created_at: string;
}

export interface FormCreate {
  name: string;
  description?: string;
  purpose: string;
  instructions?: string;
  category?: string;
  target_audience?: FormAudience;
  vertical_id?: string;
  event_id?: string;
  sections?: FormSectionSchema[];
  initial_schema?: FormFieldSchema[];
  review_config?: FormChecklistConfigItem[];
  transformation_config?: FormTransformationConfig;
  distribution_config?: Record<string, any>;
  publish_and_distribute?: boolean;
  recipient_ids?: string[];
  distribution_deadline?: string;
  distribution_instructions?: string;
}

export interface FormUpdate {
  name?: string;
  description?: string;
  purpose?: string;
  instructions?: string;
  category?: string;
  target_audience?: FormAudience;
  vertical_id?: string;
  event_id?: string;
  status?: FormStatus;
  sections?: FormSectionSchema[];
  distribution_config?: Record<string, any>;
  publish_and_distribute?: boolean;
  recipient_ids?: string[];
  distribution_deadline?: string;
  distribution_instructions?: string;
}

export interface FormResponse {
  id: string;
  name: string;
  description?: string | null;
  purpose: string;
  instructions?: string | null;
  category?: string | null;
  status: FormStatus;
  owner_id: string;
  owner_username?: string | null;
  vertical_id?: string | null;
  vertical_name?: string | null;
  event_id?: string | null;
  event_name?: string | null;
  target_audience: FormAudience;
  current_version_number: number;
  distribution_config?: Record<string, any>;
  distributions?: FormDistributionResponse[];
  total_recipients?: number;
  responses_received?: number;
  pending_responses?: number;
  not_started_responses?: number;
  completed_responses?: number;
  completion_percentage?: number;
  deadline?: string | null;
  created_at: string;
  updated_at: string;
  latest_version?: FormVersionResponse | null;
}

export interface FormListResponse {
  total: number;
  items: FormResponse[];
}

// -------------------------------------------------------------
// Distribution Interfaces
// -------------------------------------------------------------

export interface FormReviewerAssignInput {
  user_id: string;
  role_label: string;
  phase_number: number;
}


export interface FormDistributeRequest {
  recipient_ids: string[];
  deadline?: string;
  instructions?: string;
  reviewers?: FormReviewerAssignInput[];
}

export interface FormDistributionResponse {
  id: string;
  form_id: string;
  form_name?: string | null;
  form_version_id: string;
  distributor_id: string;
  distributor_username?: string | null;
  title?: string | null;
  instructions?: string | null;
  deadline?: string | null;
  recipient_count: number;
  created_at: string;
}

export interface RecipientSummaryItem {
  response_id: string;
  recipient_id: string;
  recipient_name: string;
  recipient_username: string;
  event_id?: string | null;
  event_name?: string | null;
  status: FormResponseStatus;
  submitted_at?: string | null;
  resubmitted_at?: string | null;
  current_phase: number;
  checklist_completed_count: number;
  checklist_total_count: number;
}

export interface DistributionSummaryResponse {
  distribution_id?: string | null;
  form_id: string;
  form_name: string;
  version_number: number;
  total_recipients: number;
  counts: Record<string, number>;
  recipients: RecipientSummaryItem[];
}

// -------------------------------------------------------------
// Response & Review Workflow Interfaces
// -------------------------------------------------------------

export interface FormResponseSaveDraft {
  response_data: Record<string, unknown>;
}

export interface FormResponseSubmit {
  response_data: Record<string, unknown>;
}

export interface FormResponseReturnRequest {
  return_reason: string;
  reviewer_remarks?: string;
}

export interface FormResponseForwardRequest {
  target_user_id: string;
  message: string;
  role_label?: string;
  phase_number?: number;
}

export interface FormResponseReviewRequest {
  action: string;
  return_reason?: string;
  reviewer_remarks?: string;
  execute_transformation?: boolean;
}

export type FormSubmissionCreate = FormResponseSubmit;
export type FormSubmissionReviewRequest = FormResponseReviewRequest;

export interface FormReviewerResponse {
  id: string;
  response_id: string;
  user_id: string;
  username?: string | null;
  full_name?: string | null;
  role_label: string;
  phase_number: number;
  status: string;
  decision_comments?: string | null;
  decided_at?: string | null;
  created_at: string;
}


export interface FormChecklistItemResponse {
  id: string;
  response_id: string;
  phase_number: number;
  phase_name: string;
  title: string;
  description?: string | null;
  reviewer_id?: string | null;
  reviewer_username?: string | null;
  reviewer_name?: string | null;
  status: ChecklistStatus;
  remarks?: string | null;
  evidence_link?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface ChecklistItemUpdate {
  status: ChecklistStatus;
  remarks?: string;
  evidence_link?: string;
}

export interface FormWorkflowHistoryResponse {
  id: string;
  response_id: string;
  actor_id?: string | null;
  actor_username?: string | null;
  actor_full_name?: string | null;
  action: string;
  from_status?: string | null;
  to_status?: string | null;
  message?: string | null;
  history_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface FormResponseDetailsResponse {
  id: string;
  form_id: string;
  form_name?: string | null;
  form_description?: string | null;
  form_purpose?: string | null;
  form_instructions?: string | null;
  form_version_id: string;
  version_number?: number | null;
  distribution_id?: string | null;
  recipient_id: string;
  recipient_username?: string | null;
  recipient_name?: string | null;
  event_id?: string | null;
  event_name?: string | null;
  status: FormResponseStatus;
  response_data: Record<string, unknown>;
  submitted_at?: string | null;
  resubmitted_at?: string | null;
  reviewed_at?: string | null;
  approved_at?: string | null;
  deadline?: string | null;
  return_reason?: string | null;
  reviewer_remarks?: string | null;
  current_reviewer_id?: string | null;
  current_reviewer_username?: string | null;
  current_phase: number;
  sections: FormSectionSchema[];
  schema_fields: FormFieldSchema[];
  reviewers: FormReviewerResponse[];
  checklist_items: FormChecklistItemResponse[];
  workflow_history: FormWorkflowHistoryResponse[];
  created_at: string;
  updated_at: string;
}

// Backward compatibility alias
export type FormSubmissionResponse = FormResponseDetailsResponse;

export interface FormResponseListResponse {
  total: number;
  items: FormResponseDetailsResponse[];
}

export type FormSubmissionListResponse = FormResponseListResponse;

export interface FormDashboardStats {
  total_forms: number;
  active_forms?: number;
  published_forms?: number;
  total_distributions?: number;
  total_responses?: number;
  pending_responses?: number;
  pending_review?: number;
  under_review?: number;
  returned?: number;
  returned_responses?: number;
  approved?: number;
  approved_responses?: number;
}

