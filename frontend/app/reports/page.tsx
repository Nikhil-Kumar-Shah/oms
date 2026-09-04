'use client';

/**
 * Operational Work Reports Workspace (/reports)
 * Phase: Clean Hierarchical Report Browser & Viewer
 * Flow: Vertical → Role → User → Week → Day → Complete Daily Report
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { StatusBadge } from '@/components/common/StatusBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { Badge } from '@/components/ui/Badge';
import { useAuth } from '@/hooks/useAuth';
import { reportsApi, tasksApi, organizationApi } from '@/lib/api';
import {
  DailyReportResponse,
  DailyReportCreate,
  DailyReportUpdate,
  DailyReportTaskCreate,
  WeeklyReportResponse,
} from '@/types/report';
import { Vertical } from '@/types/organization';
import { TaskResponse } from '@/types/task';
import { formatAuditDateTime } from '@/lib/utils';
import {
  FileText,
  Plus,
  Calendar,
  CheckCircle2,
  User as UserIcon,
  AlertTriangle,
  Link as LinkIcon,
  ShieldCheck,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  RotateCcw,
  Check,
  Search,
  Clock,
  CheckSquare,
  Eye,
  Layers,
  ArrowRight,
} from 'lucide-react';

/**
 * Safely format literal 'YYYY-MM-DD' without local timezone day-shift corruption.
 */
function formatReportDate(dateStr: string): string {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length === 3) {
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const d = new Date(year, month, day);
    return d.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }
  return dateStr;
}

/**
 * Returns Monday date string 'YYYY-MM-DD' for a given week offset (0 = current week, 1 = prev week...).
 */
function getMondayOfWeek(offsetWeeks: number = 0): string {
  const now = new Date();
  const day = now.getDay();
  const diffToMonday = (day + 6) % 7;
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - diffToMonday - offsetWeeks * 7);
  const year = monday.getFullYear();
  const month = String(monday.getMonth() + 1).padStart(2, '0');
  const dateNum = String(monday.getDate()).padStart(2, '0');
  return `${year}-${month}-${dateNum}`;
}

/**
 * Returns Sunday date string 'YYYY-MM-DD' for a given Monday 'YYYY-MM-DD'.
 */
function getSundayOfWeek(mondayStr: string): string {
  const parts = mondayStr.split('-').map((x) => parseInt(x, 10));
  const monday = new Date(parts[0], parts[1] - 1, parts[2]);
  const sunday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6);
  const year = sunday.getFullYear();
  const month = String(sunday.getMonth() + 1).padStart(2, '0');
  const dateNum = String(sunday.getDate()).padStart(2, '0');
  return `${year}-${month}-${dateNum}`;
}

