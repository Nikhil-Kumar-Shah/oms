'use client';

/**
 * Account Succession & Ownership Governance Workspace (/transfers)
 * Governed administrative workflows for operational succession and asset handoff.
 * Reassigns active responsibilities to the successor account while immutably preserving
 * historical records, completed tasks, reports, and audit trails under the previous account.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { Modal } from '@/components/ui/Modal';
import { UserSelector } from '@/components/selectors';
import { useAuth } from '@/hooks/useAuth';
import {
  transfersApi,
  adminApi,
  ApiException,
} from '@/lib/api';
import {
  OwnershipTransferResponse,
  AccountSuccessionPreviewResponse,
  TransferStatus,
} from '@/types/governance';
import { formatAuditDateTime } from '@/lib/utils';
import {
  ArrowRightLeft,
  UserCheck,
  Shield,
  Search,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Eye,
} from 'lucide-react';

export default function AccountSuccessionPage() {
  const { user, hasPermission } = useAuth();

  const [transfers, setTransfers] = useState<OwnershipTransferResponse[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Filter & Search
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Initiate Succession Modal State
  const [isInitiateOpen, setIsInitiateOpen] = useState<boolean>(false);
  const [initiateLoading, setInitiateLoading] = useState<boolean>(false);
  const [initiateError, setInitiateError] = useState<string | null>(null);

  const [previousUserId, setPreviousUserId] = useState<string>('');
  const [successorUserId, setSuccessorUserId] = useState<string>('');
  const [reason, setReason] = useState<string>('');

  // Succession Preview State
  const [previewData, setPreviewData] = useState<AccountSuccessionPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Review Modal State
  const [selectedTransfer, setSelectedTransfer] = useState<OwnershipTransferResponse | null>(null);
  const [reviewRemarks, setReviewRemarks] = useState<string>('');
  const [reviewLoading, setReviewLoading] = useState<boolean>(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // Inspect Modal State
  const [inspectTransfer, setInspectTransfer] = useState<OwnershipTransferResponse | null>(null);

  const canRequest = hasPermission('transfers.request');
  const canApprove = hasPermission('transfers.approve');

  // Load Transfers callback for manual triggers
  const fetchTransfers = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const params: { status?: TransferStatus; limit: number } = { limit: 100 };
      if (statusFilter !== 'ALL') params.status = statusFilter as TransferStatus;

      const res = await transfersApi.list(params);
      setTransfers(res.items);
      setTotalCount(res.total);
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(err.message);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    let active = true;
    const params: { status?: TransferStatus; limit: number } = { limit: 100 };
    if (statusFilter !== 'ALL') params.status = statusFilter as TransferStatus;

    transfersApi
      .list(params)
      .then((res) => {
        if (active) {
          setTransfers(res.items);
          setTotalCount(res.total);
        }
      })
      .catch((err) => {
        if (active) {
          setErrorMsg(err instanceof ApiException ? err.message : 'Failed to load transfer records.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [statusFilter, refreshTrigger]);

  // Load Succession Dry-Run Preview when both accounts are chosen
  useEffect(() => {
    if (!previousUserId || !successorUserId) {
      return;
    }
    if (previousUserId === successorUserId) {
      return;
    }

    let active = true;

    transfersApi
      .previewSuccession(previousUserId, successorUserId)
      .then((data) => {
        if (active) {
          setPreviewData(data);
          setPreviewError(null);
        }
      })
      .catch((err) => {
        if (active) {
          setPreviewError(err instanceof ApiException ? err.message : 'Failed to generate succession preview.');
          setPreviewData(null);
        }
      })
      .finally(() => {
        if (active) setPreviewLoading(false);
      });

    return () => {
      active = false;
    };
  }, [previousUserId, successorUserId]);

  const handleInitiateSuccession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!previousUserId || !successorUserId || !reason.trim()) {
      setInitiateError('Please select both previous and successor accounts and provide a justification reason.');
      return;
    }
    if (reason.trim().length < 5) {
      setInitiateError('Reason must be at least 5 characters long.');
      return;
    }

    setInitiateLoading(true);
    setInitiateError(null);

    try {
      await transfersApi.initiateSuccession({
        previous_user_id: previousUserId,
        successor_user_id: successorUserId,
        reason: reason.trim(),
      });
      setSuccessMsg('Account succession request initiated successfully. Awaiting four-eyes administrative review.');
      setIsInitiateOpen(false);
      setPreviousUserId('');
      setSuccessorUserId('');
      setReason('');
      setPreviewData(null);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) {
        setInitiateError(err.message);
      } else if (err instanceof Error) {
        setInitiateError(err.message);
      }
    } finally {
      setInitiateLoading(false);
    }
  };

  const handleReviewSuccession = async (status: 'APPROVED' | 'REJECTED') => {
    if (!selectedTransfer) return;

    setReviewLoading(true);
    setReviewError(null);

    try {
      await transfersApi.review(selectedTransfer.id, {
        status: status as TransferStatus,
        remarks: reviewRemarks.trim() || undefined,
      });
      setSuccessMsg(
        status === 'APPROVED'
          ? 'Account succession successfully approved. Active responsibilities transitioned to successor in PostgreSQL.'
          : 'Succession request was rejected.'
      );
      setSelectedTransfer(null);
      setReviewRemarks('');
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) {
        setReviewError(err.message);
      } else if (err instanceof Error) {
        setReviewError(err.message);
      }
    } finally {
      setReviewLoading(false);
    }
  };

  // Filtered List
  const filteredTransfers = transfers.filter((t) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (t.current_owner_username && t.current_owner_username.toLowerCase().includes(q)) ||
      (t.requested_owner_username && t.requested_owner_username.toLowerCase().includes(q)) ||
      (t.requested_by_username && t.requested_by_username.toLowerCase().includes(q)) ||
      t.reason.toLowerCase().includes(q)
    );
  });

  return (
    <AppShell requiredRoles={['ADMIN']} requiredPermission="transfers.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-purple-950/20 via-indigo-950/15 to-transparent border border-purple-200 dark:border-purple-800/40">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300">
                <ArrowRightLeft className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                Account Succession & Ownership Governance
              </h1>
              <Badge variant="default" size="sm">
                Four-Eyes Governed
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 max-w-3xl">
              Governed personnel transition workflows: Reassigns active operational responsibilities to the designated successor while immutably preserving historical completed work, reports, and audit trails under the previous account.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchTransfers}
              isLoading={loading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
            {canRequest && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setInitiateError(null);
                  setPreviousUserId('');
                  setSuccessorUserId('');
                  setReason('');
                  setPreviewData(null);
                  setIsInitiateOpen(true);
                }}
                leftIcon={<UserCheck className="w-3.5 h-3.5" />}
              >
                Initiate Succession
              </Button>
            )}
          </div>
        </div>

        {/* Alerts */}
        {errorMsg && (
          <Alert variant="danger" title="Error" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" title="Success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {/* Governance Principle Banner */}
        <div className="p-4 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 text-xs text-indigo-900 dark:text-indigo-200 flex items-start gap-3">
          <Shield className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-semibold">Authoritative Succession Rule:</span>
            <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
              Account Succession transitions active tasks, event POC roles, and vertical access from departing operators to active successors. Completed tasks, daily logs, and historical audit entries remain permanently attributed to the original creator.
            </p>
          </div>
        </div>

        {/* Filter Bar */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search by previous user, successor, or reason..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50/50 dark:bg-zinc-800/50 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-zinc-500">Status:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-2.5 py-1.5 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="PENDING">Pending Review</option>
                  <option value="COMPLETED">Completed</option>
                  <option value="APPROVED">Approved</option>
                  <option value="REJECTED">Rejected</option>
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Succession & Transfer Registry Table */}
        <Card>
          <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                  Succession & Transfer Registry
                </h3>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  Showing {filteredTransfers.length} of {totalCount} records
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-16 flex flex-col items-center justify-center gap-2 text-zinc-400">
                <Spinner size="lg" />
                <p className="text-xs">Loading succession records...</p>
              </div>
            ) : filteredTransfers.length === 0 ? (
              <div className="p-12 text-center text-zinc-400 text-xs">
                No account succession or transfer records match the selected filters.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30 text-zinc-500 dark:text-zinc-400 font-semibold">
                      <th className="py-3 px-4">Workflow Type</th>
                      <th className="py-3 px-4">Previous Account</th>
                      <th className="py-3 px-4">Successor Account</th>
                      <th className="py-3 px-4">Reason</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Effective Date</th>
                      <th className="py-3 px-4">Requested By</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60">
                    {filteredTransfers.map((t) => {
                      const isPending = t.status === 'PENDING';

                      return (
                        <tr
                          key={t.id}
                          className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/30 transition-colors"
                        >
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center gap-1 font-semibold px-2 py-0.5 rounded-full text-[10px] ${
                                t.resource_type === 'ACCOUNT'
                                  ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300'
                                  : 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300'
                              }`}
                            >
                              {t.resource_type === 'ACCOUNT' ? 'Account Succession' : `Resource: ${t.resource_type}`}
                            </span>
                          </td>

                          <td className="py-3 px-4">
                            <span className="font-mono font-semibold text-zinc-900 dark:text-zinc-100">
                              {t.current_owner_username ? `@${t.current_owner_username}` : 'N/A'}
                            </span>
                          </td>

                          <td className="py-3 px-4">
                            <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400">
                              {t.requested_owner_username ? `@${t.requested_owner_username}` : 'N/A'}
                            </span>
                          </td>

                          <td className="py-3 px-4 max-w-xs truncate text-zinc-600 dark:text-zinc-300">
                            {t.reason}
                          </td>

                          <td className="py-3 px-4">
                            <span
                              className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                                t.status === 'COMPLETED' || t.status === 'APPROVED'
                                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                                  : t.status === 'PENDING'
                                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                                  : 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                              }`}
                            >
                              {t.status}
                            </span>
                          </td>

                          <td className="py-3 px-4 font-mono text-[11px] text-zinc-500 dark:text-zinc-400">
                            {formatAuditDateTime(t.completed_at || t.reviewed_at || t.created_at)}
                          </td>

                          <td className="py-3 px-4 text-zinc-500 font-mono text-[11px]">
                            {t.requested_by_username ? `@${t.requested_by_username}` : 'System'}
                          </td>

                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              {isPending && canApprove ? (
                                <Button
                                  size="sm"
                                  variant="primary"
                                  onClick={() => {
                                    setSelectedTransfer(t);
                                    setReviewRemarks('');
                                    setReviewError(null);
                                  }}
                                  className="text-[11px] px-2.5 py-1 h-auto"
                                  leftIcon={<Shield className="w-3 h-3" />}
                                >
                                  Review
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setInspectTransfer(t)}
                                  className="text-[11px] px-2 py-1 h-auto"
                                  leftIcon={<Eye className="w-3 h-3" />}
                                >
                                  Inspect
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ------------------------------------------------------------------ */}
        {/* 1. INITIATE ACCOUNT SUCCESSION MODAL                              */}
        {/* ------------------------------------------------------------------ */}
        <Modal
          isOpen={isInitiateOpen}
          onClose={() => setIsInitiateOpen(false)}
          title="Initiate Account Ownership Succession"
          description="Prepare governed succession handover from departing account to active successor."
        >
          <form onSubmit={handleInitiateSuccession} className="space-y-4 text-xs">
            {initiateError && (
              <Alert variant="danger" title="Initiation Failed">
                {initiateError}
              </Alert>
            )}

            {/* Previous Account Selection */}
            <div className="space-y-1.5">
              <UserSelector
                usage="general"
                label="1. Previous Account (Departing Operator)"
                required
                placeholder="Search departing user account..."
                value={previousUserId}
                onChange={(val) => {
                  setPreviousUserId(val || '');
                  setPreviewLoading(true);
                }}
              />
            </div>

            {/* Successor Account Selection */}
            <div className="space-y-1.5">
              <UserSelector
                usage="assignment"
                label="2. Successor Account (Operator Assuming Responsibilities)"
                required
                placeholder="Search active successor account..."
                value={successorUserId}
                onChange={(val) => {
                  setSuccessorUserId(val || '');
                  setPreviewLoading(true);
                }}
              />
            </div>

            {/* Succession Dry-Run Preview Card */}
            {previewLoading && (
              <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800 flex items-center justify-center gap-2 text-zinc-400">
                <Spinner size="sm" />
                <span>Calculating active responsibility transitions...</span>
              </div>
            )}

            {previewError && (
              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300">
                {previewError}
              </div>
            )}

            {previewData && !previewLoading && (
              <div className="p-4 rounded-xl bg-purple-50/50 dark:bg-purple-950/20 border border-purple-200/70 dark:border-purple-800/50 space-y-3">
                <div className="flex items-center justify-between border-b border-purple-100 dark:border-purple-900/50 pb-2">
                  <h4 className="font-bold text-purple-900 dark:text-purple-200 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                    Inherited Active Responsibilities Summary
                  </h4>
                  <span className="text-[10px] font-mono text-purple-600 dark:text-purple-400">
                    Live Dry-Run
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded-lg bg-white dark:bg-zinc-900 border border-purple-100 dark:border-purple-900/40">
                    <span className="text-[10px] text-zinc-500 block">Active Tasks</span>
                    <span className="text-base font-bold font-mono text-zinc-900 dark:text-zinc-100">
                      {previewData.active_tasks_count}
                    </span>
                  </div>
                  <div className="p-2 rounded-lg bg-white dark:bg-zinc-900 border border-purple-100 dark:border-purple-900/40">
                    <span className="text-[10px] text-zinc-500 block">Event POC Roles</span>
                    <span className="text-base font-bold font-mono text-zinc-900 dark:text-zinc-100">
                      {previewData.active_events_count}
                    </span>
                  </div>
                  <div className="p-2 rounded-lg bg-white dark:bg-zinc-900 border border-purple-100 dark:border-purple-900/40">
                    <span className="text-[10px] text-zinc-500 block">Assigned Verticals</span>
                    <span className="text-base font-bold font-mono text-zinc-900 dark:text-zinc-100">
                      {previewData.assigned_verticals.length}
                    </span>
                  </div>
                </div>

                {previewData.active_tasks.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-[11px] font-semibold text-zinc-700 dark:text-zinc-300 block">
                      Active Tasks to be Reassigned:
                    </span>
                    <div className="max-h-24 overflow-y-auto space-y-1 pr-1">
                      {previewData.active_tasks.map((t) => (
                        <div
                          key={t.id}
                          className="flex items-center justify-between p-1.5 rounded bg-white dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800 text-[11px]"
                        >
                          <span className="font-medium truncate max-w-xs">{t.title}</span>
                          <span className="font-mono text-[10px] text-zinc-400">{t.priority}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-[11px] text-emerald-800 dark:text-emerald-300 flex items-start gap-2">
                  <Shield className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Historical Guarantee:</strong> {previewData.historical_preservation_note}
                  </span>
                </div>
              </div>
            )}

            {/* Justification Reason */}
            <div className="space-y-1.5">
              <label className="block font-semibold text-zinc-700 dark:text-zinc-300">
                3. Reason for Succession
              </label>
              <textarea
                required
                rows={3}
                placeholder="Detail the operational necessity, personnel departure, or formal handover reason..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsInitiateOpen(false)}
                disabled={initiateLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={initiateLoading}
                disabled={!previewData || initiateLoading}
                leftIcon={<UserCheck className="w-3.5 h-3.5" />}
              >
                Submit for Dual Review
              </Button>
            </div>
          </form>
        </Modal>

        {/* ------------------------------------------------------------------ */}
        {/* 2. REVIEW SUCCESSION REQUEST MODAL                                */}
        {/* ------------------------------------------------------------------ */}
        <Modal
          isOpen={!!selectedTransfer}
          onClose={() => setSelectedTransfer(null)}
          title="Review Account Succession Request"
          description="Evaluate administrative handover and execute atomic database transitions."
        >
          {selectedTransfer && (
            <div className="space-y-4 text-xs">
              {reviewError && (
                <Alert variant="danger" title="Review Failed">
                  {reviewError}
                </Alert>
              )}

              {user?.id === selectedTransfer.requested_by_id && (
                <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <strong>Self-Approval Prohibition:</strong> You initiated this succession request. Under four-eyes governance rules, a secondary System Administrator must approve it.
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-700">
                <div>
                  <span className="text-zinc-400 block font-medium">Previous Account</span>
                  <span className="font-mono font-semibold text-zinc-900 dark:text-zinc-100">
                    @{selectedTransfer.current_owner_username}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Designated Successor</span>
                  <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400">
                    @{selectedTransfer.requested_owner_username}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Initiated By</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    @{selectedTransfer.requested_by_username}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Request Date</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    {formatAuditDateTime(selectedTransfer.created_at)}
                  </span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-zinc-500 font-medium block">Reason for Succession:</span>
                <p className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800 text-zinc-800 dark:text-zinc-200">
                  {selectedTransfer.reason}
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300">
                  Reviewer Remarks (Optional)
                </label>
                <textarea
                  rows={2}
                  placeholder="Add approval notes or rejection rationale..."
                  value={reviewRemarks}
                  onChange={(e) => setReviewRemarks(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedTransfer(null)}
                  disabled={reviewLoading}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  isLoading={reviewLoading}
                  disabled={user?.id === selectedTransfer.requested_by_id || reviewLoading}
                  onClick={() => handleReviewSuccession('REJECTED')}
                  leftIcon={<XCircle className="w-3.5 h-3.5" />}
                >
                  Reject
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  isLoading={reviewLoading}
                  disabled={user?.id === selectedTransfer.requested_by_id || reviewLoading}
                  onClick={() => handleReviewSuccession('APPROVED')}
                  leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                >
                  Approve & Transition
                </Button>
              </div>
            </div>
          )}
        </Modal>

        {/* ------------------------------------------------------------------ */}
        {/* 3. INSPECT SUCCESSION RECORD MODAL                                */}
        {/* ------------------------------------------------------------------ */}
        <Modal
          isOpen={!!inspectTransfer}
          onClose={() => setInspectTransfer(null)}
          title="Succession Record Details"
          description={`Record ID: ${inspectTransfer?.id}`}
        >
          {inspectTransfer && (
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3 p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-700">
                <div>
                  <span className="text-zinc-400 block font-medium">Status</span>
                  <span
                    className={`font-bold ${
                      inspectTransfer.status === 'COMPLETED' || inspectTransfer.status === 'APPROVED'
                        ? 'text-emerald-600'
                        : inspectTransfer.status === 'PENDING'
                        ? 'text-amber-600'
                        : 'text-rose-600'
                    }`}
                  >
                    {inspectTransfer.status}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Workflow</span>
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                    {inspectTransfer.resource_type === 'ACCOUNT' ? 'Account Succession' : inspectTransfer.resource_type}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Previous Account</span>
                  <span className="font-mono text-zinc-900 dark:text-zinc-100">
                    @{inspectTransfer.current_owner_username}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Successor Account</span>
                  <span className="font-mono text-indigo-600 dark:text-indigo-400">
                    @{inspectTransfer.requested_owner_username}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Requested By</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    @{inspectTransfer.requested_by_username}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Reviewed By</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    {inspectTransfer.reviewed_by_username ? `@${inspectTransfer.reviewed_by_username}` : 'Pending Review'}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Created Timestamp</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    {formatAuditDateTime(inspectTransfer.created_at, true)}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-400 block font-medium">Effective Timestamp</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    {formatAuditDateTime(inspectTransfer.completed_at || inspectTransfer.reviewed_at, true)}
                  </span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-zinc-500 font-medium block">Reason:</span>
                <p className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800 text-zinc-800 dark:text-zinc-200">
                  {inspectTransfer.reason}
                </p>
              </div>

              {inspectTransfer.remarks && (
                <div className="space-y-1">
                  <span className="text-zinc-500 font-medium block">Reviewer Remarks:</span>
                  <p className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800 text-zinc-800 dark:text-zinc-200 italic">
                    {inspectTransfer.remarks}
                  </p>
                </div>
              )}

              <div className="flex items-center justify-end pt-3 border-t border-zinc-100 dark:border-zinc-800">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setInspectTransfer(null)}
                >
                  Close
                </Button>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </AppShell>
  );
}
