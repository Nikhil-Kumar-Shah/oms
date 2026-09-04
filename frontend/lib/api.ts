/**
 * Centralized Typed API Client
 * Connects directly to the authoritative FastAPI backend.
 */

import { getStoredToken, clearStoredSession } from './auth';
import {
  FAQResponse,
  FAQCreate,
  FAQUpdate,
  FAQListResponse,
  FAQStatus,
} from '@/types/faq';
import { ApiError, ApiDiscoveryResponse, HealthResponse } from '@/types/api';
import { LoginRequest, LoginResponse } from '@/types/auth';
import { UnifiedMyWorkResponse } from '@/types/workspace';
import {
  TaskResponse,
  TaskListResponse,
  TaskCreate,
  TaskUpdate,
  TaskTransitionRequest,
  TaskAssignRequest,
  TaskReassignRequest,
  TaskBlockRequest,
  TaskUnblockRequest,
  TaskEscalateRequest,
  TaskResolveEscalationRequest,
  TaskCommentResponse,
  TaskCommentCreate,
  TaskHistoryResponse,
  TaskPriority,
  TaskType,
} from '@/types/task';
import {
  CalendarResponse,
  CalendarListResponse,
  CalendarCreate,
  CalendarUpdate,
  ActivityCategory,
  CalendarAudience,
} from '@/types/calendar';
import {
  IssueResponse,
  IssueListResponse,
  IssueCreate,
  IssueUpdate,
  IssueTransitionRequest,
  IssueEscalateRequest,
  IssueHistoryResponse,
  IssueCommentCreate,
  IssueCommentResponse,
  IssueSensitivity,
  IssueStatus,
} from '@/types/issue';
import {
  DailyReportResponse,
  DailyReportListResponse,
  DailyReportCreate,
  DailyReportUpdate,
  DailyReportReviewRequest,
  WeeklyReportResponse,
  WeeklyReportListResponse,
  WeeklyReportReviewRequest,
  WeeklyRollupResponse,
  DailyReportStatus,
} from '@/types/report';
import {
  EventResponse,
  EventListResponse,
  EventCreate,
  EventUpdate,
  EventTransitionRequest,
  EventAssignPOCRequest,
  EventMemberResponse,
  EventMemberCreate,
  EventMemberUpdate,
  EventReadinessItemResponse,
  EventReadinessUpdate,
  POCGroupAssignRequest,
  POCGroupResponse,
  EventDashboardResponse,
  EventStatus,
} from '@/types/event';
import {
  EventTeamCreate,
  EventTeamUpdate,
  EventTeamProfileResponse,
  EventTeamListResponse,
} from '@/types/event_team';
import {
  UserProfile,
  UserResponse,
  UserListResponse,
  UserCreateInput,
  UserUpdateInput,
  RoleDetail,
  PermissionSummary,
  AccountStatus,
  UserOperationalProfile,
  UserOperationalProfileUpdate,
} from '@/types/user';
import { VerticalListResponse, Vertical, OrganizationResponse, SelectorOptionItem, SelectorResponse, AudienceResolveRequest, AudienceResolveResponse } from '@/types/organization';
import {
  AnnouncementCreate,
  AnnouncementUpdate,
  AnnouncementResponse,
  AnnouncementListResponse,
  DirectiveCreate,
  DirectiveUpdate,
  DirectiveResponse,
  DirectiveListResponse,
  DirectiveAcknowledgeRequest,
  DirectiveAcknowledgementResponse,
  NotificationResponse,
  NotificationListResponse,
  CommunicationLogCreate,
  CommunicationLogUpdate,
  CommunicationLogResponse,
  CommunicationLogListResponse,
  AnnouncementPriority,
  AnnouncementScope,
  AnnouncementStatus,
  DirectivePriority,
  DirectiveScope,
  DirectiveStatus,
  CommunicationType,
  CommunicationLogStatus,
} from '@/types/communication';
import {
  OwnershipTransferCreate,
  OwnershipTransferReviewRequest,
  OwnershipTransferResponse,
  OwnershipTransferListResponse,
  AccountSuccessionCreate,
  AccountSuccessionPreviewResponse,
  SystemConfigCreate,
  SystemConfigUpdate,
  SystemConfigResponse,
  SystemConfigListResponse,
  AuditLogListResponse,
  TransferResourceType,
  TransferStatus,
} from '@/types/governance';
import {
  ChecklistItemUpdate,
  DistributionSummaryResponse,
  FormChecklistItemResponse,
  FormCreate,
  FormDashboardStats,
  FormDistributeRequest,
  FormDistributionResponse,
  FormListResponse,
  FormResponse,
  FormResponseDetailsResponse,
  FormResponseForwardRequest,
  FormResponseListResponse,
  FormResponseReturnRequest,
  FormResponseReviewRequest,
  FormResponseSaveDraft,
  FormResponseStatus,
  FormResponseSubmit,
  FormReviewerResponse,
  FormStatus,
  FormSubmissionCreate,
  FormSubmissionListResponse,
  FormSubmissionResponse,
  FormSubmissionReviewRequest,
  FormSubmissionStatus,
  FormUpdate,
  FormVersionCreate,
  FormVersionResponse,
  FormWorkflowHistoryResponse,
} from '@/types/form';

import {
  RequirementResponse,
  RequirementListResponse,
  RequirementCreate,
  RequirementUpdate,
  RequirementTransitionRequest,
  RequirementAssignRequest,
  RequirementForwardRequest,
  RequirementEscalateRequest,
  RequirementResolveEscalationRequest,
  RequirementMessage,
  RequirementStatus,
  RequirementPriority,
} from '@/types/requirement';
import {
  MeetingResponse,
  MeetingListResponse,
  MeetingCreate,
  MeetingUpdate,
  MeetingRSVPRequest,
  MeetingActionItemCreate,
  MeetingActionItem,
  MeetingActionConvertToTaskRequest,
  MeetingType,
  MeetingStatus,
} from '@/types/meeting';
import {
  OperationalDashboardResponse,
  PerformanceIndicatorsResponse,
  OperationalAnalyticsResponse,
  AdministrativeAnalyticsResponse,
  MySummaryAnalyticsResponse,
  AdminReportResponse,
} from '@/types/analytics';

