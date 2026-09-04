'use client';

/**
 * Operational Communication Tracker (/communications)
 * Centralized operational correspondence logs, external contact records, and audit links.
 */

import React, { useState, useEffect } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { EmptyState } from '@/components/common/EmptyState';
import { useAuth } from '@/hooks/useAuth';
import {
  communicationsApi,
  organizationApi,
  eventsApi,
  ApiException,
} from '@/lib/api';
import {
  CommunicationLogResponse,
  CommunicationLogCreate,
  CommunicationType,
} from '@/types/communication';
import { Vertical } from '@/types/organization';
import { EventResponse } from '@/types/event';
import {
  MessageSquare,
  Plus,
  Search,
  Mail,
  Phone,
  Calendar,
  FileText,
  ExternalLink,
  X,
  Eye,
} from 'lucide-react';

export default function CommunicationsPage() {
  const { hasPermission } = useAuth();

  const [logs, setLogs] = useState<CommunicationLogResponse[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>('ALL');
  const [verticalFilter, setVerticalFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Auxiliary data
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [events, setEvents] = useState<EventResponse[]>([]);

  // Selected Log for detail modal
  const [selectedLog, setSelectedLog] = useState<CommunicationLogResponse | null>(null);

  // Create Modal State
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<{
    subject: string;
    communication_type: CommunicationType;
    sender_info: string;
    recipient_info: string;
    vertical_id: string;
    event_id: string;
    reference_link: string;
    remarks: string;
    date_time: string;
  }>({
    subject: '',
    communication_type: 'OFFICIAL_MESSAGE',
    sender_info: '',
    recipient_info: '',
    vertical_id: '',
    event_id: '',
    reference_link: '',
    remarks: '',
    date_time: new Date().toISOString().slice(0, 16),
  });

  const canLog = hasPermission('communications.log') || hasPermission('communications.create');

  // Load communications
  useEffect(() => {
    let active = true;
    const fetchCommunications = async () => {
      try {
        const params: {
          communication_type?: CommunicationType;
          vertical_id?: string;
          limit: number;
        } = { limit: 100 };
        if (typeFilter !== 'ALL') params.communication_type = typeFilter as CommunicationType;
        if (verticalFilter !== 'ALL') params.vertical_id = verticalFilter;

        const res = await communicationsApi.list(params);
        if (active) {
          setLogs(res.items);
          setTotalCount(res.total);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (active) {
          const msg = err instanceof ApiException ? err.message : 'Failed to load communications';
          setErrorMsg(msg);
          setLoading(false);
        }
      }
    };

    fetchCommunications();
    return () => {
      active = false;
    };
  }, [typeFilter, verticalFilter, refreshTrigger]);

  // Load auxiliary data
  useEffect(() => {
    let active = true;
    Promise.all([
      organizationApi.listVerticals().catch(() => ({ items: [] })),
      eventsApi.list({ limit: 100 }).catch(() => ({ items: [] })),
    ]).then(([vRes, eRes]) => {
      if (active) {
        setVerticals(vRes.items || []);
        setEvents(eRes.items || []);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const handleCreateLog = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.subject.trim() || !createForm.sender_info.trim() || !createForm.recipient_info.trim()) {
      setCreateError('Subject, sender information, and recipient information are required.');
      return;
    }

    setCreateLoading(true);
    setCreateError(null);

    const payload: CommunicationLogCreate = {
      subject: createForm.subject.trim(),
      communication_type: createForm.communication_type,
      sender_info: createForm.sender_info.trim(),
      recipient_info: createForm.recipient_info.trim(),
      vertical_id: createForm.vertical_id || undefined,
      event_id: createForm.event_id || undefined,
      reference_link: createForm.reference_link.trim() || undefined,
      remarks: createForm.remarks.trim() || undefined,
      date_time: createForm.date_time ? new Date(createForm.date_time).toISOString() : undefined,
    };

    try {
      await communicationsApi.create(payload);
      setIsCreateOpen(false);
      setCreateForm({
        subject: '',
        communication_type: 'OFFICIAL_MESSAGE',
        sender_info: '',
        recipient_info: '',
        vertical_id: '',
        event_id: '',
        reference_link: '',
        remarks: '',
        date_time: new Date().toISOString().slice(0, 16),
      });
      setRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      const msg = err instanceof ApiException ? err.message : 'Failed to record communication log';
      setCreateError(msg);
    } finally {
      setCreateLoading(false);
    }
  };

  const getTypeIcon = (type: CommunicationType) => {
    switch (type) {
      case 'EMAIL':
        return <Mail className="w-4 h-4 text-sky-500" />;
      case 'CALL':
        return <Phone className="w-4 h-4 text-emerald-500" />;
      case 'MEETING':
        return <Calendar className="w-4 h-4 text-indigo-500" />;
      case 'NOTICE':
        return <FileText className="w-4 h-4 text-amber-500" />;
      default:
        return <MessageSquare className="w-4 h-4 text-zinc-500" />;
    }
  };

  const filteredLogs = logs.filter((l) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      l.subject.toLowerCase().includes(q) ||
      l.sender_info.toLowerCase().includes(q) ||
      l.recipient_info.toLowerCase().includes(q) ||
      (l.remarks && l.remarks.toLowerCase().includes(q))
    );
  });

  return (
    <AppShell
      requiredRoles={['ADMIN', 'SPORTS_CORE', 'DEPUTY_CORE']}
      requiredPermission="communications.read"
      isEventTeamAllowed={false}
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
              <MessageSquare className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              Official Communication Log
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Audit log of formal correspondence, venue permits, government authorizations, sponsor agreements, and official notices.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded-lg">
              <span>Total Entries:</span>
              <span className="font-mono text-indigo-600 dark:text-indigo-400">{totalCount}</span>
            </div>
            {canLog && (
              <Button
                variant="primary"
                onClick={() => {
                  setCreateError(null);
                  setIsCreateOpen(true);
                }}
                leftIcon={<Plus className="w-4 h-4" />}
              >
                Log Communication
              </Button>
            )}
          </div>
        </div>

        {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

        {/* Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
          <div className="sm:col-span-6 relative">
            <Search className="w-4 h-4 absolute left-3 top-3 text-zinc-400" />
            <input
              type="text"
              placeholder="Search by subject, sender, or recipient..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 pl-9 pr-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="sm:col-span-3">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full h-10 px-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Communication Types</option>
              <option value="OFFICIAL_MESSAGE">Official Message</option>
              <option value="EMAIL">Email</option>
              <option value="CALL">Call / Voice</option>
              <option value="MEETING">Meeting Record</option>
              <option value="NOTICE">Notice</option>
              <option value="OTHER">Other</option>
            </select>
          </div>

          <div className="sm:col-span-3">
            <select
              value={verticalFilter}
              onChange={(e) => setVerticalFilter(e.target.value)}
              className="w-full h-10 px-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Vertical Divisions</option>
              {verticals.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="p-16 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : filteredLogs.length === 0 ? (
          <Card>
            <CardContent className="p-8">
              <EmptyState
                icon={MessageSquare}
                title="No Communication Logs Found"
                description={
                  searchQuery || typeFilter !== 'ALL' || verticalFilter !== 'ALL'
                    ? 'No communication records match your filter criteria.'
                    : 'No operational correspondence logs have been recorded yet.'
                }
                actionLabel={canLog ? 'Record First Entry' : undefined}
                onAction={canLog ? () => setIsCreateOpen(true) : undefined}
              />
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader className="py-4 px-6 border-b border-zinc-100 dark:border-zinc-800 font-semibold text-sm">
              Operational Logs ({filteredLogs.length})
            </CardHeader>
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-50 dark:bg-zinc-800/50 text-zinc-500 font-semibold uppercase tracking-wider border-b border-zinc-200 dark:border-zinc-800">
                  <tr>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Subject</th>
                    <th className="py-3 px-4">Sender $\rightarrow$ Recipient</th>
                    <th className="py-3 px-4">Context</th>
                    <th className="py-3 px-4">Date & Time</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {filteredLogs.map((log) => (
                    <tr
                      key={log.id}
                      className="hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors"
                    >
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 font-semibold text-zinc-800 dark:text-zinc-200">
                          {getTypeIcon(log.communication_type)}
                          {log.communication_type.replace('_', ' ')}
                        </span>
                      </td>

                      <td className="py-3.5 px-4 font-bold text-zinc-900 dark:text-zinc-100 max-w-xs truncate">
                        {log.subject}
                      </td>

                      <td className="py-3.5 px-4 text-zinc-600 dark:text-zinc-400">
                        <span className="font-medium text-zinc-800 dark:text-zinc-200">{log.sender_info}</span>
                        <span className="mx-1 text-zinc-400">$\rightarrow$</span>
                        <span className="font-medium text-zinc-800 dark:text-zinc-200">{log.recipient_info}</span>
                      </td>

                      <td className="py-3.5 px-4 text-zinc-500">
                        {log.vertical_name && (
                          <span className="block font-medium text-zinc-700 dark:text-zinc-300">
                            Vertical: {log.vertical_name}
                          </span>
                        )}
                        {log.event_name && (
                          <span className="block text-indigo-600 dark:text-indigo-400">
                            Event: {log.event_name}
                          </span>
                        )}
                        {!log.vertical_name && !log.event_name && 'General'}
                      </td>

                      <td className="py-3.5 px-4 text-zinc-400 font-mono">
                        {new Date(log.date_time).toLocaleDateString()}{' '}
                        {new Date(log.date_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <Button size="sm" variant="outline" onClick={() => setSelectedLog(log)}>
                          <Eye className="w-3.5 h-3.5 mr-1" /> View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {/* View Detail Modal */}
        {selectedLog && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="relative w-[95vw] sm:w-[88vw] md:w-[75vw] lg:w-[62vw] max-w-2xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden">
              <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-start justify-between bg-white dark:bg-zinc-900">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 font-bold text-xs text-zinc-800 dark:text-zinc-200">
                      {getTypeIcon(selectedLog.communication_type)}
                      {selectedLog.communication_type.replace('_', ' ')}
                    </span>
                    <span className="text-xs text-zinc-400">
                      {new Date(selectedLog.date_time).toLocaleString()}
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100">{selectedLog.subject}</h3>
                </div>
                <button
                  onClick={() => setSelectedLog(null)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-3 text-xs">
                <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl space-y-2">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Sender Information:</span>
                    <strong className="text-zinc-800 dark:text-zinc-200">{selectedLog.sender_info}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Recipient Information:</span>
                    <strong className="text-zinc-800 dark:text-zinc-200">{selectedLog.recipient_info}</strong>
                  </div>
                  {selectedLog.vertical_name && (
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Vertical Division:</span>
                      <span className="text-zinc-800 dark:text-zinc-200">{selectedLog.vertical_name}</span>
                    </div>
                  )}
                  {selectedLog.event_name && (
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Associated Event:</span>
                      <span className="text-zinc-800 dark:text-zinc-200">{selectedLog.event_name}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Logged By:</span>
                    <span className="text-zinc-800 dark:text-zinc-200">{selectedLog.created_by_username || 'System User'}</span>
                  </div>
                </div>

                {selectedLog.remarks && (
                  <div className="space-y-1">
                    <h4 className="font-semibold text-zinc-500 uppercase">Operational Remarks & Notes</h4>
                    <div className="p-3 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 text-zinc-800 dark:text-zinc-200 whitespace-pre-wrap">
                      {selectedLog.remarks}
                    </div>
                  </div>
                )}

                {selectedLog.reference_link && (
                  <div className="p-3 bg-indigo-50 dark:bg-indigo-950/40 rounded-xl border border-indigo-200 dark:border-indigo-800 flex items-center justify-between">
                    <span className="font-medium text-indigo-700 dark:text-indigo-300">Reference Document / Link</span>
                    <a
                      href={selectedLog.reference_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-bold text-indigo-600 dark:text-indigo-400 hover:underline"
                    >
                      Open Link <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                )}
              </div>

              <div className="shrink-0 flex justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                <Button variant="outline" onClick={() => setSelectedLog(null)}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Create Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="relative w-[95vw] sm:w-[92vw] md:w-[82vw] lg:w-[72vw] xl:w-[68vw] max-w-5xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden">
              <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between bg-white dark:bg-zinc-900">
                <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-indigo-600" />
                  Log Operational Correspondence
                </h3>
                <button
                  onClick={() => setIsCreateOpen(false)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreateLog} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4">
                  {createError && <Alert variant="danger">{createError}</Alert>}

                  <Input
                    label="Subject / Correspondence Title"
                    required
                    placeholder="e.g. Venue Permit Confirmation for Main Stadium"
                    value={createForm.subject}
                    onChange={(e) => setCreateForm({ ...createForm, subject: e.target.value })}
                  />

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Communication Type</label>
                      <select
                        value={createForm.communication_type}
                        onChange={(e) => setCreateForm({ ...createForm, communication_type: e.target.value as CommunicationType })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="OFFICIAL_MESSAGE">Official Message</option>
                        <option value="EMAIL">Email</option>
                        <option value="CALL">Call / Voice</option>
                        <option value="MEETING">Meeting Record</option>
                        <option value="NOTICE">Notice</option>
                        <option value="OTHER">Other</option>
                      </select>
                    </div>

                    <Input
                      label="Date & Time"
                      type="datetime-local"
                      required
                      value={createForm.date_time}
                      onChange={(e) => setCreateForm({ ...createForm, date_time: e.target.value })}
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Input
                      label="Sender Info"
                      required
                      placeholder="e.g. Director of Athletics (admin@state.gov)"
                      value={createForm.sender_info}
                      onChange={(e) => setCreateForm({ ...createForm, sender_info: e.target.value })}
                    />

                    <Input
                      label="Recipient Info"
                      required
                      placeholder="e.g. Football Operations Lead (poc@paradox.org)"
                      value={createForm.recipient_info}
                      onChange={(e) => setCreateForm({ ...createForm, recipient_info: e.target.value })}
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Associated Vertical (Optional)</label>
                      <select
                        value={createForm.vertical_id}
                        onChange={(e) => setCreateForm({ ...createForm, vertical_id: e.target.value })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">None / General</option>
                        {verticals.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Associated Event (Optional)</label>
                      <select
                        value={createForm.event_id}
                        onChange={(e) => setCreateForm({ ...createForm, event_id: e.target.value })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">None / General</option>
                        {events.map((ev) => (
                          <option key={ev.id} value={ev.id}>
                            {ev.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <Input
                    label="Reference / Document Link (Optional)"
                    placeholder="https://docs.paradoxsports.org/permits/stadium-2026.pdf"
                    value={createForm.reference_link}
                    onChange={(e) => setCreateForm({ ...createForm, reference_link: e.target.value })}
                  />

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      Remarks & Operational Notes
                    </label>
                    <textarea
                      rows={3}
                      placeholder="Key discussion points, outcome notes, or reference details..."
                      value={createForm.remarks}
                      onChange={(e) => setCreateForm({ ...createForm, remarks: e.target.value })}
                      className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                {/* Fixed Footer Action Buttons */}
                <div className="shrink-0 flex justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                  <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" isLoading={createLoading}>
                    Record Log
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
