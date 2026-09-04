'use client';

/**
 * Master Tasks Management View (/tasks)
 * Authoritative operational task management with Universal Audience Selector for multi-target assignment.
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
import { PriorityBadge } from '@/components/common/PriorityBadge';
import { HealthIndicator } from '@/components/common/HealthIndicator';
import { TaskTypeBadge } from '@/components/common/TaskTypeBadge';
import { ActiveBadge } from '@/components/common/ActiveBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { UniversalAudienceSelector, AudienceItem } from '@/components/ui/UniversalAudienceSelector';
import { useAuth } from '@/providers/AuthProvider';
import { tasksApi, organizationApi, ApiException } from '@/lib/api';
import { TaskResponse, TaskCreate, TaskPriority, TaskType } from '@/types/task';
import { Vertical, UniversalAudienceSelection } from '@/types/organization';
import {
  Plus,
  Search,
  CheckSquare,
  AlertCircle,
  Calendar,
  Layers,
  ArrowRight,
  X,
  UserCheck,
  User as UserIcon,
  Users,
} from 'lucide-react';

export default function TasksPage() {
  const { user, hasPermission } = useAuth();
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Scope: 'all' | 'my_tasks' | 'created_by_me'
  const [scope, setScope] = useState<'all' | 'my_tasks' | 'created_by_me'>('all');

  // Filters
  const [search, setSearch] = useState<string>('');
  const [taskTypeFilter, setTaskTypeFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [verticalFilter, setVerticalFilter] = useState<string>('');

  // Dropdown Lookups
  const [verticals, setVerticals] = useState<Vertical[]>([]);

  // Create Master Task Modal
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [audienceItems, setAudienceItems] = useState<AudienceItem[]>([]);
  const [audienceSelection, setAudienceSelection] = useState<UniversalAudienceSelection | null>(null);
  const [createForm, setCreateForm] = useState<{
    title: string;
    description: string;
    task_type: TaskType;
    priority: TaskPriority;
    deadline: string;
    remarks: string;
    evidence_link: string;
  }>({
    title: '',
    description: '',
    task_type: 'ROUTINE',
    priority: 'MEDIUM',
    deadline: '',
    remarks: '',
    evidence_link: '',
  });

  const canCreate = hasPermission('tasks.create');

  // Initial lookup load
  useEffect(() => {
    let active = true;
    organizationApi
      .listVerticals()
      .then((data) => {
        if (active) setVerticals(data.items);
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, []);

  // Fetch tasks on filter / scope / refresh change
  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMsg(null);
    tasksApi
      .list({
        search: search.trim() || undefined,
        task_type: (taskTypeFilter as TaskType) || undefined,
        status: (statusFilter as any) || undefined,
        priority: (priorityFilter as TaskPriority) || undefined,
        vertical_id: verticalFilter || undefined,
        scope: scope,
        limit: 100,
      })
      .then((resp) => {
        if (active) {
          setTasks(resp.items);
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
  }, [search, taskTypeFilter, statusFilter, priorityFilter, verticalFilter, scope, refreshTrigger]);

  const openCreateModal = () => {
    setCreateError(null);
    setAudienceItems([]);
    setAudienceSelection(null);
    setCreateForm({
      title: '',
      description: '',
      task_type: 'ROUTINE',
      priority: 'MEDIUM',
      deadline: '',
      remarks: '',
      evidence_link: '',
    });
    setIsCreateOpen(true);
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.title.trim()) {
      setCreateError('Task title is required.');
      return;
    }
    if (!audienceItems || audienceItems.length === 0) {
      setCreateError('Please select at least one target vertical or user assignment.');
      return;
    }

    setCreateLoading(true);
    setCreateError(null);

    const payload: TaskCreate = {
      title: createForm.title.trim(),
      description: createForm.description.trim() || undefined,
      vertical_ids:
        audienceSelection?.vertical_ids && audienceSelection.vertical_ids.length > 0
          ? audienceSelection.vertical_ids
          : undefined,
      user_ids:
        audienceSelection?.user_ids && audienceSelection.user_ids.length > 0
          ? audienceSelection.user_ids
          : undefined,
      role_ids:
        audienceSelection?.role_ids && audienceSelection.role_ids.length > 0
          ? audienceSelection.role_ids
          : undefined,
      include_all: audienceSelection?.include_all || false,
      audience: audienceSelection || undefined,
      task_type: createForm.task_type,
      priority: createForm.priority,
      deadline: createForm.deadline ? new Date(createForm.deadline).toISOString() : undefined,
      remarks: createForm.remarks.trim() || undefined,
      evidence_link: createForm.evidence_link.trim() || undefined,
    };

    try {
      await tasksApi.create(payload);
      setIsCreateOpen(false);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) {
        setCreateError(err.message);
      } else if (err instanceof Error) {
        setCreateError(err.message);
      }
    } finally {
      setCreateLoading(false);
    }
  };

  const isExecutive = user?.roles?.some((r: any) =>
    ['ADMIN', 'SPORTS_CORE', 'DEPUTY_CORE'].includes(typeof r === 'string' ? r : r.name)
  );

  return (
    <AppShell requiredPermission="tasks.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Page Header - Keep ONLY + Create Master Task */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
              <CheckSquare className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              Master Tasks
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Operational tasks register, assignment tracking, and execution lifecycle.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {canCreate && (
              <Button
                variant="primary"
                onClick={openCreateModal}
                leftIcon={<Plus className="w-4 h-4" />}
              >
                Create Master Task
              </Button>
            )}
          </div>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Tasks Notice">
            {errorMsg}
          </Alert>
        )}

        {/* View Scope Tabs */}
        <div className="flex border-b border-zinc-200 dark:border-zinc-800">
          <button
            type="button"
            onClick={() => setScope('all')}
            className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
              scope === 'all'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
            }`}
          >
            <Layers className="w-4 h-4" />
            All Tasks
          </button>
          <button
            type="button"
            onClick={() => setScope('my_tasks')}
            className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
              scope === 'my_tasks'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
            }`}
          >
            <UserCheck className="w-4 h-4" />
            My Tasks
          </button>
          <button
            type="button"
            onClick={() => setScope('created_by_me')}
            className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
              scope === 'created_by_me'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
            }`}
          >
            <Users className="w-4 h-4" />
            Created by Me
          </button>
        </div>

        {/* Filter Toolbar */}
        <Card>
          <CardContent className="p-4 sm:p-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {/* Search */}
              <div className="relative">
                <Input
                  placeholder="Search tasks..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  leftIcon={<Search className="w-4 h-4 text-zinc-400" />}
                />
              </div>

              {/* Task Type Filter */}
              <div>
                <select
                  value={taskTypeFilter}
                  onChange={(e) => setTaskTypeFilter(e.target.value)}
                  aria-label="Filter by task type"
                  className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">All Task Types</option>
                  <option value="ROUTINE">Routine</option>
                  <option value="EVENT">Event</option>
                  <option value="MILESTONE">Milestone</option>
                  <option value="DOCUMENTATION">Documentation</option>
                  <option value="MEETING_FOLLOW_UP">Meeting Follow-up</option>
                </select>
              </div>

              {/* Status Filter */}
              <div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  aria-label="Filter by status"
                  className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">All Statuses</option>
                  <option value="NOT_STARTED">Not Started</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="BLOCKED">Blocked</option>
                  <option value="COMPLETED">Completed</option>
                  <option value="CANCELLED">Cancelled</option>
                </select>
              </div>

              {/* Priority Filter */}
              <div>
                <select
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  aria-label="Filter by priority"
                  className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">All Priorities</option>
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>

              {/* Vertical Filter */}
              <div>
                <select
                  value={verticalFilter}
                  onChange={(e) => setVerticalFilter(e.target.value)}
                  aria-label="Filter by vertical"
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

        {/* Task List / Table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between py-4 px-6 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              {scope === 'my_tasks'
                ? 'My Tasks'
                : scope === 'created_by_me'
                ? 'Created / Delegated Tasks'
                : 'Authorized Tasks'}{' '}
              ({total})
            </span>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-12 flex justify-center">
                <Spinner size="lg" />
              </div>
            ) : tasks.length === 0 ? (
              <div className="p-12">
                <EmptyState
                  icon={CheckSquare}
                  title="No Tasks Found"
                  description={
                    search || statusFilter || priorityFilter || taskTypeFilter || verticalFilter
                      ? 'No tasks matched your active filter criteria.'
                      : 'No operational tasks registered in your authorized scope.'
                  }
                  actionLabel={
                    scope === 'my_tasks'
                      ? 'Go to My Work'
                      : canCreate
                      ? 'Create Master Task'
                      : undefined
                  }
                  onAction={
                    scope === 'my_tasks'
                      ? () => (window.location.href = '/my-work')
                      : canCreate
                      ? openCreateModal
                      : undefined
                  }
                  actionIcon={scope === 'my_tasks' ? <ArrowRight className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-zinc-600 dark:text-zinc-300">
                  <thead className="bg-zinc-50 dark:bg-zinc-900/50 text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
                    <tr>
                      <th className="px-6 py-3.5">Task & Vertical</th>
                      <th className="px-4 py-3.5">Assigned To</th>
                      <th className="px-4 py-3.5">Created By</th>
                      <th className="px-4 py-3.5">Priority</th>
                      <th className="px-4 py-3.5">Status</th>
                      <th className="px-4 py-3.5">Active</th>
                      <th className="px-4 py-3.5">Health</th>
                      <th className="px-4 py-3.5">Progress</th>
                      <th className="px-4 py-3.5">Deadline</th>
                      <th className="px-6 py-3.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                    {tasks.map((task) => (
                      <tr
                        key={task.id}
                        className="hover:bg-zinc-50/70 dark:hover:bg-zinc-900/40 transition-colors group"
                      >
                        <td className="px-6 py-4">
                          <div className="space-y-1 max-w-sm">
                            <Link
                              href={`/tasks/${task.id}?from=master-tasks`}
                              className="font-semibold text-zinc-900 dark:text-zinc-100 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center gap-1.5"
                            >
                              {task.title}
                              {task.blockers && (
                                <span title={`Blocker: ${task.blockers}`} className="text-rose-500">
                                  <AlertCircle className="w-3.5 h-3.5" />
                                </span>
                              )}
                            </Link>
                            <div className="flex items-center gap-2 text-xs text-zinc-500">
                              <span className="flex items-center gap-1">
                                <Layers className="w-3 h-3 text-indigo-500" />
                                {task.vertical_name || 'Organization'}
                              </span>
                              <span>•</span>
                              <TaskTypeBadge type={task.task_type} size="sm" />
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          {task.assigned_to_name || task.assigned_to_username ? (
                            <div className="flex items-center gap-1.5">
                              <UserCheck className="w-3.5 h-3.5 text-indigo-500" />
                              <span className="font-medium text-zinc-900 dark:text-zinc-100">
                                {task.assigned_to_name || task.assigned_to_username}
                              </span>
                              {task.assigned_to_id === user?.id && (
                                <span className="text-[10px] bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 font-semibold px-1.5 py-0.5 rounded">
                                  You
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-zinc-400 italic">Unassigned</span>
                          )}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-xs text-zinc-500">
                          {task.assigned_by_username ? (
                            <div className="flex items-center gap-1">
                              <UserIcon className="w-3.5 h-3.5 text-zinc-400" />
                              <span>{task.assigned_by_username}</span>
                              {task.assigned_by_id === user?.id && (
                                <span className="text-[10px] bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 font-semibold px-1.5 py-0.5 rounded">
                                  You
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-zinc-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <PriorityBadge priority={task.priority} size="sm" />
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <StatusBadge status={task.status} size="sm" />
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <ActiveBadge status={task.status} size="sm" />
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <HealthIndicator health={task.health} size="sm" />
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-2 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
                              <div
                                className="h-full bg-indigo-600 rounded-full transition-all"
                                style={{ width: `${task.completion_percentage}%` }}
                              />
                            </div>
                            <span className="text-xs font-mono">{task.completion_percentage}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-xs text-zinc-500">
                          {task.deadline ? (
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3.5 h-3.5 text-zinc-400" />
                              {new Date(task.deadline).toLocaleDateString()}
                            </span>
                          ) : (
                            <span className="text-zinc-400">—</span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right whitespace-nowrap">
                          <Link href={`/tasks/${task.id}?from=master-tasks`}>
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

        {/* Create Master Task Modal with UniversalAudienceSelector */}
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div
              className="relative w-[95vw] sm:w-[92vw] md:w-[82vw] lg:w-[72vw] xl:w-[68vw] max-w-5xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden"
              role="dialog"
              aria-modal="true"
            >
              <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between bg-white dark:bg-zinc-900">
                <div>
                  <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                    <CheckSquare className="w-5 h-5 text-indigo-600" />
                    Create Master Task
                  </h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                    Delegate operational tasks across verticals, groups, or specific team members.
                  </p>
                </div>
                <button
                  onClick={() => setIsCreateOpen(false)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreateTask} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4">
                  {createError && (
                    <Alert variant="danger" title="Validation Error">
                      {createError}
                    </Alert>
                  )}

                  {/* Title (Required) */}
                  <Input
                    label="Task Title *"
                    required
                    placeholder="e.g., Prepare pitch inspection report"
                    value={createForm.title}
                    onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                  />

                  {/* Single Reusable Universal Audience Selector replacing separate Vertical + Assignee */}
                  <UniversalAudienceSelector
                    label="Target Assignment / Audience *"
                    required
                    placeholder="Select vertical(s), user(s), or role group..."
                    usage="assignment"
                    allowAllUsers={isExecutive}
                    allowVerticals={true}
                    allowRoles={true}
                    allowIndividualUsers={true}
                    showResolvedPreview={true}
                    value={audienceItems}
                    onChange={(items, structuredValue) => {
                      setAudienceItems(items);
                      setAudienceSelection(structuredValue);
                      setCreateError(null);
                    }}
                  />

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {/* Task Type (Optional) */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Task Type</label>
                      <select
                        value={createForm.task_type}
                        onChange={(e) => setCreateForm({ ...createForm, task_type: e.target.value as TaskType })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="ROUTINE">Routine</option>
                        <option value="EVENT">Event</option>
                        <option value="MILESTONE">Milestone</option>
                        <option value="DOCUMENTATION">Documentation</option>
                        <option value="MEETING_FOLLOW_UP">Meeting Follow-Up</option>
                      </select>
                    </div>

                    {/* Priority (Optional) */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Priority</label>
                      <select
                        value={createForm.priority}
                        onChange={(e) => setCreateForm({ ...createForm, priority: e.target.value as TaskPriority })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="LOW">Low</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="HIGH">High</option>
                        <option value="CRITICAL">Critical</option>
                      </select>
                    </div>

                    {/* Deadline (Optional) */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Deadline</label>
                      <Input
                        type="date"
                        value={createForm.deadline}
                        onChange={(e) => setCreateForm({ ...createForm, deadline: e.target.value })}
                      />
                    </div>
                  </div>

                  {/* Description (Optional) */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Description</label>
                    <textarea
                      rows={3}
                      placeholder="Task details and deliverables..."
                      value={createForm.description}
                      onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                      className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Evidence Link (Optional) */}
                    <Input
                      label="Evidence Link"
                      placeholder="https://..."
                      value={createForm.evidence_link}
                      onChange={(e) => setCreateForm({ ...createForm, evidence_link: e.target.value })}
                    />
                    {/* Remarks (Optional) */}
                    <Input
                      label="Remarks"
                      placeholder="Additional context..."
                      value={createForm.remarks}
                      onChange={(e) => setCreateForm({ ...createForm, remarks: e.target.value })}
                    />
                  </div>
                </div>

                {/* Fixed Footer Action Buttons */}
                <div className="shrink-0 flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsCreateOpen(false)}
                    disabled={createLoading}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={createLoading || !createForm.title.trim()}
                  >
                    {createLoading ? 'Creating Task...' : 'Create Task'}
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
