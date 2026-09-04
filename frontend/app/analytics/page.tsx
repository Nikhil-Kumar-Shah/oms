'use client';

/**
 * Operational Analytics & Administrative Reports (/analytics)
 * Live organizational KPIs, performance indicators, division deep-dives,
 * and executive administrative reporting.
 */

import React, { useState, useEffect } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { useAuth } from '@/hooks/useAuth';
import {
  analyticsApi,
  adminReportsApi,
  organizationApi,
  ApiException,
} from '@/lib/api';
import {
  OperationalDashboardResponse,
  PerformanceIndicatorsResponse,
  OperationalAnalyticsResponse,
  AdminReportResponse,
} from '@/types/analytics';
import { Vertical } from '@/types/organization';
import {
  BarChart3,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Flag,
  Users,
  ShieldAlert,
  FileText,
  GitPullRequest,
  TrendingUp,
  Activity,
  Layers,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';

export default function AnalyticsPage() {
  const { hasPermission } = useAuth();
  const [activeTab, setActiveTab] = useState<'dashboard' | 'indicators' | 'domains' | 'reports'>('dashboard');

  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Tab 1: Operational Dashboard
  const [dashboard, setDashboard] = useState<OperationalDashboardResponse | null>(null);

  // Tab 2: Performance Indicators
  const [indicators, setIndicators] = useState<PerformanceIndicatorsResponse | null>(null);

  // Tab 3: Division Deep-Dive
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [selectedVerticalId, setSelectedVerticalId] = useState<string>('');
  const [domainAnalytics, setDomainAnalytics] = useState<OperationalAnalyticsResponse | null>(null);
  const [domainLoading, setDomainLoading] = useState<boolean>(false);

  // Tab 4: Admin Reports
  const [selectedReportType, setSelectedReportType] = useState<'tasks' | 'events' | 'issues' | 'meetings' | 'compliance'>('tasks');
  const [reportVerticalId, setReportVerticalId] = useState<string>('');
  const [complianceDays, setComplianceDays] = useState<number>(7);
  const [adminReport, setAdminReport] = useState<AdminReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState<boolean>(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportRefreshTrigger, setReportRefreshTrigger] = useState<number>(0);

  const canViewAdminReports = hasPermission('reports.admin');

  // Load primary analytics
  useEffect(() => {
    let active = true;
    const fetchPrimaryData = async () => {
      setLoading(true);
      try {
        const [dashRes, indRes, vRes] = await Promise.all([
          analyticsApi.getOperationalDashboard(),
          analyticsApi.getPerformanceIndicators(),
          organizationApi.listVerticals().catch(() => ({ items: [] })),
        ]);
        if (active) {
          setDashboard(dashRes);
          setIndicators(indRes);
          setVerticals(vRes.items || []);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (active) {
          const msg = err instanceof ApiException ? err.message : 'Failed to load operational analytics';
          setErrorMsg(msg);
          setLoading(false);
        }
      }
    };

    fetchPrimaryData();
    return () => {
      active = false;
    };
  }, [refreshTrigger]);

  // Load domain analytics when tab is selected or vertical changes
  useEffect(() => {
    let active = true;
    const fetchDomainData = async () => {
      setDomainLoading(true);
      try {
        const res = await analyticsApi.getOperationalAnalytics({
          vertical_id: selectedVerticalId || undefined,
        });
        if (active) {
          setDomainAnalytics(res);
        }
      } catch {
        if (active) setDomainAnalytics(null);
      } finally {
        if (active) setDomainLoading(false);
      }
    };

    if (activeTab === 'domains') {
      fetchDomainData();
    }
    return () => {
      active = false;
    };
  }, [activeTab, selectedVerticalId, refreshTrigger]);

  // Load admin reports
  useEffect(() => {
    let active = true;
    const loadReport = async () => {
      if (activeTab === 'reports' && canViewAdminReports) {
        setReportLoading(true);
        setReportError(null);

        try {
          let res: AdminReportResponse;
          if (selectedReportType === 'tasks') {
            res = await adminReportsApi.getTaskReport({ vertical_id: reportVerticalId || undefined });
          } else if (selectedReportType === 'events') {
            res = await adminReportsApi.getEventReport();
          } else if (selectedReportType === 'issues') {
            res = await adminReportsApi.getIssueReport();
          } else if (selectedReportType === 'meetings') {
            res = await adminReportsApi.getMeetingReport();
          } else {
            res = await adminReportsApi.getComplianceReport({ days: complianceDays });
          }
          if (active) {
            setAdminReport(res);
          }
        } catch (err: unknown) {
          if (active) {
            const msg = err instanceof ApiException ? err.message : 'Failed to generate administrative report';
            setReportError(msg);
          }
        } finally {
          if (active) {
            setReportLoading(false);
          }
        }
      }
    };

    loadReport();
    return () => {
      active = false;
    };
  }, [activeTab, canViewAdminReports, selectedReportType, reportVerticalId, complianceDays, reportRefreshTrigger]);

  return (
    <AppShell requiredPermission="analytics.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
              <BarChart3 className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              Operational Analytics & Insights
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Live organizational telemetry, department performance indicators, and administrative compliance reporting.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRefreshTrigger((prev) => prev + 1)}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh Telemetry
            </Button>
          </div>
        </div>

        {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 p-1 bg-zinc-100 dark:bg-zinc-800/80 rounded-xl max-w-full overflow-x-auto">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeTab === 'dashboard'
                ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
            }`}
          >
            Operational Dashboard
          </button>

          <button
            onClick={() => setActiveTab('indicators')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeTab === 'indicators'
                ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
            }`}
          >
            Performance Indicators
          </button>

          <button
            onClick={() => setActiveTab('domains')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeTab === 'domains'
                ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
            }`}
          >
            Division Deep-Dive
          </button>

          {canViewAdminReports && (
            <button
              onClick={() => setActiveTab('reports')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'reports'
                  ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                  : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
              }`}
            >
              Administrative Reports
            </button>
          )}
        </div>

        {loading ? (
          <div className="p-16 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : (
          <div>
            {/* ===================================================== */}
            {/* TAB 1: OPERATIONAL DASHBOARD */}
            {/* ===================================================== */}
            {activeTab === 'dashboard' && dashboard && (
              <div className="space-y-6">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                        <Activity className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Active Tasks</span>
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboard.active_tasks}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Completed Tasks</span>
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboard.completed_tasks}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-rose-50 dark:bg-rose-950/60 flex items-center justify-center text-rose-600 dark:text-rose-400">
                        <Clock className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Overdue Tasks</span>
                        <h3 className="text-xl font-bold text-rose-600 dark:text-rose-400">{dashboard.overdue_tasks}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/60 flex items-center justify-center text-amber-600 dark:text-amber-400">
                        <AlertTriangle className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Blocked Tasks</span>
                        <h3 className="text-xl font-bold text-amber-600 dark:text-amber-400">{dashboard.blocked_tasks}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-rose-50 dark:bg-rose-950/60 flex items-center justify-center text-rose-600 dark:text-rose-400">
                        <AlertCircle className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Open Issues</span>
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboard.open_issues}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-rose-50 dark:bg-rose-950/60 flex items-center justify-center text-rose-600 dark:text-rose-400">
                        <TrendingUp className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Escalated Issues</span>
                        <h3 className="text-xl font-bold text-rose-600 dark:text-rose-400">{dashboard.escalated_issues}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-sky-50 dark:bg-sky-950/60 flex items-center justify-center text-sky-600 dark:text-sky-400">
                        <Users className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Upcoming Meetings</span>
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboard.upcoming_meetings}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                        <GitPullRequest className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Requirements</span>
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboard.pending_requirements}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                        <Flag className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Event Readiness</span>
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboard.event_readiness_avg_pct}%</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Report Compliance</span>
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboard.reporting_compliance_pct}%</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/60 flex items-center justify-center text-amber-600 dark:text-amber-400">
                        <ShieldAlert className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Pending Directives</span>
                        <h3 className="text-xl font-bold text-amber-600 dark:text-amber-400">{dashboard.pending_directives}</h3>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                        <Layers className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-2xs font-semibold text-zinc-500 uppercase">Pending Approvals</span>
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboard.outstanding_approvals}</h3>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            )}

            {/* ===================================================== */}
            {/* TAB 2: PERFORMANCE INDICATORS */}
            {/* ===================================================== */}
            {activeTab === 'indicators' && indicators && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { label: 'Task Completion Rate', val: indicators.task_completion_rate_pct, icon: CheckCircle2 },
                  { label: 'Overdue Task Rate', val: indicators.overdue_task_rate_pct, icon: Clock, invert: true },
                  { label: 'Issue Resolution Rate', val: indicators.issue_resolution_rate_pct, icon: AlertCircle },
                  { label: 'Requirement Resolution Rate', val: indicators.requirement_resolution_rate_pct, icon: GitPullRequest },
                  { label: 'Meeting RSVP Acceptance Rate', val: indicators.meeting_rsvp_rate_pct, icon: Users },
                  { label: 'Reporting Compliance Rate', val: indicators.reporting_compliance_rate_pct, icon: FileText },
                  { label: 'Event Readiness Average', val: indicators.event_readiness_avg_pct, icon: Flag },
                  { label: 'Operational Escalation Rate', val: indicators.escalation_rate_pct, icon: TrendingUp, invert: true },
                ].map((ind, i) => {
                  const Icon = ind.icon;
                  const color = ind.invert
                    ? ind.val > 20
                      ? 'text-rose-600'
                      : 'text-emerald-600'
                    : ind.val >= 75
                    ? 'text-emerald-600'
                    : ind.val >= 50
                    ? 'text-indigo-600'
                    : 'text-amber-600';

                  return (
                    <Card key={i} className="p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 flex items-center gap-2">
                          <Icon className="w-4 h-4 text-indigo-500" />
                          {ind.label}
                        </span>
                        <span className={`text-xl font-bold ${color}`}>{ind.val}%</span>
                      </div>

                      <div className="w-full h-2.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all duration-300 ${
                            ind.invert
                              ? ind.val > 20
                                ? 'bg-rose-500'
                                : 'bg-emerald-500'
                              : ind.val >= 75
                              ? 'bg-emerald-500'
                              : ind.val >= 50
                              ? 'bg-indigo-500'
                              : 'bg-amber-500'
                          }`}
                          style={{ width: `${Math.min(ind.val, 100)}%` }}
                        />
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}

            {/* ===================================================== */}
            {/* TAB 3: DIVISION DEEP-DIVE */}
            {/* ===================================================== */}
            {activeTab === 'domains' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-zinc-50 dark:bg-zinc-800/40 rounded-xl border border-zinc-200 dark:border-zinc-800">
                  <span className="text-xs font-bold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider">
                    Select Division / Scope
                  </span>

                  <select
                    value={selectedVerticalId}
                    onChange={(e) => setSelectedVerticalId(e.target.value)}
                    className="h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 min-w-[240px]"
                  >
                    <option value="">All Divisions (Global)</option>
                    {verticals.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name}
                      </option>
                    ))}
                  </select>
                </div>

                {domainLoading ? (
                  <div className="p-16 flex justify-center">
                    <Spinner size="lg" />
                  </div>
                ) : domainAnalytics ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {/* Tasks Summary */}
                    <Card>
                      <CardHeader className="py-3 px-4 border-b border-zinc-100 dark:border-zinc-800 font-bold text-xs flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4 text-indigo-500" /> Master Tasks
                        </span>
                        <span>Total: {domainAnalytics.tasks_total}</span>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Active Tasks:</span>
                          <span className="font-semibold text-zinc-800 dark:text-zinc-200">{domainAnalytics.tasks_active}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Completed:</span>
                          <span className="font-semibold text-emerald-600">{domainAnalytics.tasks_completed}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Overdue:</span>
                          <span className="font-semibold text-rose-600">{domainAnalytics.tasks_overdue}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Completion Rate:</span>
                          <span className="font-bold text-indigo-600">{domainAnalytics.tasks_completion_rate_pct}%</span>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Issues Summary */}
                    <Card>
                      <CardHeader className="py-3 px-4 border-b border-zinc-100 dark:border-zinc-800 font-bold text-xs flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <AlertCircle className="w-4 h-4 text-rose-500" /> Issues & Risks
                        </span>
                        <span>Total: {domainAnalytics.issues_total}</span>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Open Issues:</span>
                          <span className="font-semibold text-rose-600">{domainAnalytics.issues_open}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Escalated:</span>
                          <span className="font-semibold text-rose-600">{domainAnalytics.issues_escalated}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Resolved:</span>
                          <span className="font-semibold text-emerald-600">{domainAnalytics.issues_resolved}</span>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Requirements Summary */}
                    <Card>
                      <CardHeader className="py-3 px-4 border-b border-zinc-100 dark:border-zinc-800 font-bold text-xs flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <GitPullRequest className="w-4 h-4 text-sky-500" /> Requirements
                        </span>
                        <span>Total: {domainAnalytics.requirements_total}</span>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Open:</span>
                          <span className="font-semibold text-zinc-800 dark:text-zinc-200">{domainAnalytics.requirements_open}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">In Progress:</span>
                          <span className="font-semibold text-indigo-600">{domainAnalytics.requirements_in_progress}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Completed:</span>
                          <span className="font-semibold text-emerald-600">{domainAnalytics.requirements_completed}</span>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Events Summary */}
                    <Card>
                      <CardHeader className="py-3 px-4 border-b border-zinc-100 dark:border-zinc-800 font-bold text-xs flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Flag className="w-4 h-4 text-emerald-500" /> Events
                        </span>
                        <span>Total: {domainAnalytics.events_total}</span>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Planning:</span>
                          <span className="font-semibold text-zinc-800 dark:text-zinc-200">{domainAnalytics.events_planning}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">In Progress:</span>
                          <span className="font-semibold text-indigo-600">{domainAnalytics.events_in_progress}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Avg Readiness:</span>
                          <span className="font-bold text-emerald-600">{domainAnalytics.readiness_completed_pct}%</span>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Meetings Summary */}
                    <Card>
                      <CardHeader className="py-3 px-4 border-b border-zinc-100 dark:border-zinc-800 font-bold text-xs flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Users className="w-4 h-4 text-sky-500" /> Meetings
                        </span>
                        <span>Total: {domainAnalytics.meetings_total}</span>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Scheduled:</span>
                          <span className="font-semibold text-zinc-800 dark:text-zinc-200">{domainAnalytics.meetings_scheduled}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Completed:</span>
                          <span className="font-semibold text-emerald-600">{domainAnalytics.meetings_completed}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">RSVP Acceptance:</span>
                          <span className="font-bold text-indigo-600">{domainAnalytics.meetings_rsvp_accepted_pct}%</span>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Work Reports Summary */}
                    <Card>
                      <CardHeader className="py-3 px-4 border-b border-zinc-100 dark:border-zinc-800 font-bold text-xs flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <FileText className="w-4 h-4 text-indigo-500" /> Work Reports
                        </span>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Daily Submitted (7d):</span>
                          <span className="font-bold text-zinc-800 dark:text-zinc-200">{domainAnalytics.daily_reports_submitted_last_7d}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Weekly Submitted (4w):</span>
                          <span className="font-bold text-zinc-800 dark:text-zinc-200">{domainAnalytics.weekly_reports_submitted_last_4w}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Dynamic Forms Total:</span>
                          <span className="font-semibold text-zinc-800 dark:text-zinc-200">{domainAnalytics.forms_total}</span>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                ) : null}
              </div>
            )}

            {/* ===================================================== */}
            {/* TAB 4: ADMINISTRATIVE REPORTS */}
            {/* ===================================================== */}
            {activeTab === 'reports' && canViewAdminReports && (
              <div className="space-y-4">
                <div className="p-4 bg-zinc-50 dark:bg-zinc-800/40 rounded-xl border border-zinc-200 dark:border-zinc-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <select
                      value={selectedReportType}
                      onChange={(e) =>
                        setSelectedReportType(e.target.value as 'tasks' | 'events' | 'issues' | 'meetings' | 'compliance')
                      }
                      className="h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 font-semibold focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="tasks">Task Completion Report</option>
                      <option value="events">Event Readiness Report</option>
                      <option value="issues">Issue Escalation Report</option>
                      <option value="meetings">Meeting Attendance Report</option>
                      <option value="compliance">Reporting Compliance Report</option>
                    </select>

                    {selectedReportType === 'tasks' && (
                      <select
                        value={reportVerticalId}
                        onChange={(e) => setReportVerticalId(e.target.value)}
                        className="h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">All Verticals</option>
                        {verticals.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name}
                          </option>
                        ))}
                      </select>
                    )}

                    {selectedReportType === 'compliance' && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-500">Days:</span>
                        <input
                          type="number"
                          min={1}
                          max={90}
                          value={complianceDays}
                          onChange={(e) => setComplianceDays(Number(e.target.value))}
                          className="w-20 h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 font-mono"
                        />
                      </div>
                    )}
                  </div>

                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setReportRefreshTrigger((p) => p + 1)}
                    isLoading={reportLoading}
                  >
                    Generate Report
                  </Button>
                </div>

                {reportError && <Alert variant="danger">{reportError}</Alert>}

                {reportLoading ? (
                  <div className="p-16 flex justify-center">
                    <Spinner size="lg" />
                  </div>
                ) : adminReport ? (
                  <div className="space-y-4">
                    {/* Summary Card */}
                    <Card>
                      <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-bold text-sm flex items-center justify-between">
                        <span>{adminReport.report_name}</span>
                        <span className="text-xs font-normal text-zinc-400 font-mono">
                          Generated: {new Date(adminReport.generated_at).toLocaleString()}
                        </span>
                      </CardHeader>
                      <CardContent className="p-4">
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                          <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl">
                            <span className="text-zinc-400 block">Total Records</span>
                            <strong className="text-lg text-zinc-900 dark:text-zinc-100 font-bold">
                              {adminReport.total_records}
                            </strong>
                          </div>
                          {Object.entries(adminReport.summary || {}).map(([k, v]) => (
                            <div key={k} className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl">
                              <span className="text-zinc-400 block capitalize">{k.replace(/_/g, ' ')}</span>
                              <strong className="text-lg text-indigo-600 dark:text-indigo-400 font-bold">
                                {String(v)}
                              </strong>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    {/* Records Table */}
                    {adminReport.records.length > 0 && (
                      <Card>
                        <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-xs text-zinc-500 uppercase tracking-wider">
                          Report Line Items ({adminReport.records.length})
                        </CardHeader>
                        <CardContent className="p-0 overflow-x-auto">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-zinc-50 dark:bg-zinc-800/50 text-zinc-500 font-semibold uppercase tracking-wider border-b border-zinc-200 dark:border-zinc-800">
                              <tr>
                                {Object.keys(adminReport.records[0] || {}).map((col) => (
                                  <th key={col} className="py-2.5 px-4 capitalize">
                                    {col.replace(/_/g, ' ')}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                              {adminReport.records.map((row, rIdx) => (
                                <tr key={rIdx} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors">
                                  {Object.entries(row).map(([, val], cIdx) => (
                                    <td key={cIdx} className="py-3 px-4 font-mono text-3xs text-zinc-800 dark:text-zinc-200">
                                      {typeof val === 'object' ? JSON.stringify(val) : String(val ?? '—')}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                ) : null}
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