export default function ReportsPage() {
  const { user, primaryVertical, roleNames } = useAuth();
  const [activeTab, setActiveTab] = useState<'my' | 'review' | 'weekly'>('my');

  // Hierarchy Permissions
  const isSupervisorRole = useMemo(() => {
    return roleNames.some((r) =>
      ['COORDINATOR', 'SUPER_COORDINATOR', 'DEPUTY_CORE', 'SPORTS_CORE', 'CORE', 'ADMIN'].includes(r)
    );
  }, [roleNames]);

  const isExecutive = useMemo(() => {
    return roleNames.some((r) => ['SPORTS_CORE', 'DEPUTY_CORE', 'CORE', 'ADMIN'].includes(r));
  }, [roleNames]);

  const primaryRole = roleNames[0] || 'VOLUNTEER';

  // Available roles to inspect based on viewer's authority
  const allowedSubordinateRoles = useMemo(() => {
    if (isExecutive) {
      return [
        { code: 'SUPER_COORDINATOR', label: 'Super Coordinator' },
        { code: 'COORDINATOR', label: 'Coordinator' },
        { code: 'VOLUNTEER', label: 'Volunteer' },
      ];
    }
    if (roleNames.includes('SUPER_COORDINATOR')) {
      return [
        { code: 'COORDINATOR', label: 'Coordinator' },
        { code: 'VOLUNTEER', label: 'Volunteer' },
      ];
    }
    if (roleNames.includes('COORDINATOR')) {
      return [{ code: 'VOLUNTEER', label: 'Volunteer' }];
    }
    return [];
  }, [isExecutive, roleNames]);

  // Global State
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Tab 1: My Daily Reports State
  const [myReports, setMyReports] = useState<DailyReportResponse[]>([]);
  const [assignedTasks, setAssignedTasks] = useState<TaskResponse[]>([]);

  // Tab 2: Supervisor Review Queue State
  const [reviewQueue, setReviewQueue] = useState<DailyReportResponse[]>([]);

  // Tab 3: Hierarchical Weekly Reports State
  const [verticalsList, setVerticalsList] = useState<Vertical[]>([]);
  const [selectedVerticalId, setSelectedVerticalId] = useState<string>('');
  const [selectedRoleCode, setSelectedRoleCode] = useState<string>('');
  const [userSearchQuery, setUserSearchQuery] = useState<string>('');
  const [matchingUsers, setMatchingUsers] = useState<any[]>([]);
  const [selectedTargetUser, setSelectedTargetUser] = useState<any>(null);

  const [weeklyWeekOffset, setWeeklyWeekOffset] = useState<number>(0);
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReportResponse | null>(null);
  const [weeklyLoading, setWeeklyLoading] = useState<boolean>(false);
  const [previousWeeksOpen, setPreviousWeeksOpen] = useState<boolean>(false);

  // Dedicated Daily Report View Modal State
  const [activeReportDetail, setActiveReportDetail] = useState<DailyReportResponse | null>(null);
  const [reportDetailLoading, setReportDetailLoading] = useState<boolean>(false);

  // Submit / Resubmit Modal State
  const [isSubmitOpen, setIsSubmitOpen] = useState<boolean>(false);
  const [isResubmitMode, setIsResubmitMode] = useState<boolean>(false);
  const [editingReportId, setEditingReportId] = useState<string | null>(null);
  const [submitLoading, setSubmitLoading] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Submit Form Fields
  const [workSummary, setWorkSummary] = useState<string>('');
  const [blockers, setBlockers] = useState<string>('');
  const [nextActions, setNextActions] = useState<string>('');
  const [evidenceLinks, setEvidenceLinks] = useState<string>('');
  const [taskSearch, setTaskSearch] = useState<string>('');
  const [selectedTasks, setSelectedTasks] = useState<Record<string, string>>({});

  // Supervisor Review Action State (in Report Detail Modal)
  const [reviewActionType, setReviewActionType] = useState<'REVIEWED' | 'RETURNED'>('REVIEWED');
  const [reviewComments, setReviewComments] = useState<string>('');
  const [reviewSubmitting, setReviewSubmitting] = useState<boolean>(false);
  const [reviewFormOpen, setReviewFormOpen] = useState<boolean>(false);

  // Weekly Review Action State
  const [weeklyReviewOpen, setWeeklyReviewOpen] = useState<boolean>(false);
  const [weeklyReviewAction, setWeeklyReviewAction] = useState<'REVIEWED' | 'RETURNED'>('REVIEWED');
  const [weeklyReviewComments, setWeeklyReviewComments] = useState<string>('');
  const [weeklyReviewLoading, setWeeklyReviewLoading] = useState<boolean>(false);

  // Load User's Assigned Tasks on mount
  useEffect(() => {
    if (user?.id) {
      tasksApi
        .list({ assigned_to_id: user.id, limit: 100 })
        .then((res) => setAssignedTasks(res.items || []))
        .catch(() => {});
    }
  }, [user?.id]);

  // Load Verticals on mount
  useEffect(() => {
    organizationApi
      .listVerticals()
      .then((res) => {
        const items = res.items || [];
        if (isExecutive) {
          setVerticalsList(items.filter((v) => v.status === 'ACTIVE'));
          if (items.length > 0 && !selectedVerticalId) {
            setSelectedVerticalId(items[0].id);
          }
        } else if (primaryVertical?.id) {
          const userV = items.filter((v) => v.id === primaryVertical.id);
          setVerticalsList(userV.length > 0 ? userV : items);
          setSelectedVerticalId(primaryVertical.id);
        }
      })
      .catch(() => {});
  }, [isExecutive, primaryVertical?.id]);

  // Default Role Selection when allowed roles change
  useEffect(() => {
    if (allowedSubordinateRoles.length > 0 && !selectedRoleCode) {
      setSelectedRoleCode(allowedSubordinateRoles[0].code);
    }
  }, [allowedSubordinateRoles, selectedRoleCode]);

  // Fetch Matching Users when Vertical or Role changes
  useEffect(() => {
    if (!isSupervisorRole) {
      // Non-supervisor: Target user is self
      setSelectedTargetUser({
        id: user?.id,
        username: user?.username,
        full_name: user?.full_name,
        role: primaryRole,
        vertical_name: primaryVertical?.name || 'General',
      });
      return;
    }

    if (!selectedVerticalId) return;

    organizationApi
      .searchUsers({
        vertical_id: selectedVerticalId,
        role_filter: selectedRoleCode || undefined,
        search: userSearchQuery.trim() || undefined,
        limit: 50,
      })
      .then((res) => {
        const uList = res.items || [];
        setMatchingUsers(uList);
        if (uList.length > 0) {
          // If current selected user is not in the list, set to first
          if (!selectedTargetUser || !uList.some((u) => u.id === selectedTargetUser.id)) {
            const first = uList[0];
            setSelectedTargetUser({
              id: first.id,
              username: first.username,
              full_name: first.full_name,
              role: first.roles?.[0]?.name || selectedRoleCode || 'Member',
              vertical_name: first.verticals?.[0]?.name || 'General',
            });
          }
        } else {
          // No matching users in this vertical/role combination
          setSelectedTargetUser(null);
        }
      })
      .catch(() => setMatchingUsers([]));
  }, [
    isSupervisorRole,
    selectedVerticalId,
    selectedRoleCode,
    userSearchQuery,
    user?.id,
    user?.username,
    user?.full_name,
    primaryRole,
    primaryVertical?.name,
  ]);

  // Load Data for Active Tab
  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      if (activeTab === 'my') {
        const res = await reportsApi.getMyDaily({ limit: 50 });
        const sorted = (res.items || []).sort(
          (a, b) => new Date(b.report_date).getTime() - new Date(a.report_date).getTime()
        );
        setMyReports(sorted);
      } else if (activeTab === 'review') {
        const res = await reportsApi.getReviewQueue({ limit: 50 });
        setReviewQueue(res.items || []);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load report items');
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Load Weekly Report for Selected Target User
  const loadTargetWeeklyReport = useCallback(async () => {
    const targetUid = selectedTargetUser?.id || user?.id;
    if (!targetUid) {
      setWeeklyReport(null);
      return;
    }

    setWeeklyLoading(true);
    setErrorMsg(null);
    try {
      const weekStartStr = getMondayOfWeek(weeklyWeekOffset);
      const res = await reportsApi.getCurrentWeekly({
        user_id: targetUid,
        week_start: weekStartStr,
      });
      setWeeklyReport(res);
    } catch (err: any) {
      setWeeklyReport(null);
      setErrorMsg(err.message || 'Unable to load weekly report for selected user');
    } finally {
      setWeeklyLoading(false);
    }
  }, [selectedTargetUser?.id, user?.id, weeklyWeekOffset]);

  useEffect(() => {
    if (activeTab === 'weekly') {
      loadTargetWeeklyReport();
    }
  }, [activeTab, loadTargetWeeklyReport]);

  // Open Dedicated Daily Report Detail View
  const handleOpenReportDetail = async (reportId: string) => {
    setReportDetailLoading(true);
    setReviewFormOpen(false);
    setReviewComments('');
    setErrorMsg(null);
    try {
      const detail = await reportsApi.getDailyById(reportId);
      setActiveReportDetail(detail);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load daily report details');
    } finally {
      setReportDetailLoading(false);
    }
  };

  // Submit Review from Report Detail View
  const handleExecuteDailyReview = async () => {
    if (!activeReportDetail) return;
    if (reviewActionType === 'RETURNED' && (!reviewComments.trim() || reviewComments.trim().length < 2)) {
      setErrorMsg('Review comments are mandatory when returning a report for correction.');
      return;
    }

    setReviewSubmitting(true);
    try {
      const updated = await reportsApi.reviewDaily(activeReportDetail.id, {
        status: reviewActionType,
        review_comments: reviewComments.trim() || null,
      });

      setSuccessMsg(
        reviewActionType === 'REVIEWED'
          ? 'Report successfully approved!'
          : 'Report returned to submitter for correction.'
      );
      setActiveReportDetail(updated);
      setReviewFormOpen(false);
      loadData();
      if (activeTab === 'weekly') {
        loadTargetWeeklyReport();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process report review.');
    } finally {
      setReviewSubmitting(false);
    }
  };

  // Submit Weekly Review
  const handleExecuteWeeklyReview = async () => {
    if (!weeklyReport) return;
    if (weeklyReviewAction === 'RETURNED' && (!weeklyReviewComments.trim() || weeklyReviewComments.trim().length < 2)) {
      setErrorMsg('Supervisor comments are mandatory when returning a weekly report.');
      return;
    }

    setWeeklyReviewLoading(true);
    try {
      await reportsApi.reviewWeekly(weeklyReport.id, {
        status: weeklyReviewAction,
        supervisor_comments: weeklyReviewComments.trim() || null,
      });

      setSuccessMsg(
        weeklyReviewAction === 'REVIEWED'
          ? 'Weekly report successfully approved!'
          : 'Weekly report returned for correction.'
      );
      setWeeklyReviewOpen(false);
      loadTargetWeeklyReport();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to review weekly report.');
    } finally {
      setWeeklyReviewLoading(false);
    }
  };

  // Open Create Modal
  const handleOpenCreateModal = () => {
    setIsResubmitMode(false);
    setEditingReportId(null);
    setWorkSummary('');
    setBlockers('');
    setNextActions('');
    setEvidenceLinks('');
    setSelectedTasks({});
    setTaskSearch('');
    setSubmitError(null);
    setIsSubmitOpen(true);
  };

  // Open Edit & Resubmit Modal
  const handleOpenResubmitModal = (report: DailyReportResponse) => {
    setIsResubmitMode(true);
    setEditingReportId(report.id);
    setWorkSummary(report.work_summary || '');
    setBlockers(report.blockers || '');
    setNextActions(report.next_actions || '');
    setEvidenceLinks(report.evidence_links || '');

    const initialTasks: Record<string, string> = {};
    if (report.tasks) {
      report.tasks.forEach((t) => {
        initialTasks[t.task_id] = t.progress_notes || '';
      });
    }
    setSelectedTasks(initialTasks);
    setTaskSearch('');
    setSubmitError(null);
    setIsSubmitOpen(true);
  };

  // Submit Daily Report
  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workSummary.trim() || workSummary.trim().length < 5) {
      setSubmitError('Work completed today is required and must be at least 5 characters.');
      return;
    }

    setSubmitLoading(true);
    setSubmitError(null);

    const taskItems: DailyReportTaskCreate[] = Object.entries(selectedTasks).map(
      ([task_id, progress_notes]) => ({
        task_id,
        progress_notes: progress_notes.trim() || undefined,
      })
    );

    try {
      if (isResubmitMode && editingReportId) {
        const payload: DailyReportUpdate = {
          work_summary: workSummary.trim(),
          tasks: taskItems,
          blockers: blockers.trim() || null,
          next_actions: nextActions.trim() || null,
          evidence_links: evidenceLinks.trim() || null,
          submit_now: true,
        };
        await reportsApi.resubmitDaily(editingReportId, payload);
        setSuccessMsg('Daily report corrected and resubmitted successfully!');
      } else {
        const payload: DailyReportCreate = {
          work_summary: workSummary.trim(),
          tasks: taskItems,
          blockers: blockers.trim() || null,
          next_actions: nextActions.trim() || null,
          evidence_links: evidenceLinks.trim() || null,
          submit_now: true,
        };
        await reportsApi.submitDaily(payload);
        setSuccessMsg('Daily work report submitted successfully!');
      }

      setIsSubmitOpen(false);
      loadData();
      if (activeTab === 'weekly') {
        loadTargetWeeklyReport();
      }
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to submit report. Please verify input.');
    } finally {
      setSubmitLoading(false);
    }
  };

  // Task Selection Utilities
  const filteredAssignedTasks = useMemo(() => {
    if (!taskSearch.trim()) return assignedTasks;
    const q = taskSearch.toLowerCase();
    return assignedTasks.filter((t) => t.title.toLowerCase().includes(q));
  }, [assignedTasks, taskSearch]);

  const toggleTaskSelection = (taskId: string) => {
    setSelectedTasks((prev) => {
      const next = { ...prev };
      if (taskId in next) delete next[taskId];
      else next[taskId] = '';
      return next;
    });
  };

  const updateTaskNotes = (taskId: string, notes: string) => {
    setSelectedTasks((prev) => ({ ...prev, [taskId]: notes }));
  };

  // Week Date Strings
  const mondayStr = useMemo(() => getMondayOfWeek(weeklyWeekOffset), [weeklyWeekOffset]);
  const sundayStr = useMemo(() => getSundayOfWeek(mondayStr), [mondayStr]);

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              Work Reports Workspace
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Role-aware daily operational reports, supervisor review queue, and hierarchical weekly browser.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                loadData();
                if (activeTab === 'weekly') loadTargetWeeklyReport();
              }}
              disabled={loading || weeklyLoading}
              className="gap-1.5 text-xs h-8"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading || weeklyLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleOpenCreateModal}
              className="gap-1.5 text-xs h-8"
            >
              <Plus className="w-3.5 h-3.5" />
              Submit Daily Report
            </Button>
          </div>
        </div>

        {/* Global Feedback Messages */}
        {successMsg && (
          <Alert variant="success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}
        {errorMsg && (
          <Alert variant="danger" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        {/* Workspace Tab Bar */}
        <div className="flex border-b border-border gap-2">
          <button
            onClick={() => setActiveTab('my')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeTab === 'my'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <UserIcon className="w-3.5 h-3.5" />
            My Daily Reports
            <Badge variant="default" className="ml-1 text-[10px]">
              {myReports.length}
            </Badge>
          </button>

          {isSupervisorRole && (
            <button
              onClick={() => setActiveTab('review')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-medium border-b-2 transition-colors ${
                activeTab === 'review'
                  ? 'border-primary text-primary font-semibold'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              Supervisor Review Queue
              {reviewQueue.length > 0 ? (
                <Badge variant="danger" className="ml-1 text-[10px] font-bold animate-pulse">
                  {reviewQueue.length}
                </Badge>
              ) : (
                <Badge variant="default" className="ml-1 text-[10px]">
                  0
                </Badge>
              )}
            </button>
          )}

          <button
            onClick={() => setActiveTab('weekly')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeTab === 'weekly'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            Weekly Reports
          </button>
        </div>

        {/* ========================================================================= */}
        {/* TAB 1: MY DAILY REPORTS                                                   */}
        {/* ========================================================================= */}
        {activeTab === 'my' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground bg-muted/20 px-3 py-2 rounded-md border border-border/50">
              <span className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                Chronological operational history (Newest first • 14-day rolling window)
              </span>
              <span className="font-semibold text-foreground">{myReports.length} reports</span>
            </div>

            {loading ? (
              <div className="py-12 flex justify-center">
                <Spinner size="lg" />
              </div>
            ) : myReports.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="No daily reports logged"
                description="You have not submitted any daily reports within the current period."
                actionLabel="Submit Daily Report"
                onAction={handleOpenCreateModal}
              />
            ) : (
              <div className="space-y-2">
                {myReports.map((report) => {
                  const isReturned = report.status === 'RETURNED';

                  return (
                    <div
                      key={report.id}
                      onClick={() => handleOpenReportDetail(report.id)}
                      className={`p-3.5 rounded-lg border cursor-pointer transition-all select-none flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                        isReturned
                          ? 'border-amber-500/40 bg-amber-500/5 hover:border-amber-500/60'
                          : 'border-border bg-card hover:border-border/90 hover:bg-muted/10 shadow-sm'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`p-2 rounded-md ${
                            isReturned ? 'bg-amber-500/10 text-amber-600' : 'bg-primary/10 text-primary'
                          }`}
                        >
                          <Calendar className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-sm text-foreground">
                              {formatReportDate(report.report_date)}
                            </span>
                            <StatusBadge status={report.status} />
                            {report.tasks && report.tasks.length > 0 && (
                              <Badge variant="default" className="text-[10px]">
                                {report.tasks.length} {report.tasks.length === 1 ? 'task' : 'tasks'}
                              </Badge>
                            )}
                            <Badge variant="default" className="text-[10px]">
                              {report.vertical_name || 'General'}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                            {report.work_summary}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-center">
                        {isReturned && (
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenResubmitModal(report);
                            }}
                            className="gap-1 text-xs h-7"
                          >
                            <RotateCcw className="w-3 h-3" />
                            Resubmit
                          </Button>
                        )}
                        <span className="text-xs text-muted-foreground flex items-center gap-1 hover:text-foreground">
                          View details <ChevronRight className="w-3.5 h-3.5" />
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: SUPERVISOR REVIEW QUEUE (Clean User → Role → Vertical → Date → Status) */}
        {/* ========================================================================= */}
        {activeTab === 'review' && isSupervisorRole && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground bg-muted/20 px-3 py-2 rounded-md border border-border/50">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                Reports pending review in your operational supervision scope
              </span>
              <span className="font-semibold text-foreground">{reviewQueue.length} pending</span>
            </div>

            {loading ? (
              <div className="py-12 flex justify-center">
                <Spinner size="lg" />
              </div>
            ) : reviewQueue.length === 0 ? (
              <EmptyState
                icon={CheckCircle2}
                title="Review queue is clear"
                description="There are currently no daily reports awaiting your supervisor review."
              />
            ) : (
              <div className="space-y-2">
                {reviewQueue.map((report) => (
                  <div
                    key={report.id}
                    onClick={() => handleOpenReportDetail(report.id)}
                    className="p-3.5 rounded-lg border border-border bg-card hover:border-border/90 hover:bg-muted/10 cursor-pointer transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-md bg-amber-500/10 text-amber-600">
                        <Clock className="w-4 h-4" />
                      </div>
                      <div>
                        {/* User → Role → Vertical → Date → Status */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-sm text-foreground">
                            {report.user_full_name || report.username}
                          </span>
                          <span className="text-muted-foreground text-xs">→</span>
                          {report.user_role && (
                            <Badge variant="default" className="text-[10px]">
                              {report.user_role}
                            </Badge>
                          )}
                          <span className="text-muted-foreground text-xs">→</span>
                          <Badge variant="default" className="text-[10px]">
                            {report.vertical_name || 'Vertical'}
                          </Badge>
                          <span className="text-muted-foreground text-xs">→</span>
                          <span className="text-xs font-semibold text-primary">
                            {formatReportDate(report.report_date)}
                          </span>
                          <span className="text-muted-foreground text-xs">→</span>
                          <StatusBadge status={report.status} />
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                          {report.work_summary}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenReportDetail(report.id);
                        }}
                        className="gap-1 text-xs h-7"
                      >
                        <Eye className="w-3 h-3" />
                        Review
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: HIERARCHICAL WEEKLY REPORT BROWSER                                  */}
        {/* Flow: Vertical → Role → User → Week → Day → Complete Daily Report        */}
        {/* ========================================================================= */}
        {activeTab === 'weekly' && (
          <div className="space-y-4">
            {/* Hierarchical Selector (Only for Supervisors) */}
            {isSupervisorRole && (
              <Card className="border border-border p-3.5 bg-card shadow-sm space-y-3">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-primary" />
                  Hierarchical Report Selector: Vertical → Role → User
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {/* Step 1: Vertical */}
                  <div>
                    <label className="block text-[11px] font-medium text-muted-foreground mb-1">
                      1. Vertical Division
                    </label>
                    <select
                      value={selectedVerticalId}
                      onChange={(e) => {
                        setSelectedVerticalId(e.target.value);
                        setSelectedTargetUser(null);
                      }}
                      className="w-full text-xs rounded-md border border-input bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      {verticalsList.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Step 2: Role */}
                  <div>
                    <label className="block text-[11px] font-medium text-muted-foreground mb-1">
                      2. Role in Vertical
                    </label>
                    <select
                      value={selectedRoleCode}
                      onChange={(e) => {
                        setSelectedRoleCode(e.target.value);
                        setSelectedTargetUser(null);
                      }}
                      className="w-full text-xs rounded-md border border-input bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      {allowedSubordinateRoles.map((r) => (
                        <option key={r.code} value={r.code}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Step 3: User */}
                  <div>
                    <label className="block text-[11px] font-medium text-muted-foreground mb-1">
                      3. Select Team Member ({matchingUsers.length})
                    </label>
                    <select
                      value={selectedTargetUser?.id || ''}
                      onChange={(e) => {
                        const picked = matchingUsers.find((u) => u.id === e.target.value);
                        if (picked) {
                          setSelectedTargetUser({
                            id: picked.id,
                            username: picked.username,
                            full_name: picked.full_name,
                            role: picked.roles?.[0]?.name || selectedRoleCode,
                            vertical_name: picked.verticals?.[0]?.name || 'General',
                          });
                        }
                      }}
                      className="w-full text-xs rounded-md border border-input bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      {matchingUsers.length === 0 ? (
                        <option value="">No members found in this vertical/role</option>
                      ) : (
                        matchingUsers.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.full_name || u.username} (@{u.username})
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                </div>

                {/* Filter Search for user if list is large */}
                <div className="pt-1 flex items-center justify-between text-xs text-muted-foreground">
                  <div className="relative w-full max-w-xs">
                    <Search className="w-3 h-3 absolute left-2.5 top-2.5 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Search member by name, username, email..."
                      value={userSearchQuery}
                      onChange={(e) => setUserSearchQuery(e.target.value)}
                      className="w-full pl-7 pr-2.5 py-1 text-xs rounded border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>

                  {/* Quick self toggle for supervisors */}
                  <button
                    onClick={() => {
                      setSelectedTargetUser({
                        id: user?.id,
                        username: user?.username,
                        full_name: user?.full_name,
                        role: primaryRole,
                        vertical_name: primaryVertical?.name || 'General',
                      });
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    View My Own Reports
                  </button>
                </div>
              </Card>
            )}

            {/* Selected User Header & Week Bar */}
            {selectedTargetUser && (
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-card p-3.5 rounded-lg border border-border shadow-sm">
                <div>
                  <div className="text-base font-bold text-foreground flex items-center gap-2">
                    {selectedTargetUser.full_name || selectedTargetUser.username}
                    <span className="text-xs font-normal text-muted-foreground">
                      (@{selectedTargetUser.username})
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    <span className="font-semibold text-foreground">
                      {selectedTargetUser.role || 'Member'}
                    </span>{' '}
                    • <span>{selectedTargetUser.vertical_name || 'General'}</span>
                  </div>
                </div>

                {/* Week Navigation */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {formatReportDate(mondayStr)} – {formatReportDate(sundayStr)}
                  </span>
                  <Button
                    size="sm"
                    variant={weeklyWeekOffset === 0 ? 'primary' : 'outline'}
                    onClick={() => setWeeklyWeekOffset(0)}
                    className="text-xs h-7"
                  >
                    Current Week
                  </Button>
                  <Button
                    size="sm"
                    variant={weeklyWeekOffset === 1 ? 'primary' : 'outline'}
                    onClick={() => setWeeklyWeekOffset(1)}
                    className="text-xs h-7"
                  >
                    Previous Week
                  </Button>
                </div>
              </div>
            )}

            {/* Weekly Days List (Monday through Sunday) */}
            {weeklyLoading ? (
              <div className="py-12 flex justify-center">
                <Spinner size="lg" />
              </div>
            ) : !weeklyReport ? (
              <EmptyState
                icon={Calendar}
                title="No report data found"
                description="There are no weekly reports available for this user and time period."
              />
            ) : (
              <div className="space-y-4">
                {/* 7-Day Clean List */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center justify-between">
                    <span>Daily Submissions (Monday – Sunday)</span>
                    <span>
                      {weeklyReport.days_reported_count || 0} / 7 Days Reported
                    </span>
                  </div>

                  {weeklyReport.days_reported && weeklyReport.days_reported.length > 0 ? (
                    weeklyReport.days_reported.map((dayItem: any) => {
                      const matchingReport = weeklyReport.daily_reports?.find(
                        (dr) => dr.report_date === dayItem.date
                      );
                      const isReported = dayItem.reported && matchingReport;

                      return (
                        <div
                          key={dayItem.date}
                          onClick={() => {
                            if (isReported) {
                              handleOpenReportDetail(matchingReport.id);
                            }
                          }}
                          className={`p-3 rounded-lg border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 ${
                            isReported
                              ? 'border-border bg-card hover:border-primary/50 hover:bg-muted/10 cursor-pointer shadow-sm'
                              : 'border-dashed border-border/60 bg-muted/5 opacity-70 cursor-default'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`p-1.5 rounded ${
                                isReported
                                  ? 'bg-emerald-500/10 text-emerald-600'
                                  : 'bg-muted/40 text-muted-foreground'
                              }`}
                            >
                              <Calendar className="w-3.5 h-3.5" />
                            </div>

                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-xs text-foreground">
                                  {dayItem.day_of_week}
                                </span>
                                <span className="text-[11px] text-muted-foreground">
                                  ({formatReportDate(dayItem.date)})
                                </span>
                                {isReported ? (
                                  <StatusBadge status={matchingReport.status} />
                                ) : (
                                  <span className="text-[11px] text-muted-foreground italic">
                                    Not submitted
                                  </span>
                                )}
                              </div>

                              {isReported && (
                                <p className="text-xs text-foreground mt-0.5 line-clamp-1">
                                  {matchingReport.work_summary}
                                </p>
                              )}
                            </div>
                          </div>

                          {isReported && (
                            <div className="flex items-center gap-2 self-end sm:self-center">
                              {matchingReport.tasks && matchingReport.tasks.length > 0 && (
                                <Badge variant="default" className="text-[10px]">
                                  {matchingReport.tasks.length} tasks
                                </Badge>
                              )}
                              <span className="text-xs text-primary font-medium flex items-center gap-0.5">
                                View report <ChevronRight className="w-3 h-3" />
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : null}
                </div>

                {/* Consolidated Weekly Summary & Supervisor Actions */}
                <div className="p-4 rounded-lg border border-border bg-card space-y-3 text-xs">
                  <div className="flex items-center justify-between border-b border-border/50 pb-2">
                    <div className="font-bold text-sm text-foreground flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-primary" />
                      Consolidated Weekly Rollup
                    </div>

                    {isSupervisorRole &&
                      selectedTargetUser &&
                      selectedTargetUser.id !== user?.id && (
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => {
                              setWeeklyReviewAction('REVIEWED');
                              setWeeklyReviewComments('');
                              setWeeklyReviewOpen(true);
                            }}
                            className="text-xs h-7 gap-1"
                          >
                            <Check className="w-3 h-3" />
                            Approve Week
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setWeeklyReviewAction('RETURNED');
                              setWeeklyReviewComments('');
                              setWeeklyReviewOpen(true);
                            }}
                            className="text-xs h-7 gap-1 text-rose-600 hover:text-rose-700"
                          >
                            <RotateCcw className="w-3 h-3" />
                            Return Week
                          </Button>
                        </div>
                      )}
                  </div>

                  <div>
                    <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                      Work Completed
                    </span>
                    <p className="text-foreground mt-0.5 whitespace-pre-wrap bg-muted/20 p-2.5 rounded leading-relaxed">
                      {weeklyReport.summary || 'No daily reports logged for this period.'}
                    </p>
                  </div>

                  {weeklyReport.blockers && (
                    <div className="p-2.5 rounded bg-rose-500/5 border border-rose-500/20 text-rose-600 dark:text-rose-400">
                      <span className="font-semibold">Blockers Encountered:</span>{' '}
                      {weeklyReport.blockers}
                    </div>
                  )}

                  {weeklyReport.priorities_next_week && (
                    <div className="p-2.5 rounded bg-blue-500/5 border border-blue-500/20 text-blue-600 dark:text-blue-400">
                      <span className="font-semibold">Priorities for Next Week:</span>{' '}
                      {weeklyReport.priorities_next_week}
                    </div>
                  )}

                  {weeklyReport.supervisor_comments && (
                    <div className="p-2.5 rounded bg-muted/40 border border-border">
                      <span className="font-semibold text-muted-foreground">Supervisor Feedback:</span>{' '}
                      {weeklyReport.supervisor_comments}
                    </div>
                  )}
                </div>

                {/* Collapsed Minimal Previous Weeks */}
                <div className="pt-2 border-t border-border/50">
                  <button
                    onClick={() => setPreviousWeeksOpen(!previousWeeksOpen)}
                    className="text-xs font-semibold text-muted-foreground hover:text-foreground flex items-center gap-1.5"
                  >
                    <ChevronDown
                      className={`w-3.5 h-3.5 transition-transform ${
                        previousWeeksOpen ? 'rotate-180' : ''
                      }`}
                    />
                    Previous Weeks History
                  </button>

                  {previousWeeksOpen && (
                    <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
                      {[1, 2, 3].map((offset) => {
                        const mStr = getMondayOfWeek(offset);
                        const sStr = getSundayOfWeek(mStr);
                        const isCurrentOffset = weeklyWeekOffset === offset;

                        return (
                          <button
                            key={offset}
                            onClick={() => setWeeklyWeekOffset(offset)}
                            className={`p-2.5 rounded-md border text-left text-xs transition-all ${
                              isCurrentOffset
                                ? 'border-primary bg-primary/10 text-primary font-semibold'
                                : 'border-border bg-card text-muted-foreground hover:border-border/80 hover:text-foreground'
                            }`}
                          >
                            <div className="font-medium">
                              Week {offset === 1 ? '(Previous 7d)' : `(-${offset}w)`}
                            </div>
                            <div className="text-[11px] opacity-80 mt-0.5">
                              {formatReportDate(mStr)} – {formatReportDate(sStr)}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* MODAL: DEDICATED DAILY REPORT DETAIL VIEW                                  */}
        {/* Clean Structured Layout: User → Role → Vertical → Date → Status → Details */}
        {/* ========================================================================= */}
        <Modal
          isOpen={!!activeReportDetail}
          onClose={() => setActiveReportDetail(null)}
          title="Daily Operational Work Report"
        >
          {reportDetailLoading ? (
            <div className="py-12 flex justify-center">
              <Spinner size="lg" />
            </div>
          ) : activeReportDetail ? (
            <div className="space-y-4 text-xs">
              {/* Structured Header: User, Role, Vertical, Date, Status */}
              <div className="p-3.5 rounded-lg bg-muted/30 border border-border grid grid-cols-2 gap-2.5">
                <div>
                  <span className="font-semibold text-muted-foreground">User:</span>{' '}
                  <span className="text-foreground font-bold">
                    {activeReportDetail.user_full_name || activeReportDetail.username}
                  </span>{' '}
                  <span className="text-muted-foreground">(@{activeReportDetail.username})</span>
                </div>
                <div>
                  <span className="font-semibold text-muted-foreground">Role:</span>{' '}
                  <Badge variant="default" className="text-[10px]">
                    {activeReportDetail.user_role || 'Member'}
                  </Badge>
                </div>
                <div>
                  <span className="font-semibold text-muted-foreground">Vertical:</span>{' '}
                  <span className="text-foreground font-medium">
                    {activeReportDetail.vertical_name || 'General'}
                  </span>
                </div>
                <div>
                  <span className="font-semibold text-muted-foreground">Report Date:</span>{' '}
                  <span className="text-foreground font-bold">
                    {formatReportDate(activeReportDetail.report_date)}
                  </span>
                </div>
                <div className="col-span-2 flex items-center gap-2 pt-1 border-t border-border/40">
                  <span className="font-semibold text-muted-foreground">Status:</span>
                  <StatusBadge status={activeReportDetail.status} />
                  {activeReportDetail.submitted_at && (
                    <span className="text-[11px] text-muted-foreground">
                      Submitted at {formatAuditDateTime(activeReportDetail.submitted_at)}
                    </span>
                  )}
                </div>
              </div>

              {/* Returned Alert if Applicable */}
              {activeReportDetail.status === 'RETURNED' && activeReportDetail.review_comments && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-700 dark:text-amber-400">
                  <div className="font-bold flex items-center gap-1.5 mb-1 text-xs">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                    Supervisor Returned This Report For Correction:
                  </div>
                  <p className="text-xs">{activeReportDetail.review_comments}</p>
                </div>
              )}

              {/* Work Completed */}
              <div>
                <h4 className="font-bold uppercase tracking-wider text-muted-foreground text-[10px] mb-1">
                  Work Completed Today
                </h4>
                <p className="text-foreground whitespace-pre-wrap bg-muted/20 p-3 rounded-md text-xs leading-relaxed border border-border/40">
                  {activeReportDetail.work_summary}
                </p>
              </div>

              {/* Associated Tasks & Progress */}
              {activeReportDetail.tasks && activeReportDetail.tasks.length > 0 && (
                <div>
                  <h4 className="font-bold uppercase tracking-wider text-muted-foreground text-[10px] mb-1.5 flex items-center gap-1">
                    <CheckSquare className="w-3 h-3 text-primary" />
                    Associated Tasks & Task Progress ({activeReportDetail.tasks.length})
                  </h4>
                  <div className="space-y-1.5">
                    {activeReportDetail.tasks.map((t) => (
                      <div
                        key={t.task_id}
                        className="p-2.5 bg-card rounded-md border border-border/70 flex flex-col gap-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-foreground">
                            {t.task_title || 'Assigned Task'}
                          </span>
                          <Badge variant="default" className="text-[10px]">
                            {t.task_status || 'ASSIGNED'}
                          </Badge>
                        </div>
                        {t.progress_notes && (
                          <div className="text-muted-foreground mt-0.5">
                            <span className="font-semibold text-foreground">Progress:</span>{' '}
                            {t.progress_notes}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Blockers & Next Actions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {activeReportDetail.blockers && (
                  <div className="p-2.5 rounded-md bg-rose-500/5 border border-rose-500/20 text-rose-600 dark:text-rose-400">
                    <span className="font-bold flex items-center gap-1 mb-0.5">
                      <AlertTriangle className="w-3 h-3" /> Blockers / Delays:
                    </span>
                    <p className="whitespace-pre-wrap text-foreground">{activeReportDetail.blockers}</p>
                  </div>
                )}

                {activeReportDetail.next_actions && (
                  <div className="p-2.5 rounded-md bg-blue-500/5 border border-blue-500/20 text-blue-600 dark:text-blue-400">
                    <span className="font-bold flex items-center gap-1 mb-0.5">
                      <Clock className="w-3 h-3" /> Next Planned Actions:
                    </span>
                    <p className="whitespace-pre-wrap text-foreground">
                      {activeReportDetail.next_actions}
                    </p>
                  </div>
                )}
              </div>

              {/* Evidence / Reference URL */}
              {activeReportDetail.evidence_links && (
                <div>
                  <span className="font-semibold text-muted-foreground mr-1.5">
                    Evidence / Reference:
                  </span>
                  <a
                    href={activeReportDetail.evidence_links}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary hover:underline inline-flex items-center gap-1 font-medium"
                  >
                    <LinkIcon className="w-3 h-3" />
                    {activeReportDetail.evidence_links}
                  </a>
                </div>
              )}

              {/* Supervisor Review Decision */}
              {activeReportDetail.status === 'REVIEWED' && (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-md text-emerald-700 dark:text-emerald-300">
                  <div className="font-bold flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Approved by {activeReportDetail.reviewed_by_username || activeReportDetail.reviewer_username || 'Supervisor'}
                    {activeReportDetail.reviewed_at
                      ? ` on ${formatAuditDateTime(activeReportDetail.reviewed_at)}`
                      : ''}
                  </div>
                  {activeReportDetail.review_comments && (
                    <p className="mt-1 text-xs">{activeReportDetail.review_comments}</p>
                  )}
                </div>
              )}

              {/* Supervisor Actions (Only for Authorized Supervisors on other's submitted reports) */}
              {isSupervisorRole &&
                activeReportDetail.user_id !== user?.id &&
                activeReportDetail.status === 'SUBMITTED' && (
                  <div className="pt-3 border-t border-border space-y-2">
                    {!reviewFormOpen ? (
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => {
                            setReviewActionType('REVIEWED');
                            setReviewComments('');
                            setReviewFormOpen(true);
                          }}
                          className="h-8 text-xs gap-1"
                        >
                          <Check className="w-3.5 h-3.5" />
                          Approve Report
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setReviewActionType('RETURNED');
                            setReviewComments('');
                            setReviewFormOpen(true);
                          }}
                          className="h-8 text-xs gap-1 text-rose-600 hover:text-rose-700"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                          Return for Correction
                        </Button>
                      </div>
                    ) : (
                      <div className="space-y-2 bg-muted/20 p-3 rounded-lg border border-border">
                        <label className="block text-xs font-semibold text-foreground">
                          {reviewActionType === 'REVIEWED'
                            ? 'Approval Comments (Optional):'
                            : 'Correction Instructions (Mandatory):'}
                        </label>
                        <textarea
                          rows={3}
                          value={reviewComments}
                          onChange={(e) => setReviewComments(e.target.value)}
                          placeholder={
                            reviewActionType === 'RETURNED'
                              ? 'State what needs correction before approval...'
                              : 'Optional notes...'
                          }
                          className="w-full text-xs rounded-md border border-input bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setReviewFormOpen(false)}
                            disabled={reviewSubmitting}
                            className="h-7 text-xs"
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            variant={reviewActionType === 'REVIEWED' ? 'primary' : 'outline'}
                            onClick={handleExecuteDailyReview}
                            disabled={reviewSubmitting}
                            className={`h-7 text-xs ${
                              reviewActionType === 'RETURNED' ? 'text-rose-600 hover:text-rose-700' : ''
                            }`}
                          >
                            {reviewSubmitting
                              ? 'Saving...'
                              : reviewActionType === 'REVIEWED'
                              ? 'Confirm Approval'
                              : 'Return for Correction'}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
            </div>
          ) : null}
        </Modal>

        {/* ========================================================================= */}
        {/* MODAL: SUBMIT / RESUBMIT DAILY REPORT                                     */}
        {/* ========================================================================= */}
        <Modal
          isOpen={isSubmitOpen}
          onClose={() => setIsSubmitOpen(false)}
          title={isResubmitMode ? 'Edit & Resubmit Daily Report' : 'Submit Daily Work Report'}
        >
          <form onSubmit={handleSubmitReport} className="space-y-3 text-xs">
            {submitError && (
              <Alert variant="danger" onClose={() => setSubmitError(null)}>
                {submitError}
              </Alert>
            )}

            {/* Derived Profile Banner */}
            <div className="p-3 rounded-md bg-primary/5 border border-primary/20 space-y-1">
              <div className="font-semibold text-primary flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" />
                Auto-Derived Profile
              </div>
              <div className="grid grid-cols-2 gap-1.5 text-muted-foreground">
                <div>
                  <span className="font-medium text-foreground">Author:</span>{' '}
                  {user?.full_name || user?.username}
                </div>
                <div>
                  <span className="font-medium text-foreground">Role:</span> {primaryRole}
                </div>
                <div>
                  <span className="font-medium text-foreground">Vertical:</span>{' '}
                  {primaryVertical?.name || 'Assigned Division'}
                </div>
                <div>
                  <span className="font-medium text-foreground">Date:</span>{' '}
                  {formatReportDate(new Date().toISOString().split('T')[0])}
                </div>
              </div>
            </div>

            {/* Work Completed */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Work Completed Today <span className="text-rose-500">*</span>
              </label>
              <textarea
                required
                rows={3}
                value={workSummary}
                onChange={(e) => setWorkSummary(e.target.value)}
                placeholder="Operational summary of work accomplished today..."
                className="w-full rounded-md border border-input bg-background p-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Tasks Multi-Selector */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="font-semibold text-foreground">
                  Associated Tasks (Optional)
                </label>
                <span className="text-muted-foreground">{Object.keys(selectedTasks).length} selected</span>
              </div>

              {assignedTasks.length === 0 ? (
                <p className="italic text-muted-foreground p-2 rounded bg-muted/10 border border-border">
                  No active tasks assigned to you. You may still submit your report.
                </p>
              ) : (
                <div className="space-y-1.5 border border-border rounded-md p-2 bg-muted/10 max-h-44 overflow-y-auto">
                  <div className="relative mb-1">
                    <Search className="w-3 h-3 absolute left-2 top-2 text-muted-foreground" />
                    <input
                      type="text"
                      value={taskSearch}
                      onChange={(e) => setTaskSearch(e.target.value)}
                      placeholder="Search tasks..."
                      className="w-full pl-6 pr-2 py-1 text-[11px] rounded border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>

                  {filteredAssignedTasks.map((task) => {
                    const isSelected = task.id in selectedTasks;
                    return (
                      <div
                        key={task.id}
                        className={`p-2 rounded border transition-colors ${
                          isSelected
                            ? 'border-primary/50 bg-primary/5'
                            : 'border-border/60 bg-card hover:border-border'
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <input
                            type="checkbox"
                            id={`task-${task.id}`}
                            checked={isSelected}
                            onChange={() => toggleTaskSelection(task.id)}
                            className="mt-0.5 rounded border-input text-primary focus:ring-primary"
                          />
                          <label
                            htmlFor={`task-${task.id}`}
                            className="flex-1 cursor-pointer select-none text-[11px]"
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className="font-medium text-foreground">{task.title}</span>
                              <Badge variant="default" className="text-[9px]">
                                {task.status}
                              </Badge>
                            </div>
                          </label>
                        </div>

                        {isSelected && (
                          <input
                            type="text"
                            value={selectedTasks[task.id] || ''}
                            onChange={(e) => updateTaskNotes(task.id, e.target.value)}
                            placeholder="Progress notes or milestones on this task..."
                            className="mt-1.5 w-full text-[11px] p-1 rounded border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Blockers */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Blockers & Delays (Optional)
              </label>
              <textarea
                rows={2}
                value={blockers}
                onChange={(e) => setBlockers(e.target.value)}
                placeholder="Any technical or operational impediments..."
                className="w-full rounded-md border border-input bg-background p-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Next Actions */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Next Planned Actions (Optional)
              </label>
              <textarea
                rows={2}
                value={nextActions}
                onChange={(e) => setNextActions(e.target.value)}
                placeholder="Activities planned for tomorrow or next session..."
                className="w-full rounded-md border border-input bg-background p-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Evidence Link */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Evidence / Reference URL (Optional)
              </label>
              <Input
                type="url"
                value={evidenceLinks}
                onChange={(e) => setEvidenceLinks(e.target.value)}
                placeholder="https://..."
                className="text-xs h-8"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsSubmitOpen(false)}
                disabled={submitLoading}
                className="h-8 text-xs"
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" disabled={submitLoading} className="h-8 text-xs">
                {submitLoading
                  ? 'Submitting...'
                  : isResubmitMode
                  ? 'Resubmit Report'
                  : 'Submit Report'}
              </Button>
            </div>
          </form>
        </Modal>

        {/* ========================================================================= */}
        {/* MODAL: WEEKLY REPORT REVIEW                                               */}
        {/* ========================================================================= */}
        <Modal
          isOpen={weeklyReviewOpen}
          onClose={() => setWeeklyReviewOpen(false)}
          title={
            weeklyReviewAction === 'REVIEWED'
              ? 'Approve Weekly Report'
              : 'Return Weekly Report for Correction'
          }
        >
          <div className="space-y-3 text-xs">
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Supervisor Feedback Comments{' '}
                {weeklyReviewAction === 'RETURNED' && <span className="text-rose-500">*</span>}
              </label>
              <textarea
                rows={4}
                value={weeklyReviewComments}
                onChange={(e) => setWeeklyReviewComments(e.target.value)}
                placeholder={
                  weeklyReviewAction === 'RETURNED'
                    ? 'Explain reasons for returning this weekly report...'
                    : 'Optional approval feedback notes...'
                }
                className="w-full rounded-md border border-input bg-background p-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setWeeklyReviewOpen(false)}
                disabled={weeklyReviewLoading}
                className="h-8 text-xs"
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant={weeklyReviewAction === 'REVIEWED' ? 'primary' : 'outline'}
                size="sm"
                onClick={handleExecuteWeeklyReview}
                disabled={weeklyReviewLoading}
                className={`h-8 text-xs ${
                  weeklyReviewAction === 'RETURNED' ? 'text-rose-600 hover:text-rose-700' : ''
                }`}
              >
                {weeklyReviewLoading
                  ? 'Saving...'
                  : weeklyReviewAction === 'REVIEWED'
                  ? 'Confirm Approval'
                  : 'Return Week'}
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </AppShell>
  );
}
