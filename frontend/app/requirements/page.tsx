'use client';

/**
 * Requirements & Master Requirements Operational Workspace (/requirements)
 * Dual-Mode Experience:
 * 1. Event Team Mode:
 *    - Streamlined creation: Title, Description, Priority, Deadline only.
 *    - Automatic event & POC binding (No recipient/target selection).
 *    - Direct tracking and single-thread conversation with assigned POCs.
 *    - Restricted from status changes, forwarding, and escalations.
 * 2. POC & Leadership Master Requirements Workspace:
 *    - Full operational tracking catalog patterned after Master Tasks.
 *    - Role-based scopes: All Requirements (Core), Assigned / POC Responsibilities, Escalated.
 *    - Status transition controls (Raised, Acknowledged, In Progress, Awaiting Info, Forwarded, Escalated, Resolved, Closed).
 *    - Internal Forwarding via UniversalSelector (User / Vertical) with audit reason and notifications.
 *    - Supervisory Escalation to Sports Core / Deputy Core.
 *    - Unified conversation & activity history stream.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { StatusBadge } from '@/components/common/StatusBadge';
import { PriorityBadge } from '@/components/common/PriorityBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { UniversalSelector } from '@/components/ui/UniversalSelector';
import { useAuth } from '@/providers/AuthProvider';
import { requirementsApi, ApiException } from '@/lib/api';
import {
  RequirementResponse,
  RequirementMessage,
  RequirementPriority,
  RequirementStatus,
  RequirementForwardRequest,
} from '@/types/requirement';
import { formatAuditDateTime } from '@/lib/utils';
import {
  GitPullRequest,
  Plus,
  Search,
  RefreshCw,
  Clock,
  Send,
  AlertTriangle,
  CheckCircle2,
  Eye,
  MessageSquare,
  ShieldAlert,
  ArrowRight,
  Forward,
  User as UserIcon,
  Filter,
  Check,
  Calendar,
  Layers,
  ChevronRight,
  ShieldCheck,
  Info,
  ExternalLink,
} from 'lucide-react';

const OPERATIONAL_STATUSES: { value: RequirementStatus; label: string }[] = [
  { value: 'RAISED', label: 'Raised' },
  { value: 'ACKNOWLEDGED', label: 'Acknowledged' },
  { value: 'IN_PROGRESS', label: 'In Progress' },
  { value: 'AWAITING_INFO', label: 'Awaiting Information' },
  { value: 'FORWARDED', label: 'Forwarded' },
  { value: 'ESCALATED', label: 'Escalated' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'CLOSED', label: 'Closed' },
];

export default function RequirementsPage() {
  const { user, hasRole, hasPermission } = useAuth();

  const isEventTeam = hasRole('EVENT_TEAM');
  const isCore = hasRole('SPORTS_CORE') || hasRole('DEPUTY_CORE') || hasRole('ADMIN');

  // Master requirements scope
  const [scope, setScope] = useState<'all' | 'assigned_to_me' | 'escalated'>('all');

  // Data states
  const [requirements, setRequirements] = useState<RequirementResponse[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');

  // Detail Modal & Conversation
  const [selectedReq, setSelectedReq] = useState<RequirementResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [messages, setMessages] = useState<RequirementMessage[]>([]);
  const [newMessage, setNewMessage] = useState<string>('');
  const [sendingMsg, setSendingMsg] = useState<boolean>(false);

  // Status transition remark state
  const [transitionStatus, setTransitionStatus] = useState<RequirementStatus | null>(null);
  const [transitionRemarks, setTransitionRemarks] = useState<string>('');
  const [transitionLoading, setTransitionLoading] = useState<boolean>(false);

  // Create Modal State
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<{
    title: string;
    description: string;
    priority: RequirementPriority;
    deadline: string;
    remarks: string;
    reference_link: string;
  }>({
    title: '',
    description: '',
    priority: 'MEDIUM',
    deadline: '',
    remarks: '',
    reference_link: '',
  });

  // Forward Modal State
  const [isForwardOpen, setIsForwardOpen] = useState<boolean>(false);
  const [forwardUserId, setForwardUserId] = useState<string>('');
  const [forwardReason, setForwardReason] = useState<string>('');
  const [forwardLoading, setForwardLoading] = useState<boolean>(false);
  const [forwardError, setForwardError] = useState<string | null>(null);

  // Escalate Modal State
  const [isEscalateOpen, setIsEscalateOpen] = useState<boolean>(false);
  const [escalateSupervisorId, setEscalateSupervisorId] = useState<string>('');
  const [escalateReason, setEscalateReason] = useState<string>('');
  const [escalateLoading, setEscalateLoading] = useState<boolean>(false);
  const [escalateError, setEscalateError] = useState<string | null>(null);

  // Fetch requirements
  useEffect(() => {
    let ignore = false;
    async function load() {
      setLoading(true);
      try {
        const res = await requirementsApi.list({
          status: statusFilter !== 'ALL' ? (statusFilter as RequirementStatus) : undefined,
          priority: priorityFilter !== 'ALL' ? (priorityFilter as RequirementPriority) : undefined,
          limit: 100,
        });
        if (!ignore) {
          setRequirements(res.items || []);
          setTotalCount(res.total || 0);
          setLoading(false);
        }
      } catch (err) {
        if (!ignore) {
          if (err instanceof ApiException) setErrorMsg(err.message);
          else if (err instanceof Error) setErrorMsg(err.message);
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      ignore = true;
    };
  }, [statusFilter, priorityFilter, refreshTrigger]);

  const refreshList = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  // Open Requirement Details & Load Conversation
  const openDetail = async (req: RequirementResponse) => {
    setSelectedReq(req);
    setDetailLoading(true);
    try {
      const [freshReq, msgs] = await Promise.all([
        requirementsApi.getById(req.id),
        requirementsApi.listMessages(req.id).catch(() => []),
      ]);
      setSelectedReq(freshReq);
      setMessages(msgs || []);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  // Filtered requirements based on Scope and Search
  const filteredRequirements = useMemo(() => {
    return requirements.filter((item) => {
      // Scope filter for non-EventTeam
      if (!isEventTeam) {
        if (scope === 'assigned_to_me') {
          const isAssigned = item.assignee_id === user?.id || item.responsible_poc_id === user?.id;
          if (!isAssigned) return false;
        } else if (scope === 'escalated') {
          if (!item.is_escalated && item.status !== 'ESCALATED') return false;
        }
      }

      // Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = item.title.toLowerCase().includes(q);
        const matchesDesc = item.description?.toLowerCase().includes(q);
        const matchesEvent = item.event_name?.toLowerCase().includes(q);
        const matchesRequester = item.requester_full_name?.toLowerCase().includes(q) || item.requester_username?.toLowerCase().includes(q);
        const matchesPOC = item.responsible_poc_full_name?.toLowerCase().includes(q) || item.responsible_poc_username?.toLowerCase().includes(q);
        const matchesAssignee = item.assignee_full_name?.toLowerCase().includes(q) || item.assignee_username?.toLowerCase().includes(q);
        const matchesId = item.id.toLowerCase().includes(q);
        return matchesTitle || matchesDesc || matchesEvent || matchesRequester || matchesPOC || matchesAssignee || matchesId;
      }

      return true;
    });
  }, [requirements, scope, searchQuery, user?.id, isEventTeam]);

  // Create Requirement Submission (Event Team & Staff)
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.title.trim()) {
      setCreateError('Please provide a requirement title.');
      return;
    }
    if (!createForm.description.trim()) {
      setCreateError('Please provide a detailed description.');
      return;
    }

    setCreateLoading(true);
    setCreateError(null);
    try {
      await requirementsApi.create({
        title: createForm.title.trim(),
        description: createForm.description.trim(),
        priority: createForm.priority,
        deadline: createForm.deadline ? new Date(createForm.deadline).toISOString() : undefined,
        remarks: createForm.remarks.trim() || undefined,
        reference_link: createForm.reference_link.trim() || undefined,
      });

      setSuccessMsg('Requirement raised successfully and routed to designated POC.');
      setIsCreateOpen(false);
      setCreateForm({
        title: '',
        description: '',
        priority: 'MEDIUM',
        deadline: '',
        remarks: '',
        reference_link: '',
      });
      refreshList();
    } catch (err) {
      if (err instanceof ApiException) setCreateError(err.message);
      else if (err instanceof Error) setCreateError(err.message);
      else setCreateError('Failed to raise requirement');
    } finally {
      setCreateLoading(false);
    }
  };

  // Add Comment / Conversation reply
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReq || !newMessage.trim()) return;
    setSendingMsg(true);
    try {
      const msg = await requirementsApi.postMessage(selectedReq.id, newMessage.trim());
      setMessages((prev) => [...prev, msg]);
      setNewMessage('');
    } catch (err) {
      if (err instanceof ApiException) setErrorMsg(err.message);
    } finally {
      setSendingMsg(false);
    }
  };

  // Status Transition
  const handleTransitionSubmit = async () => {
    if (!selectedReq || !transitionStatus) return;
    setTransitionLoading(true);
    try {
      const updated = await requirementsApi.transition(selectedReq.id, {
        status: transitionStatus,
        remarks: transitionRemarks.trim() || undefined,
      });
      setSelectedReq(updated);
      setTransitionStatus(null);
      setTransitionRemarks('');
      setSuccessMsg(`Requirement updated to ${transitionStatus}`);
      // Refresh messages to reflect system activity line
      const msgs = await requirementsApi.listMessages(selectedReq.id).catch(() => []);
      setMessages(msgs);
      refreshList();
    } catch (err) {
      if (err instanceof ApiException) setErrorMsg(err.message);
    } finally {
      setTransitionLoading(false);
    }
  };

  // Internal Forwarding
  const handleForwardSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReq) return;
    if (!forwardUserId) {
      setForwardError('Please select a recipient user or POC.');
      return;
    }
    if (!forwardReason.trim()) {
      setForwardError('Please provide a forwarding reason.');
      return;
    }

    setForwardLoading(true);
    setForwardError(null);
    try {
      const updated = await requirementsApi.forward(selectedReq.id, {
        target_user_id: forwardUserId,
        reason: forwardReason.trim(),
      });
      setSelectedReq(updated);
      setIsForwardOpen(false);
      setForwardUserId('');
      setForwardReason('');
      setSuccessMsg('Requirement forwarded successfully.');
      const msgs = await requirementsApi.listMessages(selectedReq.id).catch(() => []);
      setMessages(msgs);
      refreshList();
    } catch (err) {
      if (err instanceof ApiException) setForwardError(err.message);
      else if (err instanceof Error) setForwardError(err.message);
      else setForwardError('Failed to forward requirement');
    } finally {
      setForwardLoading(false);
    }
  };

  // Escalation Submission
  const handleEscalateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReq) return;
    if (!escalateSupervisorId) {
      setEscalateError('Please select a Core / Leadership authority to escalate to.');
      return;
    }
    if (!escalateReason.trim()) {
      setEscalateError('Please provide a reason for escalation.');
      return;
    }

    setEscalateLoading(true);
    setEscalateError(null);
    try {
      const updated = await requirementsApi.escalate(selectedReq.id, {
        escalated_to_id: escalateSupervisorId,
        reason: escalateReason.trim(),
      });
      setSelectedReq(updated);
      setIsEscalateOpen(false);
      setEscalateSupervisorId('');
      setEscalateReason('');
      setSuccessMsg('Requirement successfully escalated.');
      const msgs = await requirementsApi.listMessages(selectedReq.id).catch(() => []);
      setMessages(msgs);
      refreshList();
    } catch (err) {
      if (err instanceof ApiException) setEscalateError(err.message);
      else if (err instanceof Error) setEscalateError(err.message);
      else setEscalateError('Failed to escalate requirement');
    } finally {
      setEscalateLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Bar */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <GitPullRequest className="w-6 h-6 text-primary" />
              {isEventTeam ? 'Event Requirements' : 'Master Requirements'}
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              {isEventTeam
                ? 'Raise resource and operational requirements for your event and collaborate directly with designated POCs.'
                : 'Central operational tracking, automatic POC routing, internal forwarding, and supervisor escalation workspace.'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={refreshList}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>

            {isEventTeam && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsCreateOpen(true)}
                className="flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Raise Requirement
              </Button>
            )}
          </div>
        </div>

        {/* Notifications / Alerts */}
        {errorMsg && (
          <Alert variant="danger" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {/* Operational Workspace Navigation (POC & Core Only) */}
        {!isEventTeam && (
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-3">
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setScope('all')}
                className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  scope === 'all'
                    ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                }`}
              >
                {isCore ? 'All Requirements (Master)' : 'All Available'}
              </button>

              <button
                type="button"
                onClick={() => setScope('assigned_to_me')}
                className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  scope === 'assigned_to_me'
                    ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                }`}
              >
                Assigned / POC Duties
              </button>

              <button
                type="button"
                onClick={() => setScope('escalated')}
                className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  scope === 'escalated'
                    ? 'bg-rose-600 text-white shadow-sm'
                    : 'text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30'
                }`}
              >
                Escalations
              </button>
            </div>

            <div className="text-xs text-zinc-500 font-medium">
              Showing <span className="font-bold text-zinc-900 dark:text-zinc-100">{filteredRequirements.length}</span> of {totalCount} requirements
            </div>
          </div>
        )}

        {/* Filters Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 bg-zinc-50 dark:bg-zinc-900/50 p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800">
          <div className="md:col-span-2 relative">
            <Search className="w-4 h-4 absolute left-3 top-3 text-zinc-400" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by title, event, POC, requester, or ID..."
              className="pl-9 bg-white dark:bg-zinc-900"
            />
          </div>

          <div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full text-xs font-medium rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="ALL">All Statuses</option>
              {OPERATIONAL_STATUSES.map((st) => (
                <option key={st.value} value={st.value}>
                  {st.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="w-full text-xs font-medium rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="ALL">All Priorities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        </div>

        {/* Main List Table / Cards */}
        {loading ? (
          <div className="flex justify-center items-center py-24">
            <Spinner size="lg" />
          </div>
        ) : filteredRequirements.length === 0 ? (
          <EmptyState
            icon={GitPullRequest}
            title="No requirements found"
            description={
              isEventTeam
                ? 'You have not raised any requirements yet. Click "Raise Requirement" to request equipment, logistics, or support.'
                : 'No operational requirements match your current scope and filters.'
            }
            actionLabel={isEventTeam ? 'Raise Requirement' : undefined}
            onAction={isEventTeam ? () => setIsCreateOpen(true) : undefined}
          />
        ) : (
          <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm bg-white dark:bg-zinc-900">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-50 dark:bg-zinc-800/60 border-b border-zinc-200 dark:border-zinc-800 text-zinc-500 dark:text-zinc-400 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3.5 px-4">Requirement</th>
                    <th className="py-3.5 px-4">Event</th>
                    <th className="py-3.5 px-4">Raised By</th>
                    <th className="py-3.5 px-4">Responsible POC</th>
                    <th className="py-3.5 px-4">Current Handler</th>
                    <th className="py-3.5 px-4">Priority</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4">Activity</th>
                    <th className="py-3.5 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {filteredRequirements.map((req) => (
                    <tr
                      key={req.id}
                      onClick={() => openDetail(req)}
                      className="hover:bg-zinc-50 dark:hover:bg-zinc-800/40 cursor-pointer transition-colors"
                    >
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
                          {req.title}
                        </div>
                        <div className="text-zinc-400 text-xs truncate max-w-xs mt-0.5">
                          #{req.id.slice(0, 8)} · {req.description}
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        {req.event_name ? (
                          <div className="font-medium text-zinc-800 dark:text-zinc-200 flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                            {req.event_name}
                          </div>
                        ) : (
                          <span className="text-zinc-400 italic">General / Unlinked</span>
                        )}
                      </td>

                      <td className="py-3.5 px-4">
                        <div className="text-zinc-800 dark:text-zinc-200 font-medium">
                          {req.requester_full_name || req.requester_username}
                        </div>
                        <div className="text-zinc-400 text-[11px]">
                          {formatAuditDateTime(req.created_at)}
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        {req.responsible_poc_full_name || req.responsible_poc_username ? (
                          <div className="font-medium text-zinc-800 dark:text-zinc-200 flex items-center gap-1.5">
                            <ShieldCheck className="w-3.5 h-3.5 text-blue-500" />
                            {req.responsible_poc_full_name || req.responsible_poc_username}
                          </div>
                        ) : (
                          <span className="text-zinc-400 italic">Unassigned POC</span>
                        )}
                      </td>

                      <td className="py-3.5 px-4">
                        {req.assignee_full_name || req.assignee_username ? (
                          <div className="font-medium text-zinc-800 dark:text-zinc-200 flex items-center gap-1.5">
                            <UserIcon className="w-3.5 h-3.5 text-zinc-500" />
                            {req.assignee_full_name || req.assignee_username}
                          </div>
                        ) : (
                          <span className="text-zinc-400 italic">—</span>
                        )}
                      </td>

                      <td className="py-3.5 px-4">
                        <PriorityBadge priority={req.priority} size="sm" />
                      </td>

                      <td className="py-3.5 px-4">
                        <StatusBadge status={req.status} size="sm" />
                        {req.is_escalated && (
                          <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300">
                            ESCALATED
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1 text-zinc-500 dark:text-zinc-400">
                          <MessageSquare className="w-3.5 h-3.5" />
                          <span className="font-semibold">{req.messages_count}</span>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openDetail(req)}
                          className="text-xs h-7 px-2.5"
                        >
                          View Thread
                          <ChevronRight className="w-3.5 h-3.5 ml-1" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* Detail & Conversation Modal / Workspace Drawer                            */}
        {/* ========================================================================= */}
        {selectedReq && (
          <Modal
            isOpen={!!selectedReq}
            onClose={() => {
              setSelectedReq(null);
              setTransitionStatus(null);
            }}
            title={selectedReq.title}
            size="xl"
          >
            <div className="space-y-6">
              {/* Header Overview Metadata */}
              <div className="bg-zinc-50 dark:bg-zinc-900/60 p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-3">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={selectedReq.status} />
                    <PriorityBadge priority={selectedReq.priority} />
                    {selectedReq.is_escalated && (
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        ESCALATED TO LEADERSHIP
                      </span>
                    )}
                  </div>

                  <div className="text-xs text-zinc-500">
                    ID: <span className="font-mono">{selectedReq.id}</span> · Created {formatAuditDateTime(selectedReq.created_at)}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <div className="text-zinc-400 font-medium">Event</div>
                    <div className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
                      {selectedReq.event_name || 'General / Unlinked'}
                    </div>
                  </div>

                  <div>
                    <div className="text-zinc-400 font-medium">Raised By</div>
                    <div className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
                      {selectedReq.requester_full_name || selectedReq.requester_username}
                    </div>
                  </div>

                  <div>
                    <div className="text-zinc-400 font-medium">Responsible POC</div>
                    <div className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5 text-blue-500" />
                      {selectedReq.responsible_poc_full_name || selectedReq.responsible_poc_username || 'None'}
                    </div>
                  </div>

                  <div>
                    <div className="text-zinc-400 font-medium">Current Handler</div>
                    <div className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
                      {selectedReq.assignee_full_name || selectedReq.assignee_username || 'None'}
                    </div>
                  </div>
                </div>

                {selectedReq.deadline && (
                  <div className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1 pt-1">
                    <Calendar className="w-3.5 h-3.5" />
                    Deadline: <span className="font-semibold">{new Date(selectedReq.deadline).toLocaleString()}</span>
                  </div>
                )}
              </div>

              {/* Requirement Description */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-1">
                  Description
                </h4>
                <div className="text-sm text-zinc-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 whitespace-pre-wrap leading-relaxed">
                  {selectedReq.description}
                </div>
              </div>

              {/* Reference Link & Remarks */}
              {(selectedReq.reference_link || selectedReq.remarks) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-zinc-50 dark:bg-zinc-900/40 p-3 rounded-lg border border-zinc-200 dark:border-zinc-800 text-xs">
                  {selectedReq.reference_link && (
                    <div>
                      <div className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px] mb-1">
                        Reference Link
                      </div>
                      <a
                        href={selectedReq.reference_link.startsWith('http') ? selectedReq.reference_link : `https://${selectedReq.reference_link}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline font-medium inline-flex items-center gap-1 break-all"
                      >
                        <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                        {selectedReq.reference_link}
                      </a>
                    </div>
                  )}

                  {selectedReq.remarks && (
                    <div>
                      <div className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px] mb-1">
                        Operational Remarks
                      </div>
                      <div className="text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">
                        {selectedReq.remarks}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* POC Operational Controls (Hidden for Event Team) */}
              {!isEventTeam && (
                <div className="bg-zinc-50 dark:bg-zinc-900/60 p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                      POC Workflow Actions
                    </span>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsForwardOpen(true)}
                        className="text-xs flex items-center gap-1 h-8"
                      >
                        <Forward className="w-3.5 h-3.5 text-indigo-500" />
                        Forward Internally
                      </Button>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsEscalateOpen(true)}
                        className="text-xs flex items-center gap-1 h-8 text-rose-600 border-rose-200 hover:bg-rose-50 dark:border-rose-900/50 dark:hover:bg-rose-950/30"
                      >
                        <ShieldAlert className="w-3.5 h-3.5" />
                        Escalate
                      </Button>
                    </div>
                  </div>

                  {/* Status Transition Bar */}
                  <div className="flex flex-wrap items-center gap-2 pt-2">
                    <span className="text-xs font-medium text-zinc-500">Update Status:</span>
                    {OPERATIONAL_STATUSES.map((st) => (
                      <button
                        key={st.value}
                        type="button"
                        onClick={() => setTransitionStatus(st.value)}
                        className={`px-2.5 py-1 text-xs rounded-md border font-medium transition-colors ${
                          selectedReq.status === st.value
                            ? 'bg-zinc-900 text-white border-zinc-900 dark:bg-zinc-100 dark:text-zinc-900'
                            : 'border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                        }`}
                      >
                        {st.label}
                      </button>
                    ))}
                  </div>

                  {/* Remarks input when transitioning status */}
                  {transitionStatus && transitionStatus !== selectedReq.status && (
                    <div className="flex items-center gap-2 pt-2">
                      <Input
                        value={transitionRemarks}
                        onChange={(e) => setTransitionRemarks(e.target.value)}
                        placeholder={`Reason/remarks for transitioning to ${transitionStatus}...`}
                        className="text-xs h-8"
                      />
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={handleTransitionSubmit}
                        disabled={transitionLoading}
                        className="text-xs h-8 whitespace-nowrap"
                      >
                        {transitionLoading ? <Spinner size="sm" /> : `Confirm ${transitionStatus}`}
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {/* Unified Conversation & History Thread */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-500 flex items-center gap-1.5">
                  <MessageSquare className="w-3.5 h-3.5" />
                  Activity & Conversation Thread ({messages.length})
                </h4>

                <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 bg-zinc-50/50 dark:bg-zinc-900/40 max-h-96 overflow-y-auto space-y-3">
                  {messages.length === 0 ? (
                    <div className="text-center py-8 text-zinc-400 text-xs">
                      No replies or activity yet. Post a comment below to start communicating.
                    </div>
                  ) : (
                    messages.map((msg) => {
                      const isSystem = msg.content.startsWith('[SYSTEM ACTIVITY:');
                      return isSystem ? (
                        <div
                          key={msg.id}
                          className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800/70 border border-zinc-200 dark:border-zinc-700/60 text-xs text-zinc-600 dark:text-zinc-300 flex items-start gap-2"
                        >
                          <Info className="w-3.5 h-3.5 text-blue-500 shrink-0 mt-0.5" />
                          <div className="flex-1">
                            <span className="font-semibold text-zinc-800 dark:text-zinc-200">
                              {msg.content}
                            </span>
                            <div className="text-[10px] text-zinc-400 mt-0.5">
                              {formatAuditDateTime(msg.created_at)}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div
                          key={msg.id}
                          className={`p-3 rounded-xl border text-xs max-w-xl ${
                            msg.author_id === user?.id
                              ? 'ml-auto bg-primary/10 border-primary/20 text-zinc-900 dark:text-zinc-100'
                              : 'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100'
                          }`}
                        >
                          <div className="flex justify-between items-center mb-1 text-[11px] text-zinc-400">
                            <span className="font-bold text-zinc-700 dark:text-zinc-300">
                              {msg.author_full_name || msg.author_username}
                            </span>
                            <span>{formatAuditDateTime(msg.created_at)}</span>
                          </div>
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Message input box */}
                <form onSubmit={handleSendMessage} className="flex gap-2">
                  <Input
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    placeholder="Write a message or operational reply..."
                    className="text-xs"
                  />
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={sendingMsg || !newMessage.trim()}
                    className="flex items-center gap-1 px-4"
                  >
                    {sendingMsg ? <Spinner size="sm" /> : <Send className="w-3.5 h-3.5" />}
                    Send
                  </Button>
                </form>
              </div>
            </div>
          </Modal>
        )}

        {/* ========================================================================= */}
        {/* Create Requirement Modal (Auto-routed for Event Team)                      */}
        {/* ========================================================================= */}
        <Modal
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          title={isEventTeam ? 'Raise Event Requirement' : 'Create Requirement'}
          size="lg"
        >
          <form onSubmit={handleCreateSubmit} className="space-y-4">
            {createError && <Alert variant="danger">{createError}</Alert>}

            {isEventTeam && (
              <div className="p-3 bg-blue-50 dark:bg-blue-950/40 rounded-lg border border-blue-200 dark:border-blue-900 text-xs text-blue-700 dark:text-blue-300 flex items-start gap-2">
                <Info className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  This requirement will be <strong>automatically attached to your event</strong> and directly routed to your event’s designated <strong>POC Head</strong>.
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Requirement Title *
              </label>
              <Input
                value={createForm.title}
                onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                placeholder="e.g., Request 4 Goal Net Sets for Field B"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Detailed Description *
              </label>
              <textarea
                value={createForm.description}
                onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                rows={4}
                placeholder="Specify requirements, quantities, setup location, timing, and operational details..."
                className="w-full text-xs rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-3 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                  Priority
                </label>
                <select
                  value={createForm.priority}
                  onChange={(e) => setCreateForm({ ...createForm, priority: e.target.value as RequirementPriority })}
                  className="w-full text-xs rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-2.5 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                  Required By (Deadline)
                </label>
                <Input
                  type="datetime-local"
                  value={createForm.deadline}
                  onChange={(e) => setCreateForm({ ...createForm, deadline: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                  Remarks / Operational Notes
                </label>
                <Input
                  value={createForm.remarks}
                  onChange={(e) => setCreateForm({ ...createForm, remarks: e.target.value })}
                  placeholder="Optional operational notes or context..."
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                  Reference Link
                </label>
                <Input
                  value={createForm.reference_link}
                  onChange={(e) => setCreateForm({ ...createForm, reference_link: e.target.value })}
                  placeholder="https://drive.google.com/... or reference doc"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-4 border-t border-zinc-200 dark:border-zinc-800">
              <Button type="button" variant="ghost" onClick={() => setIsCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={createLoading}>
                {createLoading ? <Spinner size="sm" /> : 'Raise Requirement'}
              </Button>
            </div>
          </form>
        </Modal>

        {/* ========================================================================= */}
        {/* Forward Modal (Using existing UniversalSelector)                           */}
        {/* ========================================================================= */}
        <Modal
          isOpen={isForwardOpen}
          onClose={() => setIsForwardOpen(false)}
          title="Forward Requirement Internally"
          size="md"
        >
          <form onSubmit={handleForwardSubmit} className="space-y-4">
            {forwardError && <Alert variant="danger">{forwardError}</Alert>}

            <p className="text-xs text-zinc-500">
              Select an internal POC or team member to take operational responsibility for this requirement.
            </p>

            <UniversalSelector
              mode="USER"
              label="Select Recipient (POC / Staff) *"
              placeholder="Search by name, role, or vertical..."
              value={forwardUserId}
              onChange={(val) => setForwardUserId(val || '')}
              usage="general"
              required
            />

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Reason for Forwarding *
              </label>
              <textarea
                value={forwardReason}
                onChange={(e) => setForwardReason(e.target.value)}
                rows={3}
                placeholder="Explain why this requirement is being transferred..."
                className="w-full text-xs rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-2.5 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary"
                required
              />
            </div>

            <div className="flex justify-end gap-2 pt-4 border-t border-zinc-200 dark:border-zinc-800">
              <Button type="button" variant="ghost" onClick={() => setIsForwardOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={forwardLoading}>
                {forwardLoading ? <Spinner size="sm" /> : 'Confirm Forward'}
              </Button>
            </div>
          </form>
        </Modal>

        {/* ========================================================================= */}
        {/* Escalate Modal (Using existing UniversalSelector)                          */}
        {/* ========================================================================= */}
        <Modal
          isOpen={isEscalateOpen}
          onClose={() => setIsEscalateOpen(false)}
          title="Escalate Requirement to Leadership"
          size="md"
        >
          <form onSubmit={handleEscalateSubmit} className="space-y-4">
            {escalateError && <Alert variant="danger">{escalateError}</Alert>}

            <p className="text-xs text-zinc-500">
              Escalate this requirement to Sports Core or Deputy Core for high-level resource approval or blocker intervention.
            </p>

            <UniversalSelector
              mode="USER"
              label="Escalate To Authority *"
              placeholder="Search Sports Core / Deputy Core leadership..."
              value={escalateSupervisorId}
              onChange={(val) => setEscalateSupervisorId(val || '')}
              usage="general"
              required
            />

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Escalation Rationale *
              </label>
              <textarea
                value={escalateReason}
                onChange={(e) => setEscalateReason(e.target.value)}
                rows={3}
                placeholder="Detail the blocker, timeline risk, or required decision..."
                className="w-full text-xs rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-2.5 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary"
                required
              />
            </div>

            <div className="flex justify-end gap-2 pt-4 border-t border-zinc-200 dark:border-zinc-800">
              <Button type="button" variant="ghost" onClick={() => setIsEscalateOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={escalateLoading}
                className="bg-rose-600 hover:bg-rose-700 text-white"
              >
                {escalateLoading ? <Spinner size="sm" /> : 'Escalate Requirement'}
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </AppShell>
  );
}
