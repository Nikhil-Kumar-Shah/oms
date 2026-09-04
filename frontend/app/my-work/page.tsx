'use client';

/**
 * Personal Operational Workspace & My Tasks (/my-work)
 * Server-filtered personal projection consuming GET /api/v1/workspace/my-work.
 * Features dedicated "+ Create My Task" workflow automatically assigned to authenticated user.
 */

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
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
import { WorkspaceStats } from '@/components/workspace/WorkspaceStats';
import { useAuth } from '@/providers/AuthProvider';
import { workspaceApi, tasksApi, ApiException } from '@/lib/api';
import { UnifiedMyWorkResponse, MyWorkTaskItem, MyWorkMeetingItem } from '@/types/workspace';
import { TaskCreate, TaskPriority, TaskType, TaskStatus } from '@/types/task';
import {
  Briefcase,
  AlertOctagon,
  CheckCircle,
  Clock,
  ArrowRight,
  RefreshCw,
  Users,
  Layers,
  Plus,
  UserCheck,
  X,
  Play,
} from 'lucide-react';

export type WorkspaceTab = 'my_tasks' | 'completed' | 'created_by_me' | 'overdue' | 'blocked' | 'meetings';

function MyWorkContent() {
  const { user, hasPermission, hasRole } = useAuth();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get('tab');

  const [myWork, setMyWork] = useState<UnifiedMyWorkResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('my_tasks');
  const [transitioningTaskId, setTransitioningTaskId] = useState<string | null>(null);

  useEffect(() => {
    if (tabParam === 'completed') {
      setActiveTab('completed');
    } else if (tabParam === 'created_by_me' || tabParam === 'created-by-me') {
      setActiveTab('created_by_me');
    } else if (tabParam === 'overdue') {
      setActiveTab('overdue');
    } else if (tabParam === 'blocked') {
      setActiveTab('blocked');
    } else if (tabParam === 'meetings') {
      setActiveTab('meetings');
    } else if (tabParam === 'my_tasks' || tabParam === 'tasks') {
      setActiveTab('my_tasks');
    }
  }, [tabParam]);

  // Create My Task Modal
  const [isMyTaskOpen, setIsMyTaskOpen] = useState<boolean>(false);
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
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

  useEffect(() => {
    let active = true;
    workspaceApi
      .getMyWork()
      .then((data) => {
        if (active) {
          setMyWork(data);
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
  }, [refreshTrigger]);

  const handleQuickTransition = async (taskId: string, status: TaskStatus, percentage?: number) => {
    let completion_percentage = percentage;
    if (completion_percentage === undefined) {
      if (status === 'COMPLETED') completion_percentage = 100;
      else if (status === 'NOT_STARTED') completion_percentage = 0;
      else if (status === 'IN_PROGRESS') completion_percentage = 25;
    }

    setTransitioningTaskId(taskId);
    try {
      await tasksApi.transition(taskId, {
        status,
        completion_percentage,
        blockers: status === 'BLOCKED' ? 'Impediment reported by assignee' : undefined,
      });
      // Fresh server GET
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(err.message);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setTransitioningTaskId(null);
    }
  };

  const openCreateMyTaskModal = () => {
    setCreateError(null);
    setCreateForm({
      title: '',
      description: '',
      task_type: 'ROUTINE',
      priority: 'MEDIUM',
      deadline: '',
      remarks: '',
      evidence_link: '',
    });
    setIsMyTaskOpen(true);
  };

  const handleCreateMyTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.title.trim()) {
      setCreateError('Task title is required.');
      return;
    }

    setCreateLoading(true);
    setCreateError(null);

    const primaryVertId = user?.verticals?.find((v) => v.is_primary)?.id || user?.verticals?.[0]?.id;
    const payload: TaskCreate = {
      title: createForm.title.trim(),
      description: createForm.description.trim() || undefined,
      vertical_id: primaryVertId || undefined,
      is_self_task: true,
      task_type: createForm.task_type,
      priority: createForm.priority,
      deadline: createForm.deadline ? new Date(createForm.deadline).toISOString() : undefined,
      remarks: createForm.remarks.trim() || undefined,
      evidence_link: createForm.evidence_link.trim() || undefined,
    };

    try {
      await tasksApi.createSelfTask(payload);
      setIsMyTaskOpen(false);
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

  const tasks: MyWorkTaskItem[] = myWork?.tasks || [];
  const completedTasks: MyWorkTaskItem[] = myWork?.completed_tasks || [];
  const createdByMeTasks: MyWorkTaskItem[] = myWork?.created_by_me_tasks || [];
  const overdueTasks: MyWorkTaskItem[] = myWork?.overdue || [];
  const blockedTasks: MyWorkTaskItem[] = myWork?.blockers || [];
  const meetings: MyWorkMeetingItem[] = myWork?.meetings || [];

  const canViewMasterTasks =
    hasPermission('tasks.read') ||
    hasRole('ADMIN') ||
    hasRole('SPORTS_CORE') ||
    hasRole('COORDINATOR') ||
    hasRole('SUPER_COORDINATOR');

  const tabs: Array<{ id: WorkspaceTab; label: string }> = [
    { id: 'my_tasks', label: `My Tasks (${tasks.length})` },
    { id: 'completed', label: `Completed Tasks (${completedTasks.length})` },
    { id: 'created_by_me', label: `Created by Me (${createdByMeTasks.length})` },
    { id: 'overdue', label: `Overdue (${overdueTasks.length})` },
    { id: 'blocked', label: `Blocked (${blockedTasks.length})` },
    { id: 'meetings', label: `Meetings (${meetings.length})` },
  ];

  const renderTaskRow = (task: MyWorkTaskItem, fromContext: 'my-tasks' | 'completed' | 'created-by-me') => (
    <div
      key={task.id}
      className="p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:bg-zinc-50 dark:hover:bg-zinc-900/50 transition-colors"
    >
      <div className="space-y-2 flex-1 min-w-0">
        {/* Title & Dimensional Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/tasks/${task.id}?from=${fromContext}`}
            className="font-semibold text-zinc-900 dark:text-zinc-100 hover:text-indigo-600 dark:hover:text-indigo-400 truncate max-w-md"
          >
            {task.title}
          </Link>
          <TaskTypeBadge type={task.task_type} size="sm" />
          <PriorityBadge priority={task.priority} size="sm" />
          <StatusBadge status={task.status} size="sm" />
          <ActiveBadge status={task.status} size="sm" />
          <HealthIndicator health={task.health} size="sm" />
        </div>

        {/* Context & Metadata */}
        <div className="flex flex-wrap items-center gap-2.5 text-xs text-zinc-500">
          <span className="flex items-center gap-1">
            <Layers className="w-3 h-3 text-indigo-500" />
            {task.vertical_name || 'Organization'}
          </span>
          {fromContext === 'created-by-me' && (
            <>
              <span>•</span>
              <span className="flex items-center gap-1 text-zinc-700 dark:text-zinc-300 font-medium">
                <UserCheck className="w-3 h-3 text-indigo-500" />
                Assigned to: <strong>{task.assigned_to_name || task.assigned_to_username || 'Unassigned'}</strong>
              </span>
            </>
          )}
          {task.deadline && (
            <>
              <span>•</span>
              <span className="flex items-center gap-1 text-zinc-600 dark:text-zinc-400">
                <Clock className="w-3 h-3" />
                Due: {new Date(task.deadline).toLocaleDateString()}
              </span>
            </>
          )}
          {task.blocker_reason && (
            <>
              <span>•</span>
              <span className="text-rose-600 dark:text-rose-400 font-medium">
                Blocker: {task.blocker_reason}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Interactive Status Transition & Operational Options */}
      <div className="flex flex-wrap items-center gap-2 self-start lg:self-center shrink-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-zinc-500 font-medium hidden sm:inline">Status:</span>
          <select
            value={task.status === 'TODO' ? 'NOT_STARTED' : task.status}
            onChange={(e) => handleQuickTransition(task.id, e.target.value as TaskStatus)}
            disabled={transitioningTaskId === task.id}
            aria-label="Update task status"
            className="text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 hover:border-indigo-500 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 cursor-pointer transition-colors shadow-2xs"
          >
            <option value="NOT_STARTED">Not Started</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="BLOCKED">Blocked</option>
            <option value="COMPLETED">Completed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>

        {/* Quick Shortcut Buttons */}
        {(task.status === 'TODO' || (task.status as string) === 'NOT_STARTED') && (
          <Button
            size="sm"
            variant="primary"
            onClick={() => handleQuickTransition(task.id, 'IN_PROGRESS', 25)}
            isLoading={transitioningTaskId === task.id}
            leftIcon={<Play className="w-3.5 h-3.5" />}
          >
            Start
          </Button>
        )}
        {task.status === 'IN_PROGRESS' && (
          <Button
            size="sm"
            variant="primary"
            onClick={() => handleQuickTransition(task.id, 'COMPLETED', 100)}
            isLoading={transitioningTaskId === task.id}
            leftIcon={<CheckCircle className="w-3.5 h-3.5" />}
          >
            Complete
          </Button>
        )}
        {task.status === 'COMPLETED' && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleQuickTransition(task.id, 'IN_PROGRESS', 50)}
            isLoading={transitioningTaskId === task.id}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Reopen
          </Button>
        )}
        <Link href={`/tasks/${task.id}?from=${fromContext}`}>
          <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
            Details
          </Button>
        </Link>
      </div>
    </div>
  );

  return (
    <AppShell isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Page Header with Dedicated Create My Task */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
              <Briefcase className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              My Work & Tasks
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Personal operational projection: your assigned tasks and upcoming meetings.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRefreshTrigger((p) => p + 1)}
              isLoading={loading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Sync Work
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={openCreateMyTaskModal}
              leftIcon={<UserCheck className="w-4 h-4 text-emerald-300" />}
            >
              Create My Task
            </Button>
          </div>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Workspace Sync Notice">
            {errorMsg}
          </Alert>
        )}

        {/* Live Counters */}
        <WorkspaceStats stats={myWork?.stats} isLoading={loading} />

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 p-1 bg-zinc-100 dark:bg-zinc-800/80 rounded-xl max-w-full overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                  : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="p-16 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* My Tasks (Active) */}
            {activeTab === 'my_tasks' && (
              <Card>
                <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm flex items-center justify-between">
                  <span>Assigned Active Tasks ({tasks.length})</span>
                  {canViewMasterTasks && (
                    <Link href="/tasks" className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline">
                      View Master Tasks →
                    </Link>
                  )}
                </CardHeader>
                <CardContent className="p-0 divide-y divide-zinc-200 dark:divide-zinc-800">
                  {tasks.length === 0 ? (
                    <div className="p-8">
                      <EmptyState
                        icon={CheckCircle}
                        title="No Active Tasks"
                        description="You are completely up to date. No pending tasks assigned."
                        actionLabel="Create My Task"
                        onAction={openCreateMyTaskModal}
                      />
                    </div>
                  ) : (
                    tasks.map((task) => renderTaskRow(task, 'my-tasks'))
                  )}
                </CardContent>
              </Card>
            )}

            {/* Completed Tasks */}
            {activeTab === 'completed' && (
              <Card>
                <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm flex items-center justify-between">
                  <span>Completed Tasks ({completedTasks.length})</span>
                  {canViewMasterTasks && (
                    <Link href="/tasks" className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline">
                      View Master Tasks →
                    </Link>
                  )}
                </CardHeader>
                <CardContent className="p-0 divide-y divide-zinc-200 dark:divide-zinc-800">
                  {completedTasks.length === 0 ? (
                    <div className="p-8">
                      <EmptyState
                        icon={CheckCircle}
                        title="No Completed Tasks"
                        description="You haven't completed any assigned tasks yet."
                      />
                    </div>
                  ) : (
                    completedTasks.map((task) => renderTaskRow(task, 'completed'))
                  )}
                </CardContent>
              </Card>
            )}

            {/* Created by Me */}
            {activeTab === 'created_by_me' && (
              <Card>
                <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm flex items-center justify-between">
                  <span>Tasks Created by You ({createdByMeTasks.length})</span>
                  {canViewMasterTasks && (
                    <Link href="/tasks" className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline">
                      View Master Tasks →
                    </Link>
                  )}
                </CardHeader>
                <CardContent className="p-0 divide-y divide-zinc-200 dark:divide-zinc-800">
                  {createdByMeTasks.length === 0 ? (
                    <div className="p-8">
                      <EmptyState
                        icon={CheckCircle}
                        title="No Tasks Created by You"
                        description="You haven't created or delegated any tasks yet."
                        actionLabel="Create My Task"
                        onAction={openCreateMyTaskModal}
                      />
                    </div>
                  ) : (
                    createdByMeTasks.map((task) => renderTaskRow(task, 'created-by-me'))
                  )}
                </CardContent>
              </Card>
            )}

            {/* Overdue Items */}
            {activeTab === 'overdue' && (
              <Card className="border-rose-200 dark:border-rose-900/50">
                <CardHeader className="py-3 px-5 bg-rose-50/50 dark:bg-rose-950/20 border-b border-rose-100 dark:border-rose-900/40 font-semibold text-sm text-rose-700 dark:text-rose-400 flex items-center gap-2">
                  <AlertOctagon className="w-4 h-4" />
                  Overdue Operational Items ({overdueTasks.length})
                </CardHeader>
                <CardContent className="p-0 divide-y divide-rose-100 dark:divide-rose-900/30">
                  {overdueTasks.length === 0 ? (
                    <div className="p-8">
                      <EmptyState
                        icon={CheckCircle}
                        title="No Overdue Tasks"
                        description="Great job! All your assigned tasks are on schedule."
                      />
                    </div>
                  ) : (
                    overdueTasks.map((t) => (
                      <div key={t.id} className="p-4 flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Link href={`/tasks/${t.id}?from=my-tasks`} className="font-semibold text-sm text-zinc-900 dark:text-zinc-100 hover:underline">
                            {t.title}
                          </Link>
                          <p className="text-xs text-rose-600 dark:text-rose-400">
                            Deadline passed: {t.deadline ? new Date(t.deadline).toLocaleDateString() : 'N/A'}
                          </p>
                        </div>
                        <Link href={`/tasks/${t.id}?from=my-tasks`}>
                          <Button size="sm" variant="danger">Resolve</Button>
                        </Link>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            )}

            {/* Blocked Items */}
            {activeTab === 'blocked' && (
              <Card className="border-amber-200 dark:border-amber-900/50">
                <CardHeader className="py-3 px-5 bg-amber-50/50 dark:bg-amber-950/20 border-b border-amber-100 dark:border-amber-900/40 font-semibold text-sm text-amber-700 dark:text-amber-400 flex items-center gap-2">
                  <AlertOctagon className="w-4 h-4" />
                  Blocked Tasks Requiring Attention ({blockedTasks.length})
                </CardHeader>
                <CardContent className="p-0 divide-y divide-amber-100 dark:divide-amber-900/30">
                  {blockedTasks.length === 0 ? (
                    <div className="p-8">
                      <EmptyState
                        icon={CheckCircle}
                        title="No Blocked Tasks"
                        description="No tasks are currently reported as blocked."
                      />
                    </div>
                  ) : (
                    blockedTasks.map((t) => (
                      <div key={t.id} className="p-4 flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Link href={`/tasks/${t.id}?from=my-tasks`} className="font-semibold text-sm text-zinc-900 dark:text-zinc-100 hover:underline">
                            {t.title}
                          </Link>
                          <p className="text-xs text-amber-600 dark:text-amber-400">
                            Blocker: {t.blocker_reason || 'Unspecified impediment'}
                          </p>
                        </div>
                        <Link href={`/tasks/${t.id}?from=my-tasks`}>
                          <Button size="sm" variant="outline">Unblock</Button>
                        </Link>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            )}

            {/* Upcoming Meetings */}
            {activeTab === 'meetings' && (
              <Card>
                <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm flex items-center gap-2">
                  <Users className="w-4 h-4 text-indigo-500" />
                  Upcoming Meetings ({meetings.length})
                </CardHeader>
                <CardContent className="p-0 divide-y divide-zinc-200 dark:divide-zinc-800">
                  {meetings.length === 0 ? (
                    <div className="p-8">
                      <EmptyState
                        icon={Users}
                        title="No Upcoming Meetings"
                        description="You have no scheduled meetings at this time."
                      />
                    </div>
                  ) : (
                    meetings.map((m) => (
                      <div key={m.id} className="p-4 flex items-center justify-between">
                        <div className="space-y-0.5">
                          <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{m.title}</h4>
                          <p className="text-xs text-zinc-500">
                            {m.meeting_date} {m.start_time ? `at ${m.start_time}` : ''} • {m.location || 'Online'}
                          </p>
                        </div>
                        <Link href="/meetings">
                          <Button size="sm" variant="outline">RSVP</Button>
                        </Link>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Create My Task Modal */}
        {isMyTaskOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div
              className="relative w-[95vw] sm:w-[92vw] md:w-[82vw] lg:w-[72vw] xl:w-[68vw] max-w-5xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden"
              role="dialog"
              aria-modal="true"
            >
              <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between bg-white dark:bg-zinc-900">
                <div>
                  <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                    <UserCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                    Create My Task
                  </h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                    Create a personal operational task automatically assigned to you.
                  </p>
                </div>
                <button
                  onClick={() => setIsMyTaskOpen(false)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreateMyTask} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4">
                  {createError && (
                    <Alert variant="danger" title="Validation Error">
                      {createError}
                    </Alert>
                  )}

                  {/* Task Title (Required) */}
                  <Input
                    label="Task Title *"
                    required
                    placeholder="e.g., Update cricket inventory log"
                    value={createForm.title}
                    onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                  />

                  {/* Self-Assignment Card - Automatic self-assignment without vertical selection */}
                  <div className="p-3.5 bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900/50 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-indigo-100 dark:indigo-900/60 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0">
                        <UserCheck className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Assignment Scope</div>
                        <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                          <span>Self-Assigned to You</span>
                          <span className="text-xs text-zinc-500 font-mono">(@{user?.username || 'current_user'})</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {user?.verticals && user.verticals.length > 0 && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700 shadow-2xs">
                          <Layers className="w-3 h-3 text-indigo-500" />
                          {user.verticals.find((v) => v.is_primary)?.name || user.verticals[0]?.name}
                        </span>
                      )}
                      <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/40">
                        Self-Task
                      </span>
                    </div>
                  </div>

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
                      placeholder="Task deliverables and personal notes..."
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
                    onClick={() => setIsMyTaskOpen(false)}
                    disabled={createLoading}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={createLoading || !createForm.title.trim()}
                  >
                    {createLoading ? 'Creating Task...' : 'Create My Task'}
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

export default function MyWorkPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950">
          <Spinner size="lg" className="text-indigo-600 dark:text-indigo-400" />
        </div>
      }
    >
      <MyWorkContent />
    </React.Suspense>
  );
}
