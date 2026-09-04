/**
 * Analytics & Administrative Reporting Domain Types
 * Matches backend schemas in app/schemas/analytics.py
 */

export interface OperationalDashboardResponse {
  generated_at: string;
  active_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  blocked_tasks: number;
  open_issues: number;
  escalated_issues: number;
  upcoming_meetings: number;
  pending_requirements: number;
  event_readiness_avg_pct: number;
  reporting_compliance_pct: number;
  pending_directives: number;
  outstanding_approvals: number;
}

export interface PerformanceIndicatorsResponse {
  generated_at: string;
  task_completion_rate_pct: number;
  overdue_task_rate_pct: number;
  issue_resolution_rate_pct: number;
  requirement_resolution_rate_pct: number;
  meeting_rsvp_rate_pct: number;
  reporting_compliance_rate_pct: number;
  event_readiness_avg_pct: number;
  escalation_rate_pct: number;
}

export interface OperationalAnalyticsResponse {
  vertical_id?: string | null;
  vertical_name?: string | null;
  generated_at: string;

  // Tasks
  tasks_total: number;
  tasks_active: number;
  tasks_completed: number;
  tasks_overdue: number;
  tasks_blocked: number;
  tasks_completion_rate_pct: number;

  // Issues
  issues_total: number;
  issues_open: number;
  issues_escalated: number;
  issues_resolved: number;

  // Requirements
  requirements_total: number;
  requirements_open: number;
  requirements_in_progress: number;
  requirements_completed: number;

  // Events
  events_total: number;
  events_planning: number;
  events_in_progress: number;
  events_completed: number;
  readiness_completed_pct: number;

  // Meetings
  meetings_total: number;
  meetings_scheduled: number;
  meetings_completed: number;
  meetings_rsvp_accepted_pct: number;

  // Reports
  daily_reports_submitted_last_7d: number;
  weekly_reports_submitted_last_4w: number;

  // Forms
  forms_total: number;
  form_submissions_total: number;
  form_submissions_pending: number;
}

export interface AdministrativeAnalyticsResponse {
  generated_at: string;
  organization_name: string;
  total_verticals: number;
  total_users: number;
  active_users: number;

  // System-wide metrics
  global_tasks_total: number;
  global_tasks_completion_rate: number;
  global_overdue_tasks: number;

  global_open_issues: number;
  global_critical_issues: number;

  global_active_events: number;
  global_event_readiness_avg_pct: number;

  global_active_directives: number;
  directive_acknowledgement_compliance_pct: number;

  reporting_compliance_rate_pct: number;
  system_config_keys_count: number;
  audit_events_last_24h: number;
}

export interface MySummaryAnalyticsResponse {
  user_id: string;
  username: string;
  generated_at: string;

  my_tasks_total: number;
  my_tasks_in_progress: number;
  my_tasks_completed: number;
  my_tasks_overdue: number;

  my_assigned_requirements_total: number;
  my_open_requirements: number;

  my_upcoming_meetings_count: number;
  my_pending_rsvps_count: number;

  my_pending_directive_acknowledgements: number;
  my_unread_notifications_count: number;
  my_daily_report_submitted_today: boolean;
}

export interface AdminReportResponse {
  report_name: string;
  generated_at: string;
  total_records: number;
  summary: Record<string, unknown>;
  records: Array<Record<string, unknown>>;
}
