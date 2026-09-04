'use client';

/**
 * Issue Details & Escalation Workflow (/issues/[id])
 * Detailed issue view, formal escalation, resolution, and immutable change history.
 */

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { StatusBadge } from '@/components/common/StatusBadge';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { useAuth } from '@/hooks/useAuth';
import { issuesApi, ApiException } from '@/lib/api';
import {
  IssueResponse,
  IssueHistoryResponse,
  IssueCommentResponse,
  IssueStatus,
} from '@/types/issue';
import {
  Layers,
  ArrowLeft,
  CheckCircle,
  TrendingUp,
  History,
  Shield,
  Clock,
  Play,
  MessageSquare,
  Send,
} from 'lucide-react';

export default function IssueDetailPage() {
  const params = useParams();
  const issueId = params.id as string;

  const { hasPermission } = useAuth();
  const [issue, setIssue] = useState<IssueResponse | null>(null);
  const [history, setHistory] = useState<IssueHistoryResponse[]>([]);
  const [comments, setComments] = useState<IssueCommentResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [commentInput, setCommentInput] = useState<string>('');
  const [commentLoading, setCommentLoading] = useState<boolean>(false);

  // Modals
  const [activeModal, setActiveModal] = useState<'escalate' | 'resolve' | null>(null);
  const [modalLoading, setModalLoading] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Form states
  const [escalationTarget, setEscalationTarget] = useState<string>('');
  const [escalationAction, setEscalationAction] = useState<string>('');
  const [resolutionText, setResolutionText] = useState<string>('');

  const canUpdate = hasPermission('issues.update');
  const canEscalate = hasPermission('issues.escalate');

  useEffect(() => {
    let active = true;
    if (issueId) {
      Promise.all([
        issuesApi.getById(issueId),
        issuesApi.listHistory(issueId),
        issuesApi.listComments(issueId),
      ])
        .then(([issueData, historyData, commentsData]) => {
          if (active) {
            setIssue(issueData);
            setHistory(historyData);
            setComments(commentsData);
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
  }, [issueId, refreshTrigger]);

  const handleStatusTransition = async (status: IssueStatus, resolution?: string) => {
    setModalLoading(true);
    setModalError(null);
    try {
      await issuesApi.transition(issueId, { status, resolution });
      setActiveModal(null);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleEscalate = async () => {
    if (!escalationTarget.trim() || !escalationAction.trim()) {
      setModalError('Escalation target and required action are mandatory.');
      return;
    }
    setModalLoading(true);
    setModalError(null);
    try {
      await issuesApi.escalate(issueId, {
        escalation_target: escalationTarget.trim(),
        escalation_action: escalationAction.trim(),
      });
      setActiveModal(null);
      setEscalationTarget('');
      setEscalationAction('');
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
      const newComment = await issuesApi.addComment(issueId, { content: commentInput.trim() });
      setComments((prev) => [...prev, newComment]);
      setCommentInput('');
    } catch (err) {
      // Comment form stays populated for retry
    } finally {
      setCommentLoading(false);
    }
  };

  return (
    <AppShell
      requiredPermission="issues.read"
      isEventTeamAllowed={false}
      customCrumbs={[
        { label: 'Issues & Escalations', href: '/issues' },
        { label: issue?.title || 'Issue Details' },
      ]}
    >
      <div className="space-y-6 max-w-5xl mx-auto">
        {/* Back Link */}
        <div>
          <Link
            href="/issues"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Issue Register
          </Link>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Issue Details Notice">
            {errorMsg}
          </Alert>
        )}

        {loading ? (
          <div className="p-16 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : !issue ? (
          <Alert variant="danger" title="Not Found">
            Issue not found or unauthorized.
          </Alert>
        ) : (
          <div className="space-y-6">
            {/* Header Card */}
            <Card>
              <CardContent className="p-6 space-y-4">
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={issue.status} size="md" />
                      {issue.sensitivity === 'CONFIDENTIAL' ? (
                        <span className="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                          <Shield className="w-3.5 h-3.5" />
                          CONFIDENTIAL
                        </span>
                      ) : (
                        <span className="text-xs font-mono px-2 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                          {issue.sensitivity}
                        </span>
                      )}
                    </div>

                    <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                      {issue.title}
                    </h1>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
                      <span className="flex items-center gap-1">
                        <Layers className="w-3.5 h-3.5 text-indigo-500" />
                        {issue.vertical_name || 'Organization'}
                      </span>
                      <span>•</span>
                      <span>Raised by: <strong>{issue.raised_by_username}</strong></span>
                      <span>•</span>
                      <span>Date: {new Date(issue.date_raised).toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-wrap items-center gap-2">
                    {canUpdate && issue.status === 'OPEN' && (
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => handleStatusTransition('IN_PROGRESS')}
                        leftIcon={<Play className="w-3.5 h-3.5" />}
                      >
                        Start Investigation
                      </Button>
                    )}

                    {canUpdate && issue.status !== 'RESOLVED' && issue.status !== 'CLOSED' && (
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => {
                          setModalError(null);
                          setActiveModal('resolve');
                        }}
                        leftIcon={<CheckCircle className="w-3.5 h-3.5" />}
                      >
                        Resolve Issue
                      </Button>
                    )}

                    {canEscalate && issue.status !== 'RESOLVED' && issue.status !== 'CLOSED' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setModalError(null);
                          setActiveModal('escalate');
                        }}
                        leftIcon={<TrendingUp className="w-3.5 h-3.5 text-amber-500" />}
                      >
                        Escalate to Leadership
                      </Button>
                    )}

                    {canUpdate && (issue.status === 'RESOLVED' || issue.status === 'CLOSED') && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleStatusTransition('OPEN')}
                        leftIcon={<Play className="w-3.5 h-3.5" />}
                      >
                        Reopen Issue
                      </Button>
                    )}
                  </div>
                </div>

                {/* Escalation Alert - strictly active while status is ESCALATED */}
                {issue.status === 'ESCALATED' && issue.escalation_target && (
                  <Alert variant="warning" title={`Active Escalation to ${issue.escalation_target}`}>
                    {issue.escalation_action}
                  </Alert>
                )}

                {/* Resolution Banner */}
                {issue.status === 'RESOLVED' && (
                  <div className="p-4 rounded-xl bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/60 flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <h4 className="text-sm font-bold text-emerald-900 dark:text-emerald-200">
                        Issue Resolved
                      </h4>
                      <p className="text-xs text-emerald-700 dark:text-emerald-300 leading-relaxed">
                        {issue.resolution || 'This operational issue has been marked as resolved.'}
                      </p>
                      {issue.resolution_date && (
                        <p className="text-[11px] text-emerald-600/90 dark:text-emerald-400/90 font-medium">
                          Resolved on {new Date(issue.resolution_date).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* Closed Banner */}
                {issue.status === 'CLOSED' && (
                  <div className="p-4 rounded-xl bg-zinc-100 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700 flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-zinc-500 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <h4 className="text-sm font-bold text-zinc-800 dark:text-zinc-200">
                        Issue Closed & Archived
                      </h4>
                      <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                        {issue.resolution || 'This issue has been formally closed and archived.'}
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Description and Details */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 space-y-6">
                <Card>
                  <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm">
                    Detailed Statement & Required Actions
                  </CardHeader>
                  <CardContent className="p-5 space-y-4">
                    <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap">
                      {issue.description}
                    </p>

                    {issue.action_required && (
                      <div className="pt-3 border-t border-zinc-100 dark:border-zinc-800">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-zinc-500 uppercase">Requested Action</span>
                          {(issue.status === 'RESOLVED' || issue.status === 'CLOSED') && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-bold">
                              Completed / Shut Down
                            </span>
                          )}
                        </div>
                        <p className={`mt-1 text-sm ${(issue.status === 'RESOLVED' || issue.status === 'CLOSED') ? 'text-zinc-500 dark:text-zinc-400 line-through' : 'text-zinc-900 dark:text-zinc-100 font-medium'}`}>
                          {issue.action_required}
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Comments / Discussion Section */}
                <Card>
                  <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <MessageSquare className="w-4 h-4 text-indigo-500" />
                      Issue Discussion ({comments.length})
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
                        placeholder="Add a remark or progress comment..."
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

              {/* Sidebar Info & History */}
              <div className="space-y-6">
                <Card>
                  <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm">
                    Assignment & Deadline
                  </CardHeader>
                  <CardContent className="p-5 space-y-3 text-xs">
                    <div>
                      <span className="text-zinc-400">Assigned To</span>
                      {issue.assignees && issue.assignees.length > 0 ? (
                        <div className="mt-1.5 space-y-1">
                          {issue.assignees.map((asgn) => (
                            <div
                              key={asgn.id}
                              className="flex items-center gap-2 p-1.5 rounded-lg bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-100 dark:border-zinc-800"
                            >
                              <div className="w-6 h-6 rounded-full bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 flex items-center justify-center font-bold text-[10px]">
                                {asgn.username[0]?.toUpperCase() || 'U'}
                              </div>
                              <div className="min-w-0">
                                <p className="font-semibold text-zinc-900 dark:text-zinc-100 text-xs truncate">
                                  {asgn.full_name || asgn.username}
                                </p>
                                {asgn.full_name && (
                                  <p className="text-[10px] text-zinc-400 truncate">@{asgn.username}</p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm mt-0.5">
                          {issue.assigned_to_username || 'Unassigned'}
                        </p>
                      )}
                    </div>

                    <div>
                      <span className="text-zinc-400">Target Resolution Date</span>
                      <p className="font-medium text-zinc-800 dark:text-zinc-200 mt-0.5 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-zinc-400" />
                        {issue.deadline ? new Date(issue.deadline).toLocaleDateString() : 'No deadline'}
                        {(issue.status === 'RESOLVED' || issue.status === 'CLOSED') && (
                          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold ml-1.5">
                            (Concluded)
                          </span>
                        )}
                      </p>
                    </div>
                  </CardContent>
                </Card>

                {/* History Audit */}
                <Card>
                  <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm flex items-center gap-2">
                    <History className="w-4 h-4 text-indigo-500" />
                    Audit Trail ({history.length})
                  </CardHeader>
                  <CardContent className="p-4 space-y-2.5 max-h-60 overflow-y-auto text-xs">
                    {history.length === 0 ? (
                      <p className="text-zinc-400 italic">No history records.</p>
                    ) : (
                      history.map((h) => (
                        <div
                          key={h.id}
                          className="p-2.5 rounded-lg bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-100 dark:border-zinc-800 text-xs space-y-0.5"
                        >
                          <span className="font-semibold text-indigo-600 dark:text-indigo-400">{h.action}</span>
                          <p className="text-zinc-500">
                            By <strong>{h.actor_username || 'System'}</strong> on {new Date(h.timestamp).toLocaleTimeString()}
                          </p>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>

            {/* Escalate Modal */}
            <ConfirmDialog
              isOpen={activeModal === 'escalate'}
              title="Escalate Operational Issue"
              description="Formally route this issue to organizational/vertical leadership."
              variant="warning"
              confirmLabel="Escalate"
              isLoading={modalLoading}
              onConfirm={handleEscalate}
              onCancel={() => setActiveModal(null)}
            >
              <div className="space-y-3">
                {modalError && <Alert variant="danger">{modalError}</Alert>}
                <Input
                  label="Escalation Target"
                  required
                  placeholder="e.g., Sports Core Lead, Disciplinary Committee"
                  value={escalationTarget}
                  onChange={(e) => setEscalationTarget(e.target.value)}
                />
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                    Required Action / Directive <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={3}
                    required
                    placeholder="Specific executive action or resolution requested..."
                    value={escalationAction}
                    onChange={(e) => setEscalationAction(e.target.value)}
                    className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              </div>
            </ConfirmDialog>

            {/* Resolve Modal */}
            <ConfirmDialog
              isOpen={activeModal === 'resolve'}
              title="Resolve Operational Issue"
              description="Capture resolution notes to close this issue."
              variant="primary"
              confirmLabel="Mark Resolved"
              isLoading={modalLoading}
              onConfirm={() => handleStatusTransition('RESOLVED', resolutionText.trim())}
              onCancel={() => setActiveModal(null)}
            >
              <div className="space-y-3">
                {modalError && <Alert variant="danger">{modalError}</Alert>}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                    Resolution Summary <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={3}
                    required
                    placeholder="Describe how the deficiency was rectified..."
                    value={resolutionText}
                    onChange={(e) => setResolutionText(e.target.value)}
                    className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>
            </ConfirmDialog>
          </div>
        )}
      </div>
    </AppShell>
  );
}
