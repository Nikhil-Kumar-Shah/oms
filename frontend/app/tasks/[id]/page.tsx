'use client';

/**
 * Task Details & Lifecycle Management (/tasks/[id])
 * Detailed task view, status transitions, reassignment, comments, and immutable history.
 */

import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
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
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { ErrorView } from '@/components/ui/ErrorView';
import { UserSelector } from '@/components/selectors';
import { useAuth } from '@/hooks/useAuth';
import { tasksApi, organizationApi, ApiException } from '@/lib/api';
import {
  TaskResponse,
  TaskCommentResponse,
  TaskHistoryResponse,
  TaskStatus,
} from '@/types/task';
import {
  Calendar,
  Layers,
  ArrowLeft,
  Play,
  CheckCircle,
  AlertOctagon,
  Unlock,
  TrendingUp,
  MessageSquare,
  History,
  Send,
  UserCheck,
  ExternalLink,
} from 'lucide-react';

function TaskDetailContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const fromParam = searchParams.get('from');
  const taskId = params.id as string;

  const { user, hasPermission, hasRole } = useAuth();
  const [task, setTask] = useState<TaskResponse | null>(null);
  const [comments, setComments] = useState<TaskCommentResponse[]>([]);
  const [history, setHistory] = useState<TaskHistoryResponse[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Comment state
  const [commentInput, setCommentInput] = useState<string>('');
  const [commentLoading, setCommentLoading] = useState<boolean>(false);

  // Transition & Action modals
  const [activeModal, setActiveModal] = useState<
    'start' | 'complete' | 'block' | 'unblock' | 'escalate' | 'reassign' | null
  >(null);
  const [modalLoading, setModalLoading] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Form states for modals
  const [blockerText, setBlockerText] = useState<string>('');
  const [unblockResolution, setUnblockResolution] = useState<string>('');
  const [escalateReason, setEscalateReason] = useState<string>('');
  const [reassignUserId, setReassignUserId] = useState<string>('');

  const canTransition = hasPermission('tasks.transition');
  const canReassign = hasPermission('tasks.assign');

  useEffect(() => {
    let active = true;
    if (taskId) {
      Promise.all([
        tasksApi.getById(taskId),
        tasksApi.listComments(taskId),
        tasksApi.listHistory(taskId),
      ])
        .then(([taskData, commentsData, historyData]) => {
          if (active) {
            setTask(taskData);
            setComments(commentsData);
            setHistory(historyData);
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
    }
    return () => {
      active = false;
    };
  }, [taskId, refreshTrigger]);

  const handleStatusTransition = async (status: TaskStatus, percentage?: number) => {
    setModalLoading(true);
    setModalError(null);
    try {
      await tasksApi.transition(taskId, {
        status,
        completion_percentage: percentage,
      });
      setActiveModal(null);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleBlockTask = async () => {
    if (!blockerText.trim()) {
      setModalError('Blocker description is required.');
      return;
    }
    setModalLoading(true);
    setModalError(null);
    try {
      await tasksApi.block(taskId, { blocker_description: blockerText.trim() });
      setActiveModal(null);
      setBlockerText('');
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleUnblockTask = async () => {
    setModalLoading(true);
    setModalError(null);
    try {
      await tasksApi.unblock(taskId, { resolution: unblockResolution.trim() || undefined });
      setActiveModal(null);
      setUnblockResolution('');
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleEscalateTask = async () => {
    if (!escalateReason.trim()) {
      setModalError('Escalation reason is required.');
      return;
    }
    setModalLoading(true);
    setModalError(null);
    try {
      await tasksApi.escalate(taskId, { reason: escalateReason.trim() });
      setActiveModal(null);
      setEscalateReason('');
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleReassignTask = async () => {
    if (!reassignUserId) {
      setModalError('Please select a target assignee.');
      return;
    }
    setModalLoading(true);
    setModalError(null);
    try {
      await tasksApi.reassign(taskId, { new_assigned_to_id: reassignUserId });
      setActiveModal(null);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentInput.trim()) return;

    setCommentLoading(true);
    try {
      await tasksApi.addComment(taskId, { content: commentInput.trim() });
      setCommentInput('');
      const updatedComments = await tasksApi.listComments(taskId);
      setComments(updatedComments);
    } catch (err) {
      if (err instanceof ApiException) setErrorMsg(err.message);
    } finally {
      setCommentLoading(false);
    }
  };

  // Determine authorized navigation context
  const canAccessMasterTasks =
    hasPermission('tasks.read') ||
    hasRole('ADMIN') ||
    hasRole('SPORTS_CORE') ||
    hasRole('COORDINATOR') ||
    hasRole('SUPER_COORDINATOR');

  let navContext: 'my_tasks' | 'completed' | 'created_by_me' | 'master_tasks' = 'my_tasks';

  if (fromParam === 'completed') {
    navContext = 'completed';
  } else if (fromParam === 'created-by-me' || fromParam === 'created_by_me') {
    navContext = 'created_by_me';
  } else if (fromParam === 'master-tasks' || fromParam === 'tasks') {
    // If user lacks master tasks permission, NEVER route or link to master tasks
    navContext = canAccessMasterTasks ? 'master_tasks' : 'my_tasks';
  } else if (fromParam === 'my-tasks' || fromParam === 'my-work') {
    navContext = 'my_tasks';
  } else {
    // Default fallback based on permissions and relationship
    if (!canAccessMasterTasks || task?.assigned_to_id === user?.id) {
      navContext = task?.status === 'COMPLETED' ? 'completed' : 'my_tasks';
    } else if (task?.assigned_by_id === user?.id && !canAccessMasterTasks) {
      navContext = 'created_by_me';
    } else {
      navContext = canAccessMasterTasks ? 'master_tasks' : 'my_tasks';
    }
  }

  let customCrumbs: Array<{ label: string; href?: string }>;
  let backHref: string;
  let backLabel: string;

  if (navContext === 'completed') {
    customCrumbs = [
      { label: 'My Tasks', href: '/my-tasks' },
      { label: 'Completed Tasks', href: '/my-tasks?tab=completed' },
      { label: task?.title || 'Task Details' },
    ];
    backHref = '/my-tasks?tab=completed';
    backLabel = 'Back to Completed Tasks';
  } else if (navContext === 'created_by_me') {
    customCrumbs = [
      { label: 'My Tasks', href: '/my-tasks' },
      { label: 'Created by Me', href: '/my-tasks?tab=created_by_me' },
      { label: task?.title || 'Task Details' },
    ];
    backHref = '/my-tasks?tab=created_by_me';
    backLabel = 'Back to Created by Me';
  } else if (navContext === 'master_tasks') {
    customCrumbs = [
      { label: 'Master Tasks', href: '/tasks' },
      { label: task?.title || 'Task Details' },
    ];
    backHref = '/tasks';
    backLabel = 'Back to Master Tasks';
  } else {
    customCrumbs = [
      { label: 'My Tasks', href: '/my-tasks' },
      { label: task?.title || 'Task Details' },
    ];
    backHref = '/my-tasks';
    backLabel = 'Back to My Tasks';
  }

  return (
    <AppShell
      isEventTeamAllowed={true}
      customCrumbs={customCrumbs}
    >
      <div className="space-y-6 max-w-6xl mx-auto">
        {/* Back Link */}
        <div>
          <Link
            href={backHref}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            {backLabel}
          </Link>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Task Notice">
            {errorMsg}
          </Alert>
        )}

        {loading ? (
          <div className="p-16 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : !task ? (
          <ErrorView
            type="404"
            title="Task Not Found"
            message="The requested task could not be found or access is restricted by your vertical scope."
            showHomeButton={true}
            returnHref={backHref}
            returnLabel={backLabel}
            onRetry={() => setRefreshTrigger((prev) => prev + 1)}
            layout="inline"
          />
        ) : (
          <div className="space-y-6">
            {/* Header Card */}
            <Card>
              <CardContent className="p-6 space-y-4">
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <TaskTypeBadge type={task.task_type} size="md" />
                      <PriorityBadge priority={task.priority} size="md" />
                      <StatusBadge status={task.status} size="md" />
                      <ActiveBadge status={task.status} size="md" />
                      <HealthIndicator health={task.health} size="md" />
                    </div>

                    <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                      {task.title}
                    </h1>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
                      <span className="flex items-center gap-1">
                        <Layers className="w-3.5 h-3.5 text-indigo-500" />
                        {task.vertical_name || 'Organization Wide'}
                      </span>
                      <span>•</span>
                      <span>Assigned by: <strong>{task.assigned_by_username}</strong></span>
                      <span>•</span>
                      <span>Created: {new Date(task.created_at).toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Operational Action Controls */}
                  {canTransition && (
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Direct Status Selector */}
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-zinc-500 font-medium hidden sm:inline">Status:</span>
                        <select
                          value={task.status === 'TODO' ? 'NOT_STARTED' : task.status}
                          onChange={(e) => {
                            const newStatus = e.target.value as TaskStatus;
                            if (newStatus === 'BLOCKED') {
                              setModalError(null);
                              setActiveModal('block');
                            } else {
                              let pct = task.completion_percentage;
                              if (newStatus === 'COMPLETED') pct = 100;
                              else if (newStatus === 'NOT_STARTED') pct = 0;
                              else if (newStatus === 'IN_PROGRESS' && pct === 0) pct = 25;
                              handleStatusTransition(newStatus, pct);
                            }
                          }}
                          disabled={modalLoading}
                          aria-label="Change task status"
                          className="text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 hover:border-indigo-500 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 cursor-pointer transition-colors shadow-2xs"
                        >
                          <option value="NOT_STARTED">Not Started</option>
                          <option value="IN_PROGRESS">In Progress</option>
                          <option value="BLOCKED">Blocked</option>
                          <option value="COMPLETED">Completed</option>
                          <option value="CANCELLED">Cancelled</option>
                        </select>
                      </div>

                      {(task.status === 'TODO' || (task.status as string) === 'NOT_STARTED') && (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => handleStatusTransition('IN_PROGRESS', 25)}
                          leftIcon={<Play className="w-3.5 h-3.5" />}
                        >
                          Start Task
                        </Button>
                      )}

                      {task.status === 'IN_PROGRESS' && (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => handleStatusTransition('COMPLETED', 100)}
                          leftIcon={<CheckCircle className="w-3.5 h-3.5" />}
                        >
                          Mark Complete
                        </Button>
                      )}

                      {task.status !== 'BLOCKED' && task.status !== 'COMPLETED' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setModalError(null);
                            setActiveModal('block');
                          }}
                          leftIcon={<AlertOctagon className="w-3.5 h-3.5 text-rose-500" />}
                        >
                          Report Blocker
                        </Button>
                      )}

                      {task.status === 'BLOCKED' && (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => {
                            setModalError(null);
                            setActiveModal('unblock');
                          }}
                          leftIcon={<Unlock className="w-3.5 h-3.5" />}
                        >
                          Unblock
                        </Button>
                      )}

                      {canReassign && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setModalError(null);
                            setActiveModal('reassign');
                          }}
                          leftIcon={<UserCheck className="w-3.5 h-3.5" />}
                        >
                          Reassign
                        </Button>
                      )}

                      {!task.is_escalated && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setModalError(null);
                            setActiveModal('escalate');
                          }}
                          leftIcon={<TrendingUp className="w-3.5 h-3.5 text-amber-500" />}
                        >
                          Escalate
                        </Button>
                      )}
                    </div>
                  )}
                </div>

                {/* Blocker Alert Banner */}
                {task.blockers && (
                  <Alert variant="danger" title="Operational Blocker Active">
                    {task.blockers}
                  </Alert>
                )}

                {/* Escalation Alert Banner */}
                {task.is_escalated && (
                  <Alert variant="warning" title="Task Escalated">
                    {task.escalation_reason || 'Escalated to vertical leadership.'}
                  </Alert>
                )}
              </CardContent>
            </Card>

            {/* Main Info Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: Details, Deliverables & Comments */}
              <div className="lg:col-span-2 space-y-6">
                {/* Description */}
                <Card>
                  <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm">
                    Task Description & Scope
                  </CardHeader>
                  <CardContent className="p-5 space-y-4">
                    <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap">
                      {task.description || <span className="text-zinc-400 italic">No description provided.</span>}
                    </p>

                    {task.evidence_link && (
                      <div className="pt-3 border-t border-zinc-100 dark:border-zinc-800">
                        <span className="text-xs font-semibold text-zinc-500 uppercase">Evidence / Deliverable Link</span>
                        <div className="mt-1">
                          <a
                            href={task.evidence_link}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1.5 text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            {task.evidence_link}
                          </a>
                        </div>
                      </div>
                    )}

                    {task.remarks && (
                      <div className="pt-3 border-t border-zinc-100 dark:border-zinc-800">
                        <span className="text-xs font-semibold text-zinc-500 uppercase">Operational Remarks</span>
                        <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">{task.remarks}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Comments Section */}
                <Card>
                  <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <MessageSquare className="w-4 h-4 text-indigo-500" />
                      Task Discussion ({comments.length})
                    </span>
                  </CardHeader>
                  <CardContent className="p-5 space-y-4">
                    {comments.length === 0 ? (
                      <p className="text-xs text-zinc-400 italic py-2">No comments posted yet.</p>
                    ) : (
                      <div className="space-y-3">
                        {comments.map((c) => (
                          <div
                            key={c.id}
                            className="p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200/80 dark:border-zinc-800 space-y-1.5"
                          >
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                                {c.author_name || c.author_username}
                              </span>
                              <span className="text-zinc-400">
                                {new Date(c.created_at).toLocaleString()}
                              </span>
                            </div>
                            <p className="text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">
                              {c.content}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Add Comment Form */}
                    <form onSubmit={handleAddComment} className="pt-3 border-t border-zinc-100 dark:border-zinc-800 space-y-2">
                      <textarea
                        rows={2}
                        placeholder="Add an operational note or progress comment..."
                        value={commentInput}
                        onChange={(e) => setCommentInput(e.target.value)}
                        className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      />
                      <div className="flex justify-end">
                        <Button
                          type="submit"
                          size="sm"
                          variant="primary"
                          isLoading={commentLoading}
                          disabled={!commentInput.trim()}
                          rightIcon={<Send className="w-3.5 h-3.5" />}
                        >
                          Post Comment
                        </Button>
                      </div>
                    </form>
                  </CardContent>
                </Card>
              </div>

              {/* Right Column: Execution Attributes & Immutable History */}
              <div className="space-y-6">
                {/* Execution Metadata Card */}
                <Card>
                  <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm">
                    Execution Details
                  </CardHeader>
                  <CardContent className="p-5 space-y-4 text-xs">
                    <div>
                      <span className="text-zinc-400">Assigned To</span>
                      <p className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm mt-0.5">
                        {task.assigned_to_name || task.assigned_to_username || 'Unassigned'}
                      </p>
                    </div>

                    <div>
                      <span className="text-zinc-400">Completion Status</span>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex-1 h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-indigo-600 rounded-full"
                            style={{ width: `${task.completion_percentage}%` }}
                          />
                        </div>
                        <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100">
                          {task.completion_percentage}%
                        </span>
                      </div>
                    </div>

                    <div>
                      <span className="text-zinc-400">Deadline</span>
                      <p className="font-medium text-zinc-800 dark:text-zinc-200 mt-0.5 flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-zinc-400" />
                        {task.deadline ? new Date(task.deadline).toLocaleString() : 'No deadline'}
                      </p>
                    </div>

                    {task.completed_on && (
                      <div>
                        <span className="text-zinc-400">Completed On</span>
                        <p className="font-medium text-emerald-600 dark:text-emerald-400 mt-0.5">
                          {new Date(task.completed_on).toLocaleString()}
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Immutable History Audit Trail */}
                <Card>
                  <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm flex items-center gap-2">
                    <History className="w-4 h-4 text-indigo-500" />
                    Audit History ({history.length})
                  </CardHeader>
                  <CardContent className="p-4 space-y-3">
                    {history.length === 0 ? (
                      <p className="text-xs text-zinc-400 italic">No history records logged.</p>
                    ) : (
                      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                        {history.map((h) => (
                          <div
                            key={h.id}
                            className="p-2.5 rounded-lg bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-100 dark:border-zinc-800/80 text-xs space-y-1"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                                {h.action}
                              </span>
                              <span className="text-zinc-400 font-mono text-[10px]">
                                {new Date(h.timestamp).toLocaleTimeString()}
                              </span>
                            </div>
                            <p className="text-zinc-500">
                              Actor: <strong>{h.actor_username || 'System'}</strong>
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>

            {/* Modal Dialogs */}
            {/* Blocker Modal */}
            <ConfirmDialog
              isOpen={activeModal === 'block'}
              title="Report Operational Blocker"
              description="Record a critical blocker preventing task progress."
              variant="danger"
              confirmLabel="Block Task"
              isLoading={modalLoading}
              onConfirm={handleBlockTask}
              onCancel={() => setActiveModal(null)}
            >
              <div className="space-y-3">
                {modalError && <Alert variant="danger">{modalError}</Alert>}
                <textarea
                  rows={3}
                  required
                  placeholder="Describe the blocker details, dependency, or issue..."
                  value={blockerText}
                  onChange={(e) => setBlockerText(e.target.value)}
                  className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-rose-500"
                />
              </div>
            </ConfirmDialog>

            {/* Unblock Modal */}
            <ConfirmDialog
              isOpen={activeModal === 'unblock'}
              title="Unblock Task"
              description="Confirm resolution of the blocker and resume execution."
              variant="primary"
              confirmLabel="Resume Task"
              isLoading={modalLoading}
              onConfirm={handleUnblockTask}
              onCancel={() => setActiveModal(null)}
            >
              <div className="space-y-3">
                {modalError && <Alert variant="danger">{modalError}</Alert>}
                <Input
                  label="Resolution Remarks (Optional)"
                  placeholder="How was the blocker resolved?"
                  value={unblockResolution}
                  onChange={(e) => setUnblockResolution(e.target.value)}
                />
              </div>
            </ConfirmDialog>

            {/* Escalate Modal */}
            <ConfirmDialog
              isOpen={activeModal === 'escalate'}
              title="Escalate Operational Task"
              description="Escalate this task to vertical leadership for urgent review."
              variant="warning"
              confirmLabel="Submit Escalation"
              isLoading={modalLoading}
              onConfirm={handleEscalateTask}
              onCancel={() => setActiveModal(null)}
            >
              <div className="space-y-3">
                {modalError && <Alert variant="danger">{modalError}</Alert>}
                <textarea
                  rows={3}
                  required
                  placeholder="State the escalation reason and requested leadership action..."
                  value={escalateReason}
                  onChange={(e) => setEscalateReason(e.target.value)}
                  className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </ConfirmDialog>

            {/* Reassign Modal */}
            <ConfirmDialog
              isOpen={activeModal === 'reassign'}
              title="Reassign Task"
              description="Select a new user within this vertical division."
              variant="primary"
              confirmLabel="Reassign"
              isLoading={modalLoading}
              onConfirm={handleReassignTask}
              onCancel={() => setActiveModal(null)}
            >
              <div className="space-y-3">
                {modalError && <Alert variant="danger">{modalError}</Alert>}
                <UserSelector
                  usage="assignment"
                  label="Target Assignee"
                  required
                  placeholder="Search member in division to reassign..."
                  verticalId={task?.vertical_id || undefined}
                  value={reassignUserId}
                  onChange={(val) => setReassignUserId(val || '')}
                />
              </div>
            </ConfirmDialog>
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default function TaskDetailPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950">
          <Spinner size="lg" className="text-indigo-600 dark:text-indigo-400" />
        </div>
      }
    >
      <TaskDetailContent />
    </React.Suspense>
  );
}
