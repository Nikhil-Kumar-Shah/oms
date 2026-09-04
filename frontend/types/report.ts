/**
 * Work Reports (Daily & Weekly) Types
 * Aligned with backend app/schemas/report.py
 */

export type DailyReportStatus = 'DRAFT' | 'SUBMITTED' | 'REVIEWED' | 'RETURNED' | 'FLAGGED';
export type WeeklyReportStatus = 'DRAFT' | 'SUBMITTED' | 'REVIEWED' | 'RETURNED';

export interface DailyReportTaskCreate {
  task_id: string;
  progress_notes?: string;
}

export interface DailyReportTaskResponse {
  task_id: string;
  task_title?: string;
  task_status?: string;
  progress_notes?: string;
}

export interface DailyReportHistoryResponse {
  id: string;
  report_id: string;
  actor_id?: string;
  actor_username?: string;
  action: string;
  comments?: string;
  created_at: string;
}

export interface DailyReportResponse {
  id: string;
  user_id: string;
  author_id?: string;
  user_role?: string;
  username?: string;
  user_full_name?: string;
  vertical_id: string;
  vertical_name?: string;
  report_date: string;
  work_summary: string;
  tasks_completed?: string;
  tasks?: DailyReportTaskResponse[];
  blockers?: string;
  issues?: string;
  next_actions?: string;
  evidence_links?: string;
  status: DailyReportStatus;
  reviewer_id?: string;
  reviewer_username?: string;
  reviewed_by_id?: string;
  reviewed_by_username?: string;
  review_comments?: string;
  history?: DailyReportHistoryResponse[];
  submitted_at?: string;
  reviewed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface DailyReportListResponse {
  total: number;
  items: DailyReportResponse[];
}

export interface DailyReportCreate {
  vertical_id?: string | null;
  report_date?: string | null;
  work_summary: string;
  tasks?: DailyReportTaskCreate[];
  task_ids?: string[];
  assigned_task_id?: string | null;
  tasks_completed?: string | null;
  blockers?: string | null;
  issues?: string | null;
  next_actions?: string | null;
  evidence_links?: string | null;
  submit_now?: boolean;
}

export interface DailyReportUpdate {
  work_summary?: string;
  tasks?: DailyReportTaskCreate[];
  task_ids?: string[];
  tasks_completed?: string | null;
  blockers?: string | null;
  issues?: string | null;
  next_actions?: string | null;
  evidence_links?: string | null;
  submit_now?: boolean;
}

export interface DailyReportReviewRequest {
  status: DailyReportStatus;
  review_comments?: string | null;
}

export interface WeeklyTaskSummary {
  id: string;
  title: string;
  status: string;
  priority: string;
  assigned_to_name?: string;
  deadline?: string;
}

export interface WeeklyIssueSummary {
  id: string;
  title: string;
  status: string;
  sensitivity: string;
}

export interface WeeklyRollupResponse {
  start_date: string;
  end_date: string;
  vertical_id?: string;
  vertical_name?: string;
  user_id?: string;
  user_name?: string;
  daily_reports_count: number;
  daily_reports_submitted: DailyReportResponse[];
  completed_tasks_count: number;
  completed_tasks: WeeklyTaskSummary[];
  incomplete_tasks_count: number;
  incomplete_tasks: WeeklyTaskSummary[];
  blockers_count?: number;
  blockers?: string[];
  major_issues_count?: number;
  major_issues?: WeeklyIssueSummary[];
  achievements?: string[];
  existing_weekly_report?: WeeklyReportResponse | null;
}

export interface WeeklyReportResponse {
  id: string;
  user_id: string;
  author_id?: string;
  user_role?: string;
  username?: string;
  user_full_name?: string;
  vertical_id: string;
  vertical_name?: string;
  week_start_date: string;
  week_end_date: string;
  days_reported_count?: number;
  days_reported?: any[];
  summary: string;
  completed_work?: string;
  outstanding_work?: string;
  tasks_worked_on?: DailyReportTaskResponse[];
  daily_reports?: DailyReportResponse[];
  blockers?: string;
  issues?: string;
  priorities_next_week?: string;
  supervisor_comments?: string;
  reviewer_id?: string;
  reviewer_username?: string;
  reviewed_by_id?: string;
  reviewed_by_username?: string;
  status: WeeklyReportStatus;
  submitted_at?: string;
  reviewed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface WeeklyReportListResponse {
  total: number;
  items: WeeklyReportResponse[];
}

export interface WeeklyReportReviewRequest {
  status: WeeklyReportStatus;
  supervisor_comments?: string | null;
}
