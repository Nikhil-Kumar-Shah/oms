'use client';

/**
 * Issues & Escalation Register (/issues)
 * Operational issue tracking with sensitivity controls, vertical scoping, and escalation management.
 */

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { StatusBadge } from '@/components/common/StatusBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { UniversalSelector } from '@/components/ui/UniversalSelector';
import { UniversalAudienceSelector, AudienceItem } from '@/components/ui/UniversalAudienceSelector';
import { UniversalAudienceSelection } from '@/types/organization';
import { useAuth } from '@/providers/AuthProvider';
import { issuesApi, organizationApi, usersApi, ApiException } from '@/lib/api';
import { IssueResponse, IssueCreate, IssueSensitivity, IssueStatus } from '@/types/issue';
import { Vertical, UserSummary } from '@/types/organization';
import {
  AlertTriangle,
  Plus,
  Search,
  Shield,
  Layers,
  ArrowRight,
  X,
  TrendingUp,
  Users,
} from 'lucide-react';

export default function IssuesPage() {
  const { user, hasRole, hasPermission } = useAuth();
  const [issues, setIssues] = useState<IssueResponse[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Search & Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [sensitivityFilter, setSensitivityFilter] = useState<string>('');
  const [verticalFilter, setVerticalFilter] = useState<string>('');

  // Domain data
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [users, setUsers] = useState<UserSummary[]>([]);

  // Create Modal
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Scope & Assignee selections via Universal Selector
  const [scopeItems, setScopeItems] = useState<AudienceItem[]>([]);
  const [scopeValue, setScopeValue] = useState<UniversalAudienceSelection>({});
  const [assigneeItems, setAssigneeItems] = useState<AudienceItem[]>([]);
  const [assigneeValue, setAssigneeValue] = useState<UniversalAudienceSelection>({});

  const [createForm, setCreateForm] = useState<{
    title: string;
    description: string;
    sensitivity: IssueSensitivity;
    action_required: string;
    deadline: string;
  }>({
    title: '',
    description: '',
    sensitivity: 'NORMAL',
    action_required: '',
    deadline: '',
  });

  const canCreate = hasPermission('issues.create');

  useEffect(() => {
    let active = true;
    organizationApi.listVerticals().then((d) => active && setVerticals(d.items)).catch(() => {});
    usersApi.listUsers().then((d) => active && setUsers(d.items)).catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    issuesApi
      .list({
        search: search.trim() || undefined,
        status: (statusFilter as IssueStatus) || undefined,
        sensitivity: (sensitivityFilter as IssueSensitivity) || undefined,
        vertical_id: verticalFilter || undefined,
        limit: 100,
      })
      .then((resp) => {
        if (active) {
          setIssues(resp.items);
          setTotal(resp.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          if (err instanceof ApiException) setErrorMsg(err.message);
          else if (err instanceof Error) setErrorMsg(err.message);
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [search, statusFilter, sensitivityFilter, verticalFilter, refreshTrigger]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.title.trim()) {
      setCreateError('Issue Title * is required.');
      return;
    }
    if (!createForm.description.trim()) {
      setCreateError('Detailed Description * is required.');
      return;
    }

    const vids = scopeValue.vertical_ids || [];
    const hasAudience = scopeValue.include_all || vids.length > 0;
    if (!hasAudience) {
      setCreateError('Audience / Scope * is required. Please select at least one vertical division.');
      return;
    }

    setCreateLoading(true);
    setCreateError(null);

    const payload: IssueCreate = {
      title: createForm.title.trim(),
      description: createForm.description.trim(),
      sensitivity: createForm.sensitivity || 'NORMAL',
      vertical_id: vids.length > 0 ? vids[0] : undefined,
      vertical_ids: vids.length > 0 ? vids : undefined,
      all_users: scopeValue.include_all || false,
      assignee_user_ids: assigneeValue.user_ids?.length ? assigneeValue.user_ids : undefined,
      assignee_role_ids: assigneeValue.role_ids?.length ? assigneeValue.role_ids : undefined,
      assignee_vertical_ids: assigneeValue.vertical_ids?.length ? assigneeValue.vertical_ids : undefined,
      assignee_all_users: assigneeValue.include_all || false,
      deadline: createForm.deadline ? new Date(createForm.deadline).toISOString() : null,
      action_required: createForm.action_required.trim() || null,
      evidence_link: null,
      remarks: null,
    };

    try {
      await issuesApi.create(payload);
      setIsCreateOpen(false);
      setCreateForm({
        title: '',
        description: '',
        sensitivity: 'NORMAL',
        action_required: '',
        deadline: '',
      });
      setScopeItems([]);
      setScopeValue({});
      setAssigneeItems([]);
      setAssigneeValue({});
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setCreateError(err.message);
      else if (err instanceof Error) setCreateError(err.message);
      else setCreateError('An unexpected error occurred while raising the issue.');
    } finally {
      setCreateLoading(false);
    }
  };

  const renderSensitivityBadge = (sensitivity: IssueSensitivity) => {
    switch (sensitivity) {
      case 'CONFIDENTIAL':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-md bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
            <Shield className="w-3 h-3" />
            CONFIDENTIAL
          </span>
        );
      case 'SENSITIVE':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-md bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            SENSITIVE
          </span>
        );
      default:
        return (
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
            NORMAL
          </span>
        );
    }
  };

  return (
    <AppShell requiredPermission="issues.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
              <AlertTriangle className="w-6 h-6 text-amber-500" />
              Issues & Escalation Register
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Operational deficiency tracking, risk logging, and formal vertical escalation channels.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {canCreate && (
              <Button
                variant="primary"
                onClick={() => {
                  setCreateError(null);
                  setIsCreateOpen(true);
                }}
                leftIcon={<Plus className="w-4 h-4" />}
              >
                Raise Issue
              </Button>
            )}
          </div>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Issue Register Notice">
            {errorMsg}
          </Alert>
        )}

        {/* Filters */}
        <Card>
          <CardContent className="p-4 sm:p-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="relative">
                <Input
                  placeholder="Search issues..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  leftIcon={<Search className="w-4 h-4 text-zinc-400" />}
                />
              </div>

              <div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">All Statuses</option>
                  <option value="OPEN">Open</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="ESCALATED">Escalated</option>
                  <option value="RESOLVED">Resolved</option>
                  <option value="CLOSED">Closed</option>
                </select>
              </div>

              <div>
                <select
                  value={sensitivityFilter}
                  onChange={(e) => setSensitivityFilter(e.target.value)}
                  className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">All Sensitivities</option>
                  <option value="NORMAL">Normal</option>
                  <option value="SENSITIVE">Sensitive</option>
                  <option value="CONFIDENTIAL">Confidential</option>
                </select>
              </div>

              <div>
                <select
                  value={verticalFilter}
                  onChange={(e) => setVerticalFilter(e.target.value)}
                  className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">All Verticals</option>
                  {verticals.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Issues List Table */}
        <Card>
          <CardHeader className="py-4 px-6 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between">
            <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Issues ({total})
            </span>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-12 flex justify-center">
                <Spinner size="lg" />
              </div>
            ) : issues.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={AlertTriangle}
                  title="No Issues Reported"
                  description="No operational issues match the active filter criteria."
                  actionLabel={canCreate ? 'Raise New Issue' : undefined}
                  onAction={canCreate ? () => setIsCreateOpen(true) : undefined}
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-zinc-600 dark:text-zinc-300">
                  <thead className="bg-zinc-50 dark:bg-zinc-900/50 text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
                    <tr>
                      <th className="px-6 py-3.5">Issue Title</th>
                      <th className="px-4 py-3.5">Sensitivity</th>
                      <th className="px-4 py-3.5">Status</th>
                      <th className="px-4 py-3.5">Vertical</th>
                      <th className="px-4 py-3.5">Raised By</th>
                      <th className="px-4 py-3.5">Assignee</th>
                      <th className="px-6 py-3.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                    {issues.map((issue) => (
                      <tr
                        key={issue.id}
                        className="hover:bg-zinc-50/70 dark:hover:bg-zinc-900/40 transition-colors"
                      >
                        <td className="px-6 py-4">
                          <div className="space-y-0.5 max-w-sm">
                            <Link
                              href={`/issues/${issue.id}`}
                              className="font-semibold text-zinc-900 dark:text-zinc-100 hover:text-indigo-600 dark:hover:text-indigo-400"
                            >
                              {issue.title}
                            </Link>
                            {issue.status === 'ESCALATED' && issue.escalation_target && (
                              <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1 font-medium">
                                <TrendingUp className="w-3 h-3" />
                                Escalated to: {issue.escalation_target}
                              </p>
                            )}
                            {issue.status === 'RESOLVED' && (
                              <p className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                                Resolved {issue.resolution_date ? `• ${new Date(issue.resolution_date).toLocaleDateString()}` : ''}
                              </p>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          {renderSensitivityBadge(issue.sensitivity)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <StatusBadge status={issue.status} size="sm" />
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-xs">
                          <span className="flex items-center gap-1">
                            <Layers className="w-3 h-3 text-indigo-500" />
                            {issue.vertical_name || 'Organization'}
                          </span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-xs text-zinc-500">
                          {issue.raised_by_username}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-xs">
                          {issue.assignees && issue.assignees.length > 1 ? (
                            <span
                              className="font-medium text-indigo-700 dark:text-indigo-300 flex items-center gap-1.5 cursor-help"
                              title={issue.assignees.map((a) => a.full_name || a.username).join(', ')}
                            >
                              <Users className="w-3.5 h-3.5 text-indigo-500" />
                              {issue.vertical_name ? `${issue.vertical_name} Team` : 'Assigned Team'} ({issue.assignees.length})
                            </span>
                          ) : issue.assignees && issue.assignees.length === 1 ? (
                            <span className="font-medium text-zinc-800 dark:text-zinc-200">
                              {issue.assignees[0].full_name || issue.assignees[0].username}
                            </span>
                          ) : issue.assigned_to_username ? (
                            <span className="font-medium text-zinc-800 dark:text-zinc-200">{issue.assigned_to_username}</span>
                          ) : issue.vertical_name ? (
                            <span className="text-zinc-500 italic">{issue.vertical_name} (Unassigned)</span>
                          ) : (
                            <span className="text-zinc-400 italic">Unassigned</span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right whitespace-nowrap">
                          <Link href={`/issues/${issue.id}`}>
                            <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                              View
                            </Button>
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Raise Issue Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="relative w-[95vw] sm:w-[92vw] md:w-[82vw] lg:w-[72vw] xl:w-[68vw] max-w-5xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden">
              <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between bg-white dark:bg-zinc-900">
                <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-500" />
                  Raise Operational Issue
                </h3>
                <button
                  onClick={() => setIsCreateOpen(false)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreate} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4">
                  {createError && <Alert variant="danger">{createError}</Alert>}

                  {/* 1. Issue Title * */}
                  <Input
                    label="Issue Title *"
                    required
                    placeholder="e.g., Shortage of referee kits for Group B"
                    value={createForm.title}
                    onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                  />

                  {/* 2. Audience / Scope * (Universal Selector) */}
                  <UniversalAudienceSelector
                    label="Audience / Scope *"
                    description="Select the vertical division(s) or scope affected by this issue."
                    placeholder="Select affected vertical division(s)..."
                    required
                    usage="audience"
                    allowAllUsers={hasRole('ADMIN') || hasRole('SPORTS_CORE') || hasRole('DEPUTY_CORE')}
                    allowVerticals={true}
                    allowRoles={false}
                    allowIndividualUsers={false}
                    value={scopeItems}
                    onChange={(items, structured) => {
                      setScopeItems(items);
                      setScopeValue(structured);
                    }}
                  />

                  {/* 3. Sensitivity Level (Optional) */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      Sensitivity Level (Optional)
                    </label>
                    <select
                      value={createForm.sensitivity}
                      onChange={(e) => setCreateForm({ ...createForm, sensitivity: e.target.value as IssueSensitivity })}
                      className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="NORMAL">Normal</option>
                      <option value="SENSITIVE">Sensitive</option>
                      <option value="CONFIDENTIAL">Confidential</option>
                    </select>
                  </div>

                  {/* 4. Detailed Description * */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      Detailed Description <span className="text-rose-500">*</span>
                    </label>
                    <textarea
                      rows={3}
                      required
                      placeholder="Provide full context, affected parties, and impact..."
                      value={createForm.description}
                      onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                      className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  {/* 5. Assignee / Responsible Users (Optional) (Universal Selector) */}
                  <UniversalAudienceSelector
                    label="Assignee / Responsible Users (Optional)"
                    description="Assign to specific members, complete role groups (e.g. Coordinators), or entire verticals."
                    placeholder="Search users by username, full name, email, or select role groups/verticals..."
                    usage="general"
                    allowAllUsers={false}
                    allowVerticals={true}
                    allowRoles={true}
                    allowIndividualUsers={true}
                    value={assigneeItems}
                    onChange={(items, structured) => {
                      setAssigneeItems(items);
                      setAssigneeValue(structured);
                    }}
                  />

                  {/* 6. Deadline (Optional) & 7. Requested Action (Optional) */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Input
                      label="Deadline (Optional)"
                      type="date"
                      value={createForm.deadline}
                      onChange={(e) => setCreateForm({ ...createForm, deadline: e.target.value })}
                    />

                    <Input
                      label="Requested Action (Optional)"
                      placeholder="e.g., Procurement of 10 additional jersey sets"
                      value={createForm.action_required}
                      onChange={(e) => setCreateForm({ ...createForm, action_required: e.target.value })}
                    />
                  </div>
                </div>

                {/* Fixed Footer Action Buttons */}
                <div className="shrink-0 flex justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                  <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" isLoading={createLoading}>
                    Raise Issue
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