export function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL.replace(/\/+$/, '');
  }
  // In browser runtime, default to relative path to leverage Nginx reverse proxy on the same origin
  if (typeof window !== 'undefined') {
    return '/api/v1';
  }
  // In server-side Node.js runtime, connect directly to local backend
  return 'http://127.0.0.1:8000/api/v1';
}

export class ApiException extends Error {
  public code: string;
  public status: number;
  public details?: Record<string, unknown>;

  constructor(status: number, error: ApiError) {
    super(error.message || 'API request failed');
    this.name = 'ApiException';
    this.status = status;
    this.code = error.code || 'UNKNOWN_ERROR';
    this.details = error.details as Record<string, unknown> | undefined;
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
  skipAuth?: boolean;
}

/**
 * Core HTTP Request Dispatcher
 */
async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, skipAuth = false, headers = {}, ...customConfig } = options;

  // Build URL with query params
  const baseUrl = getApiBaseUrl();
  let url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const reqHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(headers as Record<string, string>),
  };

  // Attach Bearer Token if available
  if (!skipAuth) {
    const token = getStoredToken();
    if (token) {
      reqHeaders['Authorization'] = `Bearer ${token}`;
    }
  }

  try {
    const response = await fetch(url, {
      ...customConfig,
      headers: reqHeaders,
    });

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    const isJson = response.headers.get('content-type')?.includes('application/json');
    const data = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      // 401 Unauthorized handling: Invalidate local token
      if (response.status === 401 && !endpoint.includes('/auth/login')) {
        clearStoredSession();
        if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          window.location.href = '/login';
        }
      }

      // Format standard ApiError
      let apiError: ApiError;
      if (typeof data === 'object' && data !== null) {
        if ('error' in data && typeof data.error === 'object' && data.error !== null) {
          apiError = { ...(data.error as ApiError) };
          // Preserve field-level validation errors if present
          if (apiError.details && typeof apiError.details === 'object' && 'validation_errors' in apiError.details) {
            const errList = (apiError.details as { validation_errors?: Array<{ field?: string; message?: string }> }).validation_errors;
            if (Array.isArray(errList) && errList.length > 0) {
              const formatted = errList
                .map((e) => `${(e.field || '').replace(/^body\s*->\s*/, '')}: ${e.message}`)
                .join('; ');
              apiError.message = `Validation error: ${formatted}`;
            }
          }
        } else if ('detail' in data) {
          let detailMsg = '';
          if (Array.isArray(data.detail)) {
            detailMsg = `Validation error: ${data.detail
              .map((d: any) => `${(d.loc || []).filter((x: any) => x !== 'body').join('.')}: ${d.msg}`)
              .join('; ')}`;
          } else if (typeof data.detail === 'string') {
            detailMsg = data.detail;
          } else {
            detailMsg = JSON.stringify(data.detail);
          }
          apiError = {
            code: response.status === 403 ? 'FORBIDDEN' : response.status === 404 ? 'NOT_FOUND' : response.status === 422 ? 'VALIDATION_ERROR' : 'REQUEST_ERROR',
            message: detailMsg,
            details: typeof data.detail === 'object' ? data.detail : undefined,
          };
        } else {
          apiError = {
            code: 'API_ERROR',
            message: data.message || `Request failed with status ${response.status}`,
            details: data,
          };
        }
      } else {
        apiError = {
          code: 'HTTP_ERROR',
          message: data || `HTTP ${response.status} ${response.statusText}`,
        };
      }

      throw new ApiException(response.status, apiError);
    }

    return data as T;
  } catch (error) {
    if (error instanceof ApiException) {
      throw error;
    }

    // Network error or backend offline
    const networkError: ApiError = {
      code: 'NETWORK_ERROR',
      message: error instanceof Error ? error.message : 'Unable to connect to Paradox Sports OMS backend.',
    };
    throw new ApiException(0, networkError);
  }
}

/**
 * Authentication Endpoints API
 */
