/**
 * Communication Domain Types
 * Matches backend schemas in app/schemas/communication.py
 */

export type AnnouncementPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';
export type AnnouncementScope = 'ALL' | 'ORGANIZATION' | 'VERTICAL' | 'EVENT' | 'EVENT_TEAM' | 'USER';
export type AnnouncementStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';

export type DirectivePriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type DirectiveScope = 'ALL' | 'VERTICAL' | 'USER';
export type DirectiveStatus = 'DRAFT' | 'ISSUED' | 'SUPERSEDED' | 'ARCHIVED';
export type AcknowledgementStatus = 'PENDING' | 'ACKNOWLEDGED';

export type NotificationType =
  | 'TASK'
  | 'TASK_ASSIGNED'
  | 'TASK_STATUS_CHANGED'
  | 'TASK_ESCALATED'
  | 'REQUIREMENT'
  | 'REQUIREMENT_ASSIGNED'
  | 'MEETING'
  | 'MEETING_INVITATION'
  | 'DIRECTIVE'
  | 'DIRECTIVE_ISSUED'
  | 'ANNOUNCEMENT'
  | 'ANNOUNCEMENT_PUBLISHED'
  | 'TRANSFER'
  | 'FORM'
  | 'FORM_ASSIGNED'
  | 'REPORT'
  | 'REPORT_SUBMITTED'
  | 'REPORT_REVIEWED'
  | 'ISSUE_CREATED'
  | 'ISSUE_ESCALATED'
  | 'ISSUE_RESOLVED'
  | 'SYSTEM'
  | 'SYSTEM_ALERT';


export type NotificationReadStatus = 'UNREAD' | 'READ' | 'DISMISSED';

export type CommunicationType = 'EMAIL' | 'MEETING' | 'OFFICIAL_MESSAGE' | 'NOTICE' | 'CALL' | 'OTHER';
export type CommunicationLogStatus = 'ACTIVE' | 'ARCHIVED';

export interface AnnouncementCreate {
  title: string;
  content: string;
  category?: string;
  priority?: AnnouncementPriority;
  scope?: AnnouncementScope;
  vertical_id?: string;
  event_id?: string;
  target_user_id?: string;
  expires_at?: string;
  publish_now?: boolean;
}

export interface AnnouncementUpdate {
  title?: string;
  content?: string;
  category?: string;
  priority?: AnnouncementPriority;
  scope?: AnnouncementScope;
  vertical_id?: string;
  event_id?: string;
  target_user_id?: string;
  expires_at?: string;
}

export interface AnnouncementResponse {
  id: string;
  title: string;
  content: string;
  category: string;
  priority: AnnouncementPriority;
  scope: AnnouncementScope;
  vertical_id?: string | null;
  vertical_name?: string | null;
  event_id?: string | null;
  event_name?: string | null;
  target_user_id?: string | null;
  target_username?: string | null;
  author_id: string;
  author_username?: string | null;
  status: AnnouncementStatus;
  published_at?: string | null;
  expires_at?: string | null;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnnouncementListResponse {
  total: number;
  items: AnnouncementResponse[];
}

export interface DirectiveCreate {
  title: string;
  instruction: string;
  scope?: DirectiveScope;
  vertical_id?: string;
  target_user_id?: string;
  priority?: DirectivePriority;
  effective_date?: string;
  deadline?: string;
  requires_acknowledgement?: boolean;
  issue_now?: boolean;
}

export interface DirectiveUpdate {
  title?: string;
  instruction?: string;
  priority?: DirectivePriority;
  effective_date?: string;
  deadline?: string;
  requires_acknowledgement?: boolean;
}

export interface DirectiveAcknowledgementResponse {
  id: string;
  directive_id: string;
  user_id: string;
  username?: string | null;
  full_name?: string | null;
  status: AcknowledgementStatus;
  acknowledged_at?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface DirectiveAcknowledgeRequest {
  notes?: string;
}

export interface DirectiveResponse {
  id: string;
  title: string;
  instruction: string;
  issued_by_id: string;
  issued_by_username?: string | null;
  scope: DirectiveScope;
  vertical_id?: string | null;
  vertical_name?: string | null;
  target_user_id?: string | null;
  target_username?: string | null;
  priority: DirectivePriority;
  effective_date: string;
  deadline?: string | null;
  status: DirectiveStatus;
  requires_acknowledgement: boolean;
  created_at: string;
  updated_at: string;
  acknowledgements: DirectiveAcknowledgementResponse[];
  total_acknowledgements: number;
  acknowledged_count: number;
}

export interface DirectiveListResponse {
  total: number;
  items: DirectiveResponse[];
}

export interface NotificationResponse {
  id: string;
  recipient_id: string;
  notification_type: NotificationType;
  title: string;
  message: string;
  related_resource_type?: string | null;
  related_resource_id?: string | null;
  read_status: NotificationReadStatus;
  is_read?: boolean;
  created_at: string;
  read_at?: string | null;
}


export interface NotificationListResponse {
  total: number;
  unread_count: number;
  items: NotificationResponse[];
}

export interface CommunicationLogCreate {
  date_time?: string;
  communication_type?: CommunicationType;
  subject: string;
  sender_info: string;
  recipient_info: string;
  vertical_id?: string;
  event_id?: string;
  related_resource_type?: string;
  related_resource_id?: string;
  reference_link?: string;
  remarks?: string;
}

export interface CommunicationLogUpdate {
  subject?: string;
  sender_info?: string;
  recipient_info?: string;
  vertical_id?: string;
  event_id?: string;
  reference_link?: string;
  remarks?: string;
  status?: CommunicationLogStatus;
}

export interface CommunicationLogResponse {
  id: string;
  date_time: string;
  communication_type: CommunicationType;
  subject: string;
  sender_info: string;
  recipient_info: string;
  vertical_id?: string | null;
  vertical_name?: string | null;
  event_id?: string | null;
  event_name?: string | null;
  related_resource_type?: string | null;
  related_resource_id?: string | null;
  reference_link?: string | null;
  remarks?: string | null;
  created_by_id: string;
  created_by_username?: string | null;
  status: CommunicationLogStatus;
  created_at: string;
  updated_at: string;
}

export interface CommunicationLogListResponse {
  total: number;
  items: CommunicationLogResponse[];
}
