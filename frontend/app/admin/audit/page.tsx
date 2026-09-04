'use client';

/**
 * Immutable Audit Center (/admin/audit)
 * Append-only security and operational activity trail with structured metadata inspection.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { EmptyState } from '@/components/common/EmptyState';
import { Modal } from '@/components/ui/Modal';
import { auditApi, ApiException } from '@/lib/api';
import { AuditLogResponse } from '@/types/governance';
import { formatAuditDateTime } from '@/lib/utils';
import {
  ShieldCheck,
  Search,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  FileText,
} from 'lucide-react';

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogResponse[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filters
  const [outcomeFilter, setOutcomeFilter] = useState<string>('ALL');
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Selected Log for detail inspection
  const [selectedLog, setSelectedLog] = useState<AuditLogResponse | null>(null);
  const [showRawJson, setShowRawJson] = useState<boolean>(false);

  const fetchAuditLogs = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const params: {
        action?: string;
        outcome?: string;
        resource_type?: string;
        limit: number;
      } = { limit: 150 };

      if (outcomeFilter !== 'ALL') params.outcome = outcomeFilter;
      if (resourceTypeFilter !== 'ALL') params.resource_type = resourceTypeFilter;

      const res = await auditApi.listLogs(params);
      setLogs(res.items || []);
      setTotalCount(res.total || 0);
    } catch (err: unknown) {
      const msg = err instanceof ApiException ? err.message : 'Failed to load audit records';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  }, [outcomeFilter, resourceTypeFilter]);

  useEffect(() => {
    let active = true;
    const params: {
      action?: string;
      outcome?: string;
      resource_type?: string;
      limit: number;
    } = { limit: 150 };

    if (outcomeFilter !== 'ALL') params.outcome = outcomeFilter;
    if (resourceTypeFilter !== 'ALL') params.resource_type = resourceTypeFilter;

    auditApi
      .listLogs(params)
      .then((res) => {
        if (active) {
          setLogs(res.items || []);
          setTotalCount(res.total || 0);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          const msg = err instanceof ApiException ? err.message : 'Failed to load audit records';
          setErrorMsg(msg);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [outcomeFilter, resourceTypeFilter]);

  const filteredLogs = logs.filter((l) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      l.action.toLowerCase().includes(q) ||
      (l.actor_username && l.actor_username.toLowerCase().includes(q)) ||
      l.resource_type.toLowerCase().includes(q) ||
      (l.resource_id && l.resource_id.toLowerCase().includes(q)) ||
      (l.ip_address && l.ip_address.toLowerCase().includes(q))
    );
  });

  return (
    <AppShell requiredRoles={['ADMIN']} requiredPermission="audit.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-indigo-950/20 via-purple-950/15 to-transparent border border-indigo-200 dark:border-indigo-800/40">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                Immutable Audit Center
              </h1>
              <Badge variant="default" size="sm">
                Compliance & Security
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
              Append-only security and operational audit trail with cryptographic correlation identifiers.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-xs font-semibold px-3 py-1.5 bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-xs">
              <span>Total Records: </span>
              <span className="font-mono text-indigo-600 dark:text-indigo-400 font-bold">{totalCount}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchAuditLogs}
              isLoading={loading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
          </div>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Audit Center Alert" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        {/* Filters Bar */}
        <Card>
          <CardContent className="p-4">
            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-center">
              <div className="sm:col-span-6 relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search by action, actor, resource ID, or IP..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-xs bg-zinc-50/50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="sm:col-span-3 flex items-center gap-2">
                <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 shrink-0">
                  Outcome:
                </label>
                <select
                  value={outcomeFilter}
                  onChange={(e) => setOutcomeFilter(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="ALL">All Outcomes</option>
                  <option value="SUCCESS">SUCCESS</option>
                  <option value="FAILURE">FAILURE</option>
                  <option value="DENIED">DENIED</option>
                </select>
              </div>

              <div className="sm:col-span-3 flex items-center gap-2">
                <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 shrink-0">
                  Resource:
                </label>
                <select
                  value={resourceTypeFilter}
                  onChange={(e) => setResourceTypeFilter(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="ALL">All Resource Types</option>
                  <option value="AUTH">AUTH / SESSION</option>
                  <option value="USER">USER</option>
                  <option value="VERTICAL">VERTICAL</option>
                  <option value="TASK">TASK</option>
                  <option value="EVENT">EVENT</option>
                  <option value="ISSUE">ISSUE</option>
                  <option value="FORM">FORM</option>
                  <option value="CONFIG">CONFIG</option>
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Audit Log Table */}
        <Card>
          <CardHeader className="py-3 px-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between">
            <CardTitle className="text-sm font-bold">Security & Operational Event Trail</CardTitle>
            <span className="text-[11px] font-mono text-zinc-400">
              Showing {filteredLogs.length} verified records
            </span>
          </CardHeader>
          <CardContent className="p-0">
            {loading && logs.length === 0 ? (
              <div className="p-16 flex flex-col items-center justify-center gap-2 text-zinc-400">
                <Spinner size="md" />
                <p className="text-xs">Loading audit ledger...</p>
              </div>
            ) : filteredLogs.length === 0 ? (
              <EmptyState
                icon={ShieldCheck}
                title="No Audit Records"
                description={
                  searchQuery || outcomeFilter !== 'ALL' || resourceTypeFilter !== 'ALL'
                    ? 'No audit log entries match the filter criteria.'
                    : 'Audit log table is empty.'
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-50 dark:bg-zinc-900/50 text-zinc-500 font-semibold uppercase tracking-wider text-[10px] border-b border-zinc-200 dark:border-zinc-800">
                    <tr>
                      <th className="py-3 px-4">Outcome</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Resource Target</th>
                      <th className="py-3 px-4">Actor</th>
                      <th className="py-3 px-4">IP / Context</th>
                      <th className="py-3 px-4">Timestamp</th>
                      <th className="py-3 px-4 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60">
                    {filteredLogs.map((log) => {
                      const isSuccess = log.outcome === 'SUCCESS';

                      return (
                        <tr
                          key={log.id}
                          className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40 transition-colors"
                        >
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold text-[10px] ${
                                isSuccess
                                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                                  : 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                              }`}
                            >
                              {isSuccess ? (
                                <CheckCircle2 className="w-3 h-3" />
                              ) : (
                                <XCircle className="w-3 h-3" />
                              )}
                              {log.outcome}
                            </span>
                          </td>

                          <td className="py-3 px-4 font-mono font-semibold text-zinc-900 dark:text-zinc-100">
                            {log.action}
                          </td>

                          <td className="py-3 px-4 font-mono text-zinc-600 dark:text-zinc-400">
                            <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                              {log.resource_type}
                            </span>
                            {log.resource_id && (
                              <span className="text-zinc-400 text-[10px] ml-1">
                                ({log.resource_id.slice(0, 8)}...)
                              </span>
                            )}
                          </td>

                          <td className="py-3 px-4 text-zinc-800 dark:text-zinc-200">
                            {log.actor_username ? (
                              <span className="font-medium">@{log.actor_username}</span>
                            ) : log.actor_id ? (
                              <span className="font-mono text-[10px]">{log.actor_id.slice(0, 8)}...</span>
                            ) : (
                              <span className="text-zinc-400 italic">System</span>
                            )}
                          </td>

                          <td className="py-3 px-4 text-zinc-500 dark:text-zinc-400 font-mono text-[11px]">
                            {log.ip_address || 'Internal'}
                          </td>

                          <td className="py-3 px-4 text-zinc-500 dark:text-zinc-400 font-mono text-[11px]">
                            {formatAuditDateTime(log.timestamp || log.created_at, true)}
                          </td>

                          <td className="py-3 px-4 text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setSelectedLog(log);
                                setShowRawJson(false);
                              }}
                              className="text-[11px] px-2.5 py-1 h-auto"
                              leftIcon={<FileText className="w-3 h-3" />}
                            >
                              Inspect
                            </Button>
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

        {/* Detailed Record Modal */}
        <Modal
          isOpen={!!selectedLog}
          onClose={() => {
            setSelectedLog(null);
            setShowRawJson(false);
          }}
          title={`Audit Record: ${selectedLog?.action}`}
          description={`Log ID: ${selectedLog?.id}`}
        >
          {selectedLog && (
            <div className="space-y-4 text-xs">
              {/* Structured Summary Grid */}
              <div className="grid grid-cols-2 gap-3 p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Outcome</span>
                  <span
                    className={`font-bold ${
                      selectedLog.outcome === 'SUCCESS' ? 'text-emerald-600' : 'text-rose-600'
                    }`}
                  >
                    {selectedLog.outcome}
                  </span>
                </div>

                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Actor</span>
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                    {selectedLog.actor_username ? `@${selectedLog.actor_username}` : 'System Engine'}
                  </span>
                </div>

                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Target Resource</span>
                  <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400">
                    {selectedLog.resource_type}
                  </span>
                </div>

                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Resource ID</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    {selectedLog.resource_id || 'N/A'}
                  </span>
                </div>

                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Timestamp</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    {formatAuditDateTime(selectedLog.timestamp || selectedLog.created_at, true)}
                  </span>
                </div>

                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">IP Address / Host</span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">
                    {selectedLog.ip_address || 'Internal Service'}
                  </span>
                </div>
              </div>

              {/* Collapsible Technical Details */}
              <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowRawJson(!showRawJson)}
                  className="flex items-center gap-1.5 text-xs font-semibold text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                >
                  {showRawJson ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  <span>{showRawJson ? 'Hide' : 'Show'} Technical JSON Metadata</span>
                </button>

                {showRawJson && (
                  <div className="mt-3 p-4 bg-zinc-950 text-emerald-400 rounded-xl overflow-x-auto text-xs font-mono border border-zinc-800">
                    <pre>{JSON.stringify(selectedLog.details || {}, null, 2)}</pre>
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-3 border-t border-zinc-100 dark:border-zinc-800">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSelectedLog(null);
                    setShowRawJson(false);
                  }}
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