export const authApi = {
  login: (credentials: LoginRequest): Promise<LoginResponse> =>
    request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
      skipAuth: true,
    }),

  getMe: (): Promise<UserProfile> =>
    request<UserProfile>('/auth/me', {
      method: 'GET',
    }),

  logout: (): Promise<{ message: string }> =>
    request<{ message: string }>('/auth/logout', {
      method: 'POST',
    }),

  changePassword: (data: { current_password: string; new_password: string }): Promise<{ success: boolean; message: string }> =>
    request<{ success: boolean; message: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

/**
 * User Operational Profile API
 */
export const profileApi = {
  getMyProfile: (): Promise<UserOperationalProfile> =>
    request<UserOperationalProfile>('/profiles/me', {
      method: 'GET',
    }),

  updateMyProfile: (data: UserOperationalProfileUpdate): Promise<UserOperationalProfile> =>
    request<UserOperationalProfile>('/profiles/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getUserProfile: (userId: string): Promise<UserOperationalProfile> =>
    request<UserOperationalProfile>(`/profiles/${userId}`, {
      method: 'GET',
    }),

  updateUserProfile: (userId: string, data: UserOperationalProfileUpdate): Promise<UserOperationalProfile> =>
    request<UserOperationalProfile>(`/profiles/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};

/**
 * System & Discovery Endpoints API
 */
export const systemApi = {
  getDiscovery: (): Promise<ApiDiscoveryResponse> =>
    request<ApiDiscoveryResponse>('', {
      method: 'GET',
    }),

  getHealth: (): Promise<HealthResponse> =>
    request<HealthResponse>('/health', {
      method: 'GET',
      skipAuth: true,
    }),
};

/**
 * Unified Workspace API
 */
export const workspaceApi = {
  getMyWork: (): Promise<UnifiedMyWorkResponse> =>
    request<UnifiedMyWorkResponse>('/workspace/my-work', {
      method: 'GET',
    }),
};

/**
 * Master Tasks API
 */
export const tasksApi = {
  list: (params?: {
    vertical_id?: string;
    status?: string;
    status_filter?: string;
    priority?: TaskPriority;
    health?: string;
    task_type?: TaskType;
    assigned_to_id?: string;
    created_by_id?: string;
    scope?: 'all' | 'my_tasks' | 'created_by_me';
    search?: string;
    skip?: number;
    limit?: number;
  }): Promise<TaskListResponse> => {
    const finalParams = { ...params };
    if (finalParams?.status_filter && !finalParams.status) {
      finalParams.status = finalParams.status_filter;
      delete finalParams.status_filter;
    }
    return request<TaskListResponse>('/tasks', {
      method: 'GET',
      params: finalParams,
    });
  },

  getById: (taskId: string): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}`, {
      method: 'GET',
    }),

  create: (data: TaskCreate): Promise<TaskResponse> =>
    request<TaskResponse>('/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createSelfTask: (data: TaskCreate): Promise<TaskResponse> =>
    request<TaskResponse>('/tasks/self', {
      method: 'POST',
      body: JSON.stringify({ ...data, is_self_task: true }),
    }),

  update: (taskId: string, data: TaskUpdate): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  transition: (taskId: string, data: TaskTransitionRequest): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}/transition`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  assign: (taskId: string, data: TaskAssignRequest): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}/assign`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  reassign: (taskId: string, data: TaskReassignRequest): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}/reassign`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  block: (taskId: string, data: TaskBlockRequest): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}/block`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  unblock: (taskId: string, data: TaskUnblockRequest): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}/unblock`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  escalate: (taskId: string, data: TaskEscalateRequest): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}/escalate`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  resolveEscalation: (taskId: string, data: TaskResolveEscalationRequest): Promise<TaskResponse> =>
    request<TaskResponse>(`/tasks/${taskId}/resolve-escalation`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listComments: (taskId: string): Promise<TaskCommentResponse[]> =>
    request<TaskCommentResponse[]>(`/tasks/${taskId}/comments`, {
      method: 'GET',
    }),

  addComment: (taskId: string, data: TaskCommentCreate): Promise<TaskCommentResponse> =>
    request<TaskCommentResponse>(`/tasks/${taskId}/comments`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listHistory: (taskId: string): Promise<TaskHistoryResponse[]> =>
    request<TaskHistoryResponse[]>(`/tasks/${taskId}/history`, {
      method: 'GET',
    }),
};

/**
 * Master Calendar API
 */
export const calendarApi = {
  list: (params?: {
    view?: 'personal' | 'master';
    start_date?: string;
    end_date?: string;
    category?: ActivityCategory;
    priority?: string;
    status?: string;
    audience?: CalendarAudience;
    vertical_id?: string;
    skip?: number;
    limit?: number;
  }): Promise<CalendarListResponse> =>
    request<CalendarListResponse>('/calendar', {
      method: 'GET',
      params,
    }),

  listPersonal: (params?: {
    start_date?: string;
    end_date?: string;
    category?: ActivityCategory;
    priority?: string;
    status?: string;
    vertical_id?: string;
    skip?: number;
    limit?: number;
  }): Promise<CalendarListResponse> =>
    request<CalendarListResponse>('/calendar/personal', {
      method: 'GET',
      params,
    }),

  listMaster: (params?: {
    start_date?: string;
    end_date?: string;
    category?: ActivityCategory;
    priority?: string;
    status?: string;
    vertical_id?: string;
    skip?: number;
    limit?: number;
  }): Promise<CalendarListResponse> =>
    request<CalendarListResponse>('/calendar/master', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<CalendarResponse> =>
    request<CalendarResponse>(`/calendar/${id}`, {
      method: 'GET',
    }),

  create: (data: CalendarCreate): Promise<CalendarResponse> =>
    request<CalendarResponse>('/calendar', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: CalendarUpdate): Promise<CalendarResponse> =>
    request<CalendarResponse>(`/calendar/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: (id: string): Promise<{ success: boolean; message: string }> =>
    request<{ success: boolean; message: string }>(`/calendar/${id}`, {
      method: 'DELETE',
    }),

  executeAction: (id: string, payload: { action: string; remarks?: string }): Promise<CalendarResponse> =>
    request<CalendarResponse>(`/calendar/${id}/actions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  reschedule: (
    id: string,
    payload: {
      new_date: string;
      new_start_time?: string;
      new_end_time?: string;
      reason?: string;
    }
  ): Promise<CalendarResponse> =>
    request<CalendarResponse>(`/calendar/${id}/reschedule`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

/**
 * Issues & Escalations API
 */
export const issuesApi = {
  list: (params?: {
    vertical_id?: string;
    status?: IssueStatus;
    sensitivity?: IssueSensitivity;
    assigned_to_id?: string;
    search?: string;
    skip?: number;
    limit?: number;
  }): Promise<IssueListResponse> =>
    request<IssueListResponse>('/issues', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<IssueResponse> =>
    request<IssueResponse>(`/issues/${id}`, {
      method: 'GET',
    }),

  create: (data: IssueCreate): Promise<IssueResponse> =>
    request<IssueResponse>('/issues', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: IssueUpdate): Promise<IssueResponse> =>
    request<IssueResponse>(`/issues/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  transition: (id: string, data: IssueTransitionRequest): Promise<IssueResponse> =>
    request<IssueResponse>(`/issues/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  escalate: (id: string, data: IssueEscalateRequest): Promise<IssueResponse> =>
    request<IssueResponse>(`/issues/${id}/escalate`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listHistory: (id: string): Promise<IssueHistoryResponse[]> =>
    request<IssueHistoryResponse[]>(`/issues/${id}/history`, {
      method: 'GET',
    }),

  listComments: (id: string): Promise<IssueCommentResponse[]> =>
    request<IssueCommentResponse[]>(`/issues/${id}/comments`, {
      method: 'GET',
    }),

  addComment: (id: string, data: IssueCommentCreate): Promise<IssueCommentResponse> =>
    request<IssueCommentResponse>(`/issues/${id}/comments`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

/**
 * Work Reports API
 */
export const reportsApi = {
  submitDaily: (data: DailyReportCreate): Promise<DailyReportResponse> =>
    request<DailyReportResponse>('/reports/daily', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getMyDaily: (params?: {
    report_date?: string;
    status?: DailyReportStatus;
    skip?: number;
    limit?: number;
  }): Promise<DailyReportListResponse> =>
    request<DailyReportListResponse>('/reports/daily', {
      method: 'GET',
      params,
    }),

  getVerticalDaily: (
    verticalId: string,
    params?: {
      status?: DailyReportStatus;
      skip?: number;
      limit?: number;
    }
  ): Promise<DailyReportListResponse> =>
    request<DailyReportListResponse>('/reports/daily', {
      method: 'GET',
      params: { vertical_id: verticalId, ...params },
    }),

  getDailyById: (id: string): Promise<DailyReportResponse> =>
    request<DailyReportResponse>(`/reports/daily/${id}`, {
      method: 'GET',
    }),

  resubmitDaily: (id: string, data: DailyReportUpdate): Promise<DailyReportResponse> =>
    request<DailyReportResponse>(`/reports/daily/${id}/resubmit`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  reviewDaily: (id: string, data: DailyReportReviewRequest): Promise<DailyReportResponse> =>
    request<DailyReportResponse>(`/reports/daily/${id}/review`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getReviewQueue: (params?: {
    skip?: number;
    limit?: number;
  }): Promise<DailyReportListResponse> =>
    request<DailyReportListResponse>('/reports/review-queue', {
      method: 'GET',
      params,
    }),

  getCurrentWeekly: (params?: {
    user_id?: string;
    week_start?: string;
  }): Promise<WeeklyReportResponse> =>
    request<WeeklyReportResponse>('/reports/weekly/current', {
      method: 'GET',
      params,
    }),

  listWeekly: (params?: {
    user_id?: string;
    vertical_id?: string;
    status?: string;
    skip?: number;
    limit?: number;
  }): Promise<WeeklyReportListResponse> =>
    request<WeeklyReportListResponse>('/reports/weekly', {
      method: 'GET',
      params,
    }),

  reviewWeekly: (id: string, data: WeeklyReportReviewRequest): Promise<WeeklyReportResponse> =>
    request<WeeklyReportResponse>(`/reports/weekly/${id}/review`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getWeeklyRollup: (params: {
    start_date: string;
    end_date: string;
    vertical_id?: string;
    user_id?: string;
  }): Promise<WeeklyRollupResponse> =>
    request<WeeklyRollupResponse>('/reports/weekly/rollup', {
      method: 'GET',
      params,
    }),
};

/**
 * Organization & Verticals Lookup API
 */
export const organizationApi = {
  get: (): Promise<OrganizationResponse> =>
    request<OrganizationResponse>('/organization', {
      method: 'GET',
    }),

  getOrganization: (): Promise<OrganizationResponse> =>
    request<OrganizationResponse>('/organization', {
      method: 'GET',
    }),

  listVerticals: (params?: { status?: string } | string): Promise<VerticalListResponse> => {
    const status_filter = typeof params === 'string' ? params : params?.status;
    return request<VerticalListResponse>('/organization/verticals', {
      method: 'GET',
      params: status_filter ? { status_filter } : undefined,
    });
  },

  getVertical: (verticalId: string): Promise<Vertical> =>
    request<Vertical>(`/organization/verticals/${verticalId}`, {
      method: 'GET',
    }),

  searchUsers: (params?: {
    search?: string;
    vertical_id?: string;
    role_filter?: string;
    status_filter?: string;
    limit?: number;
    offset?: number;
  }): Promise<UserListResponse> =>
    request<UserListResponse>('/organization/users', {
      method: 'GET',
      params: { limit: 100, ...params },
    }),

  getSelectorOptions: (params: {
    selection_type?: string;
    search?: string;
    vertical_id?: string;
    role_filter?: string;
    event_id?: string;
    usage?: 'assignment' | 'audience' | 'general';
    limit?: number;
    offset?: number;
  }): Promise<SelectorResponse> =>
    request<SelectorResponse>('/organization/selector-options', {
      method: 'GET',
      params,
    }),

  resolveAudience: (data: AudienceResolveRequest): Promise<AudienceResolveResponse> =>
    request<AudienceResolveResponse>('/organization/resolve-audience', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

/**
 * Users Lookup API (for assignment selectors)
 */
export const usersApi = {
  listUsers: (params?: {
    role_name?: string;
    account_status?: string;
    search?: string;
    skip?: number;
    limit?: number;
  }): Promise<UserListResponse> =>
    request<UserListResponse>('/admin/users', {
      method: 'GET',
      params: { limit: 100, ...params },
    }),

  resolveAudience: (data: AudienceResolveRequest): Promise<AudienceResolveResponse> =>
    request<AudienceResolveResponse>('/users/resolve-audience', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

/**
 * Events & Coordination API
 */
export const eventsApi = {
  list: (params?: {
    vertical_id?: string;
    status?: EventStatus;
    limit?: number;
    offset?: number;
  }): Promise<EventListResponse> =>
    request<EventListResponse>('/events', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<EventResponse> =>
    request<EventResponse>(`/events/${id}`, {
      method: 'GET',
    }),

  create: (data: EventCreate): Promise<EventResponse> =>
    request<EventResponse>('/events', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: EventUpdate): Promise<EventResponse> =>
    request<EventResponse>(`/events/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  transition: (id: string, data: EventTransitionRequest): Promise<EventResponse> =>
    request<EventResponse>(`/events/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  assignPOC: (id: string, data: EventAssignPOCRequest): Promise<EventResponse> =>
    request<EventResponse>(`/events/${id}/poc`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  assignPOCGroup: (id: string, data: POCGroupAssignRequest): Promise<POCGroupResponse> =>
    request<POCGroupResponse>(`/events/${id}/poc-group`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getPOCGroup: (id: string): Promise<POCGroupResponse> =>
    request<POCGroupResponse>(`/events/${id}/poc-group`, {
      method: 'GET',
    }),

  listTeam: (id: string): Promise<EventMemberResponse[]> =>
    request<EventMemberResponse[]>(`/events/${id}/team`, {
      method: 'GET',
    }),

  addTeamMember: (id: string, data: EventMemberCreate): Promise<EventMemberResponse> =>
    request<EventMemberResponse>(`/events/${id}/team`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateTeamMember: (id: string, memberId: string, data: EventMemberUpdate): Promise<EventMemberResponse> =>
    request<EventMemberResponse>(`/events/${id}/team/${memberId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  listReadiness: (id: string): Promise<EventReadinessItemResponse[]> =>
    request<EventReadinessItemResponse[]>(`/events/${id}/readiness`, {
      method: 'GET',
    }),

  updateReadiness: (id: string, itemId: string, data: EventReadinessUpdate): Promise<EventReadinessItemResponse> =>
    request<EventReadinessItemResponse>(`/events/${id}/readiness/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  getDashboard: (id: string): Promise<EventDashboardResponse> =>
    request<EventDashboardResponse>(`/events/${id}/dashboard`, {
      method: 'GET',
    }),
};

/**
 * Event Teams API (Profile & Operational Boundaries)
 */
export const eventTeamsApi = {
  getMyTeam: (): Promise<EventTeamProfileResponse> =>
    request<EventTeamProfileResponse>('/event-teams/me', {
      method: 'GET',
    }),

  updateMyTeam: (data: EventTeamUpdate): Promise<EventTeamProfileResponse> =>
    request<EventTeamProfileResponse>('/event-teams/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getById: (teamId: string): Promise<EventTeamProfileResponse> =>
    request<EventTeamProfileResponse>(`/event-teams/${teamId}`, {
      method: 'GET',
    }),

  update: (teamId: string, data: EventTeamUpdate): Promise<EventTeamProfileResponse> =>
    request<EventTeamProfileResponse>(`/event-teams/${teamId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  list: (params?: { event_id?: string; limit?: number; offset?: number }): Promise<EventTeamListResponse> =>
    request<EventTeamListResponse>('/event-teams', {
      method: 'GET',
      params,
    }),

  create: (data: EventTeamCreate): Promise<EventTeamProfileResponse> =>
    request<EventTeamProfileResponse>('/event-teams', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createCredentials: (data: {
    username: string;
    password: string;
    email?: string;
    team_name?: string;
  }): Promise<{ id: string; username: string; email?: string; account_status: string }> =>
    request('/event-teams/credentials', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getUnactivatedAccounts: (): Promise<
    Array<{
      id: string;
      username: string;
      email?: string;
      full_name?: string;
      account_status: string;
      created_at: string;
    }>
  > =>
    request('/event-teams/unactivated', {
      method: 'GET',
    }),

  activate: (data: {
    team_name: string;
    head_name: string;
    head_phone: string;
    head_email: string;
    user_id: string;
    head_poc_id: string;
    additional_poc_ids: string[];
    event_id?: string;
    notes?: string;
  }): Promise<EventTeamProfileResponse> =>
    request<EventTeamProfileResponse>('/event-teams/activate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

/**
 * Announcements API
 */
export const announcementsApi = {
  list: (params?: {
    scope?: AnnouncementScope;
    status?: AnnouncementStatus;
    vertical_id?: string;
    event_id?: string;
    priority?: AnnouncementPriority;
    limit?: number;
    offset?: number;
  }): Promise<AnnouncementListResponse> =>
    request<AnnouncementListResponse>('/announcements', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<AnnouncementResponse> =>
    request<AnnouncementResponse>(`/announcements/${id}`, {
      method: 'GET',
    }),

  create: (data: AnnouncementCreate): Promise<AnnouncementResponse> =>
    request<AnnouncementResponse>('/announcements', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: AnnouncementUpdate): Promise<AnnouncementResponse> =>
    request<AnnouncementResponse>(`/announcements/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  publish: (id: string): Promise<AnnouncementResponse> =>
    request<AnnouncementResponse>(`/announcements/${id}/publish`, {
      method: 'POST',
    }),

  archive: (id: string): Promise<AnnouncementResponse> =>
    request<AnnouncementResponse>(`/announcements/${id}/archive`, {
      method: 'POST',
    }),
};

/**
 * Directives API
 */
export const directivesApi = {
  list: (params?: {
    scope?: DirectiveScope;
    status?: DirectiveStatus;
    vertical_id?: string;
    priority?: DirectivePriority;
    limit?: number;
    offset?: number;
  }): Promise<DirectiveListResponse> =>
    request<DirectiveListResponse>('/directives', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<DirectiveResponse> =>
    request<DirectiveResponse>(`/directives/${id}`, {
      method: 'GET',
    }),

  create: (data: DirectiveCreate): Promise<DirectiveResponse> =>
    request<DirectiveResponse>('/directives', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: DirectiveUpdate): Promise<DirectiveResponse> =>
    request<DirectiveResponse>(`/directives/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  issue: (id: string): Promise<DirectiveResponse> =>
    request<DirectiveResponse>(`/directives/${id}/issue`, {
      method: 'POST',
    }),

  acknowledge: (id: string, data?: DirectiveAcknowledgeRequest): Promise<DirectiveAcknowledgementResponse> =>
    request<DirectiveAcknowledgementResponse>(`/directives/${id}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),
};

/**
 * Notifications API
 */
export const notificationsApi = {
  list: (params?: {
    read_status?: string;
    notification_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<NotificationListResponse> =>
    request<NotificationListResponse>('/notifications', {
      method: 'GET',
      params,
    }),

  getUnreadCount: (): Promise<{ unread_count: number }> =>
    request<{ unread_count: number }>('/notifications/unread-count', {
      method: 'GET',
    }),

  markRead: (id: string): Promise<NotificationResponse> =>
    request<NotificationResponse>(`/notifications/${id}/read`, {
      method: 'PATCH',
    }),

  markAllRead: (): Promise<{ marked_read_count: number }> =>
    request<{ marked_read_count: number }>('/notifications/read-all', {
      method: 'POST',
    }),

  dismiss: (id: string): Promise<NotificationResponse> =>
    request<NotificationResponse>(`/notifications/${id}/dismiss`, {
      method: 'POST',
    }),
};


/**
 * Communication Tracker API
 */
export const communicationsApi = {
  list: (params?: {
    vertical_id?: string;
    event_id?: string;
    communication_type?: CommunicationType;
    status?: CommunicationLogStatus;
    limit?: number;
    offset?: number;
  }): Promise<CommunicationLogListResponse> =>
    request<CommunicationLogListResponse>('/communications', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<CommunicationLogResponse> =>
    request<CommunicationLogResponse>(`/communications/${id}`, {
      method: 'GET',
    }),

  create: (data: CommunicationLogCreate): Promise<CommunicationLogResponse> =>
    request<CommunicationLogResponse>('/communications', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: CommunicationLogUpdate): Promise<CommunicationLogResponse> =>
    request<CommunicationLogResponse>(`/communications/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
};

/**
 * Ownership Transfers API
 */
export const transfersApi = {
  list: (params?: {
    resource_type?: TransferResourceType;
    status?: TransferStatus;
    limit?: number;
    offset?: number;
  }): Promise<OwnershipTransferListResponse> =>
    request<OwnershipTransferListResponse>('/transfers', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<OwnershipTransferResponse> =>
    request<OwnershipTransferResponse>(`/transfers/${id}`, {
      method: 'GET',
    }),

  request: (data: OwnershipTransferCreate): Promise<OwnershipTransferResponse> =>
    request<OwnershipTransferResponse>('/transfers', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  previewSuccession: (previousUserId: string, successorUserId: string): Promise<AccountSuccessionPreviewResponse> =>
    request<AccountSuccessionPreviewResponse>('/transfers/succession-preview', {
      method: 'GET',
      params: { previous_user_id: previousUserId, successor_user_id: successorUserId },
    }),

  initiateSuccession: (data: AccountSuccessionCreate): Promise<OwnershipTransferResponse> =>
    request<OwnershipTransferResponse>('/transfers/succession', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  review: (id: string, data: OwnershipTransferReviewRequest): Promise<OwnershipTransferResponse> =>
    request<OwnershipTransferResponse>(`/transfers/${id}/review`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

/**
 * Audit Center API
 */
export const auditApi = {
  listLogs: (params?: {
    limit?: number;
    offset?: number;
    action?: string;
    actor_id?: string;
    resource_type?: string;
    outcome?: string;
  }): Promise<AuditLogListResponse> =>
    request<AuditLogListResponse>('/admin/audit-logs', {
      method: 'GET',
      params,
    }),
};

/**
 * System Configuration API
 */
export const configApi = {
  list: (params?: { is_active?: boolean }): Promise<SystemConfigListResponse> =>
    request<SystemConfigListResponse>('/admin/config', {
      method: 'GET',
      params,
    }),

  listConfigs: (params?: { is_active?: boolean }): Promise<SystemConfigListResponse> =>
    request<SystemConfigListResponse>('/admin/config', {
      method: 'GET',
      params,
    }),

  getByKey: (key: string): Promise<SystemConfigResponse> =>
    request<SystemConfigResponse>(`/admin/config/${key}`, {
      method: 'GET',
    }),

  create: (data: SystemConfigCreate): Promise<SystemConfigResponse> =>
    request<SystemConfigResponse>('/admin/config', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createConfig: (data: SystemConfigCreate): Promise<SystemConfigResponse> =>
    request<SystemConfigResponse>('/admin/config', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (key: string, data: SystemConfigUpdate): Promise<SystemConfigResponse> =>
    request<SystemConfigResponse>(`/admin/config/${key}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  updateConfig: (key: string, data: SystemConfigUpdate): Promise<SystemConfigResponse> =>
    request<SystemConfigResponse>(`/admin/config/${key}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
};

/**
 * Administration & Governance API
 */
export const adminApi = {
  // User Management
  listUsers: (params?: {
    status_filter?: AccountStatus;
    search?: string;
    role_filter?: string;
    vertical_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<UserListResponse> =>
    request<UserListResponse>('/admin/users', {
      method: 'GET',
      params,
    }),

  getUser: (id: string): Promise<UserResponse> =>
    request<UserResponse>(`/admin/users/${id}`, {
      method: 'GET',
    }),

  createUser: (data: UserCreateInput): Promise<UserResponse> =>
    request<UserResponse>('/admin/users', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateUser: (id: string, data: UserUpdateInput): Promise<UserResponse> =>
    request<UserResponse>(`/admin/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  setUserStatus: (id: string, status: AccountStatus): Promise<UserResponse> =>
    request<UserResponse>(`/admin/users/${id}/status`, {
      method: 'POST',
      params: { new_status: status },
    }),

  assignRoles: (id: string, roleIds: string[]): Promise<UserResponse> =>
    request<UserResponse>(`/admin/users/${id}/roles`, {
      method: 'POST',
      body: JSON.stringify({ role_ids: roleIds }),
    }),

  assignVerticals: (id: string, assignments: { vertical_id: string; is_primary: boolean }[]): Promise<UserResponse> =>
    request<UserResponse>(`/admin/users/${id}/verticals`, {
      method: 'POST',
      body: JSON.stringify({ assignments }),
    }),

  // Roles & Permissions
  listRoles: (): Promise<RoleDetail[]> =>
    request<RoleDetail[]>('/admin/roles', {
      method: 'GET',
    }),

  listPermissions: (): Promise<PermissionSummary[]> =>
    request<PermissionSummary[]>('/admin/permissions', {
      method: 'GET',
    }),

  // Verticals
  listVerticals: (status?: string): Promise<Vertical[]> =>
    request<Vertical[]>('/admin/verticals', {
      method: 'GET',
      params: status ? { status_filter: status } : undefined,
    }),

  createVertical: (data: { name: string; slug?: string; description?: string; lead_coordinator_id?: string }): Promise<Vertical> =>
    request<Vertical>('/admin/verticals', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateVertical: (id: string, data: { name?: string; description?: string; status?: string; lead_coordinator_id?: string }): Promise<Vertical> =>
    request<Vertical>(`/admin/verticals/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  disableVertical: (id: string): Promise<Vertical> =>
    request<Vertical>(`/admin/verticals/${id}/disable`, {
      method: 'POST',
    }),

  archiveVertical: (id: string): Promise<Vertical> =>
    request<Vertical>(`/admin/verticals/${id}/archive`, {
      method: 'POST',
    }),

  // Password Management
  resetPassword: (userId: string, newPassword: string): Promise<{ success: boolean; message: string }> =>
    request<{ success: boolean; message: string }>(`/admin/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword }),
    }),

  // System Health
  getHealth: (): Promise<{
    status: string;
    latency_ms?: number;
    application?: { status: string; app_name: string; version: string; environment: string; timestamp: string };
    database?: { status: string; latency_ms?: number; pool?: Record<string, unknown>; engine?: string };
    timestamp?: string;
  }> =>
    request('/admin/health', {
      method: 'GET',
    }),
};

/**
 * Dynamic Forms & Workflow API
 */
export const formsApi = {
  getStats: (): Promise<FormDashboardStats> =>
    request<FormDashboardStats>('/forms/dashboard-stats', {
      method: 'GET',
    }),

  list: (params?: {
    vertical_id?: string;
    event_id?: string;
    status?: FormStatus;
    category?: string;
    workspace_tab?: string;
    limit?: number;
    offset?: number;
  }): Promise<FormListResponse> =>

    request<FormListResponse>('/forms', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<FormResponse> =>
    request<FormResponse>(`/forms/${id}`, {
      method: 'GET',
    }),

  create: (data: FormCreate): Promise<FormResponse> =>
    request<FormResponse>('/forms', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: FormUpdate): Promise<FormResponse> =>
    request<FormResponse>(`/forms/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  createVersion: (formId: string, data: FormVersionCreate): Promise<FormVersionResponse> =>
    request<FormVersionResponse>(`/forms/${formId}/versions`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  publishVersion: (formId: string, versionNumber: number): Promise<FormVersionResponse> =>
    request<FormVersionResponse>(`/forms/${formId}/publish?version_number=${versionNumber}`, {
      method: 'POST',
    }),

  distribute: (formId: string, data: FormDistributeRequest): Promise<FormDistributionResponse> =>
    request<FormDistributionResponse>(`/forms/${formId}/distribute`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getDistributionSummary: (formId: string): Promise<DistributionSummaryResponse> =>
    request<DistributionSummaryResponse>(`/forms/${formId}/distribution-summary`, {
      method: 'GET',
    }),

  listResponses: (params?: {
    form_id?: string;
    distribution_id?: string;
    recipient_id?: string;
    submitter_id?: string;
    status?: FormResponseStatus;
    workspace_tab?: string;
    limit?: number;
    offset?: number;
  }): Promise<FormResponseListResponse> =>
    request<FormResponseListResponse>('/form-responses', {
      method: 'GET',
      params,
    }),

  listSubmissions: (formId: string, params?: { status?: FormResponseStatus; limit?: number; offset?: number }): Promise<FormResponseListResponse> =>
    request<FormResponseListResponse>('/form-responses', {
      method: 'GET',
      params: { form_id: formId, ...params },
    }),

  listAllSubmissions: (params?: {
    form_id?: string;
    submitter_id?: string;
    status?: FormResponseStatus;
    workspace_tab?: string;
    limit?: number;
    offset?: number;
  }): Promise<FormResponseListResponse> =>
    request<FormResponseListResponse>('/form-responses', {
      method: 'GET',
      params,
    }),

  getResponse: (responseId: string): Promise<FormResponseDetailsResponse> =>
    request<FormResponseDetailsResponse>(`/form-responses/${responseId}`, {
      method: 'GET',
    }),

  getSubmission: (submissionId: string): Promise<FormResponseDetailsResponse> =>
    request<FormResponseDetailsResponse>(`/form-responses/${submissionId}`, {
      method: 'GET',
    }),

  saveDraft: (responseId: string, data: { response_data: Record<string, unknown> }): Promise<FormResponseDetailsResponse> =>
    request<FormResponseDetailsResponse>(`/form-responses/${responseId}/draft`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submitResponse: (responseId: string, data: { response_data: Record<string, unknown> }): Promise<FormResponseDetailsResponse> =>
    request<FormResponseDetailsResponse>(`/form-responses/${responseId}/submit`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submit: (formId: string, data: { submission_data?: Record<string, unknown>; response_data?: Record<string, unknown> }): Promise<FormResponseDetailsResponse> =>
    request<FormResponseDetailsResponse>(`/forms/${formId}/submissions`, {
      method: 'POST',
      body: JSON.stringify({ response_data: data.response_data || data.submission_data || {} }),
    }),

  reviewResponse: (responseId: string, data: { action: string; return_reason?: string; reviewer_remarks?: string; execute_transformation?: boolean }): Promise<FormResponseDetailsResponse> =>
    request<FormResponseDetailsResponse>(`/form-responses/${responseId}/review`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  returnResponse: (responseId: string, data: { return_reason: string; reviewer_remarks?: string }): Promise<FormResponseDetailsResponse> =>
    request<FormResponseDetailsResponse>(`/form-responses/${responseId}/return`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  forwardResponse: (responseId: string, data: { target_user_id: string; message: string; role_label?: string; phase_number?: number }): Promise<FormResponseDetailsResponse> =>
    request<FormResponseDetailsResponse>(`/form-responses/${responseId}/forward`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateChecklistItem: (itemId: string, data: { status: string; remarks?: string; evidence_link?: string }): Promise<FormChecklistItemResponse> =>
    request<FormChecklistItemResponse>(`/form-responses/checklist/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
};


/**
 * Analytics API
 */
export const analyticsApi = {
  getOperationalDashboard: (): Promise<OperationalDashboardResponse> =>
    request<OperationalDashboardResponse>('/analytics/dashboard', {
      method: 'GET',
    }),

  getPerformanceIndicators: (): Promise<PerformanceIndicatorsResponse> =>
    request<PerformanceIndicatorsResponse>('/analytics/indicators', {
      method: 'GET',
    }),

  getOperationalAnalytics: (params?: { vertical_id?: string }): Promise<OperationalAnalyticsResponse> =>
    request<OperationalAnalyticsResponse>('/analytics/operational', {
      method: 'GET',
      params,
    }),

  getAdministrativeAnalytics: (): Promise<AdministrativeAnalyticsResponse> =>
    request<AdministrativeAnalyticsResponse>('/analytics/administrative', {
      method: 'GET',
    }),

  getMySummary: (): Promise<MySummaryAnalyticsResponse> =>
    request<MySummaryAnalyticsResponse>('/analytics/my-summary', {
      method: 'GET',
    }),
};

/**
 * Cross-Vertical Requirements API
 */
export const requirementsApi = {
  list: (params?: {
    requesting_vertical_id?: string;
    target_vertical_id?: string;
    status?: RequirementStatus;
    priority?: RequirementPriority;
    assignee_id?: string;
    is_escalated?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<RequirementListResponse> =>
    request<RequirementListResponse>('/requirements', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<RequirementResponse> =>
    request<RequirementResponse>(`/requirements/${id}`, {
      method: 'GET',
    }),

  create: (data: RequirementCreate): Promise<RequirementResponse> =>
    request<RequirementResponse>('/requirements', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: RequirementUpdate): Promise<RequirementResponse> =>
    request<RequirementResponse>(`/requirements/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  assign: (id: string, data: RequirementAssignRequest): Promise<RequirementResponse> =>
    request<RequirementResponse>(`/requirements/${id}/assign`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  transition: (id: string, data: RequirementTransitionRequest): Promise<RequirementResponse> =>
    request<RequirementResponse>(`/requirements/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  forward: (id: string, data: RequirementForwardRequest): Promise<RequirementResponse> =>
    request<RequirementResponse>(`/requirements/${id}/forward`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  escalate: (id: string, data: RequirementEscalateRequest): Promise<RequirementResponse> =>
    request<RequirementResponse>(`/requirements/${id}/escalate`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  resolveEscalation: (id: string, data: RequirementResolveEscalationRequest): Promise<RequirementResponse> =>
    request<RequirementResponse>(`/requirements/${id}/escalate/resolve`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listMessages: (id: string): Promise<RequirementMessage[]> =>
    request<RequirementMessage[]>(`/requirements/${id}/messages`, {
      method: 'GET',
    }),

  postMessage: (id: string, content: string): Promise<RequirementMessage> =>
    request<RequirementMessage>(`/requirements/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),
};

/**
 * Meetings & Actions Management API
 */
export const meetingsApi = {
  list: (params?: {
    vertical_id?: string;
    event_id?: string;
    meeting_type?: MeetingType;
    status?: MeetingStatus;
    limit?: number;
    offset?: number;
  }): Promise<MeetingListResponse> =>
    request<MeetingListResponse>('/meetings', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<MeetingResponse> =>
    request<MeetingResponse>(`/meetings/${id}`, {
      method: 'GET',
    }),

  create: (data: MeetingCreate): Promise<MeetingResponse> =>
    request<MeetingResponse>('/meetings', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: MeetingUpdate): Promise<MeetingResponse> =>
    request<MeetingResponse>(`/meetings/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  rsvp: (id: string, data: MeetingRSVPRequest): Promise<MeetingResponse> =>
    request<MeetingResponse>(`/meetings/${id}/rsvp`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  addActionItem: (id: string, data: MeetingActionItemCreate): Promise<MeetingActionItem> =>
    request<MeetingActionItem>(`/meetings/${id}/actions`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  convertActionToTask: (actionId: string, data?: MeetingActionConvertToTaskRequest): Promise<TaskResponse> =>
    request<TaskResponse>(`/meetings/actions/${actionId}/convert-to-task`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),
};

/**
 * Administrative Reporting API
 */
export const adminReportsApi = {
  getTaskReport: (params?: { vertical_id?: string }): Promise<AdminReportResponse> =>
    request<AdminReportResponse>('/admin/reports/tasks', {
      method: 'GET',
      params,
    }),

  getEventReport: (): Promise<AdminReportResponse> =>
    request<AdminReportResponse>('/admin/reports/events', {
      method: 'GET',
    }),

  getIssueReport: (): Promise<AdminReportResponse> =>
    request<AdminReportResponse>('/admin/reports/issues', {
      method: 'GET',
    }),

  getMeetingReport: (): Promise<AdminReportResponse> =>
    request<AdminReportResponse>('/admin/reports/meetings', {
      method: 'GET',
    }),

  getComplianceReport: (params?: { days?: number }): Promise<AdminReportResponse> =>
    request<AdminReportResponse>('/admin/reports/compliance', {
      method: 'GET',
      params,
    }),
};

/**
 * FAQ & Operational Knowledge Base API
 */
export const faqsApi = {


  list: (params?: { category?: string; status?: FAQStatus; search?: string; limit?: number; offset?: number }): Promise<FAQListResponse> =>
    request<FAQListResponse>('/faqs', {
      method: 'GET',
      params,
    }),

  getById: (id: string): Promise<FAQResponse> =>
    request<FAQResponse>(`/faqs/${id}`, {
      method: 'GET',
    }),

  create: (data: FAQCreate): Promise<FAQResponse> =>
    request<FAQResponse>('/faqs', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: FAQUpdate): Promise<FAQResponse> =>
    request<FAQResponse>(`/faqs/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: (id: string): Promise<void> =>
    request<void>(`/faqs/${id}`, {
      method: 'DELETE',
    }),
};

export const api = {
  get: <T>(url: string, options?: RequestOptions) => request<T>(url, { ...options, method: 'GET' }),

  post: <T>(url: string, body?: unknown, options?: RequestOptions) =>
    request<T>(url, { ...options, method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(url: string, body?: unknown, options?: RequestOptions) =>
    request<T>(url, { ...options, method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(url: string, body?: unknown, options?: RequestOptions) =>
    request<T>(url, { ...options, method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(url: string, options?: RequestOptions) => request<T>(url, { ...options, method: 'DELETE' }),
};

