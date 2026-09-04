'use client';

/**
 * Announcements Management (/announcements)
 * Department broadcasts, targeted audience circulars, and lifecycle management.
 */

import React, { useState, useEffect } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { StatusBadge } from '@/components/common/StatusBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { UniversalSelector } from '@/components/ui/UniversalSelector';
import { UniversalAudienceSelector, AudienceItem } from '@/components/ui/UniversalAudienceSelector';
import { useAuth } from '@/providers/AuthProvider';
import {
  announcementsApi,
  organizationApi,
  eventsApi,
  usersApi,
  ApiException,
} from '@/lib/api';
import {
  AnnouncementResponse,
  AnnouncementCreate,
  AnnouncementPriority,
  AnnouncementScope,
  AnnouncementStatus,
} from '@/types/communication';
import { Vertical, UserSummary } from '@/types/organization';
import { EventResponse } from '@/types/event';
import {
  Megaphone,
  Plus,
  Search,
  Eye,
  Send,
  Archive,
  X,
  Radio,
  User,
  List,
  Grid,
} from 'lucide-react';

export default function AnnouncementsPage() {
  const { user, hasPermission } = useAuth();

  const [announcements, setAnnouncements] = useState<AnnouncementResponse[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [viewMode, setViewMode] = useState<'table' | 'card'>('table');

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [scopeFilter, setScopeFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Auxiliary data for audience selection
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [events, setEvents] = useState<EventResponse[]>([]);
  const [usersList, setUsersList] = useState<UserSummary[]>([]);

  // Selected announcement for view modal
  const [selectedItem, setSelectedItem] = useState<AnnouncementResponse | null>(null);

  // Create Modal State
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<{
    title: string;
    content: string;
    category: string;
    priority: AnnouncementPriority;
    scope: AnnouncementScope;
    vertical_id: string;
    event_id: string;
    target_user_id: string;
    publish_now: boolean;
  }>({
    title: '',
    content: '',
    category: 'GENERAL',
    priority: 'NORMAL',
    scope: 'ALL',
    vertical_id: '',
    event_id: '',
    target_user_id: '',
    publish_now: true,
  });
  const [selectedAudienceItems, setSelectedAudienceItems] = useState<AudienceItem[]>([]);

  // Action Dialog State
  const [actionItem, setActionItem] = useState<AnnouncementResponse | null>(null);
  const [actionType, setActionType] = useState<'PUBLISH' | 'ARCHIVE' | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);

  const canCreate = hasPermission('announcements.create');
  const canPublish = hasPermission('announcements.publish');

  // Load announcements
  useEffect(() => {
    let active = true;
    const fetchAnnouncements = async () => {
      try {
        const params: {
          status?: AnnouncementStatus;
          scope?: AnnouncementScope;
          limit: number;
        } = { limit: 100 };
        if (statusFilter !== 'ALL') params.status = statusFilter as AnnouncementStatus;
        if (scopeFilter !== 'ALL') params.scope = scopeFilter as AnnouncementScope;

        const res = await announcementsApi.list(params);
        if (active) {
          setAnnouncements(res.items);
          setTotalCount(res.total);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (active) {
          const msg = err instanceof ApiException ? err.message : 'Failed to load announcements';
          setErrorMsg(msg);
          setLoading(false);
        }
      }
    };

    fetchAnnouncements();
    return () => {
      active = false;
    };
  }, [statusFilter, scopeFilter, refreshTrigger]);

  // Load audience metadata lazily when creation modal opens
  useEffect(() => {
    let active = true;
    if (isCreateOpen) {
      Promise.all([
        organizationApi.listVerticals().catch(() => ({ items: [] })),
        eventsApi.list({ limit: 100 }).catch(() => ({ items: [] })),
        usersApi.listUsers({ limit: 100 }).catch(() => ({ items: [] })),
      ]).then(([vRes, eRes, uRes]) => {
        if (active) {
          setVerticals(vRes.items || []);
          setEvents(eRes.items || []);
          setUsersList(uRes.items || []);
        }
      });
    }
    return () => {
      active = false;
    };
  }, [isCreateOpen]);


  const handleCreateAnnouncement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.title.trim() || !createForm.content.trim()) {
      setCreateError('Title and content are required.');
      return;
    }

    setCreateLoading(true);
    setCreateError(null);

    const payload: AnnouncementCreate = {
      title: createForm.title.trim(),
      content: createForm.content.trim(),
      category: createForm.category.trim() || 'GENERAL',
      priority: createForm.priority,
      scope: createForm.scope,
      vertical_id: createForm.scope === 'VERTICAL' && createForm.vertical_id ? createForm.vertical_id : undefined,
      event_id: createForm.scope === 'EVENT' && createForm.event_id ? createForm.event_id : undefined,
      target_user_id: createForm.scope === 'USER' && createForm.target_user_id ? createForm.target_user_id : undefined,
      publish_now: createForm.publish_now,
    };

    try {
      await announcementsApi.create(payload);
      setIsCreateOpen(false);
      setCreateForm({
        title: '',
        content: '',
        category: 'GENERAL',
        priority: 'NORMAL',
        scope: 'ALL',
        vertical_id: '',
        event_id: '',
        target_user_id: '',
        publish_now: true,
      });
      setRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      const msg = err instanceof ApiException ? err.message : 'Failed to create announcement';
      setCreateError(msg);
    } finally {
      setCreateLoading(false);
    }
  };

  const handleAction = async () => {
    if (!actionItem || !actionType) return;
    setActionLoading(true);

    try {
      if (actionType === 'PUBLISH') {
        await announcementsApi.publish(actionItem.id);
      } else if (actionType === 'ARCHIVE') {
        await announcementsApi.archive(actionItem.id);
      }
      setActionItem(null);
      setActionType(null);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      const msg = err instanceof ApiException ? err.message : `Failed to ${actionType.toLowerCase()} announcement`;
      setErrorMsg(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const filteredAnnouncements = announcements.filter((a) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      a.title.toLowerCase().includes(q) ||
      a.content.toLowerCase().includes(q) ||
      (a.category && a.category.toLowerCase().includes(q)) ||
      (a.author_username && a.author_username.toLowerCase().includes(q))
    );
  });

  return (
    <AppShell requiredPermission="announcements.read" isEventTeamAllowed={true}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
              <Megaphone className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              Announcements & Circulars
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Department broadcasts, targeted vertical notifications, and official circulars.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center bg-zinc-100 dark:bg-zinc-800 p-1 rounded-xl">
              <button
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-lg text-xs font-semibold flex items-center gap-1 ${
                  viewMode === 'table'
                    ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                    : 'text-zinc-500'
                }`}
              >
                <List className="w-4 h-4" />
                <span className="hidden sm:inline">List</span>
              </button>
              <button
                onClick={() => setViewMode('card')}
                className={`p-1.5 rounded-lg text-xs font-semibold flex items-center gap-1 ${
                  viewMode === 'card'
                    ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                    : 'text-zinc-500'
                }`}
              >
                <Grid className="w-4 h-4" />
                <span className="hidden sm:inline">Cards</span>
              </button>
            </div>

            <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded-lg">
              <span>Total:</span>
              <span className="font-mono text-indigo-600 dark:text-indigo-400">{totalCount}</span>
            </div>
            {canCreate && (
              <Button
                variant="primary"
                onClick={() => {
                  setCreateError(null);
                  setIsCreateOpen(true);
                }}
                leftIcon={<Plus className="w-4 h-4" />}
              >
                New Announcement
              </Button>
            )}
          </div>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Notice">
            {errorMsg}
          </Alert>
        )}

        {/* Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
          <div className="sm:col-span-6 relative">
            <Search className="w-4 h-4 absolute left-3 top-3 text-zinc-400" />
            <input
              type="text"
              placeholder="Search announcements by title, content, or category..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 pl-9 pr-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="sm:col-span-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full h-10 px-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="PUBLISHED">Published</option>
              <option value="DRAFT">Draft</option>
              <option value="ARCHIVED">Archived</option>
            </select>
          </div>

          <div className="sm:col-span-3">
            <select
              value={scopeFilter}
              onChange={(e) => setScopeFilter(e.target.value)}
              className="w-full h-10 px-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Audiences</option>
              <option value="VERTICAL">Vertical Division</option>
              <option value="EVENT">Event Specific</option>
              <option value="USER">Direct User</option>
            </select>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="p-16 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : filteredAnnouncements.length === 0 ? (
          <Card>
            <CardContent className="p-8">
              <EmptyState
                icon={Megaphone}
                title="No Announcements Found"
                description={
                  searchQuery || statusFilter !== 'ALL' || scopeFilter !== 'ALL'
                    ? 'No announcements match the active filter criteria.'
                    : 'No active department announcements have been published yet.'
                }
                actionLabel={canCreate ? 'Create First Announcement' : undefined}
                onAction={canCreate ? () => setIsCreateOpen(true) : undefined}
              />
            </CardContent>
          </Card>
        ) : viewMode === 'table' ? (
          /* Compact Operational Table View */
          <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30 text-zinc-500 font-bold uppercase tracking-wider text-[10px]">
                    <th className="py-3 px-4">Priority</th>
                    <th className="py-3 px-4">Announcement</th>
                    <th className="py-3 px-4">Audience / Scope</th>
                    <th className="py-3 px-4">Author & Date</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {filteredAnnouncements.map((item) => (
                    <tr
                      key={item.id}
                      className="hover:bg-zinc-50 dark:hover:bg-zinc-800/40 transition-colors"
                    >
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            item.priority === 'URGENT'
                              ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300'
                              : item.priority === 'HIGH'
                              ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300'
                              : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
                          }`}
                        >
                          {item.priority}
                        </span>
                      </td>

                      <td className="py-3 px-4 max-w-md">
                        <div className="space-y-0.5">
                          <div className="font-bold text-zinc-900 dark:text-zinc-100 truncate flex items-center gap-1.5">
                            <span>{item.title}</span>
                            <span className="text-[10px] text-zinc-400 font-mono">#{item.category}</span>
                          </div>
                          <p className="text-[11px] text-zinc-500 dark:text-zinc-400 line-clamp-1">
                            {item.content}
                          </p>
                        </div>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-zinc-700 dark:text-zinc-300">
                          <Radio className="w-3 h-3 text-indigo-500" />
                          {item.scope === 'ALL'
                            ? 'Organization'
                            : item.scope === 'VERTICAL'
                            ? item.vertical_name || 'Vertical'
                            : item.scope === 'EVENT'
                            ? item.event_name || 'Event'
                            : `@${item.target_username || 'User'}`}
                        </span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap text-[11px] text-zinc-500">
                        <div>@{item.author_username || 'Author'}</div>
                        <div className="text-[10px] text-zinc-400">{new Date(item.created_at).toLocaleDateString()}</div>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <StatusBadge status={item.status} size="sm" />
                      </td>

                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs px-2.5"
                            onClick={() => setSelectedItem(item)}
                          >
                            <Eye className="w-3 h-3 mr-1" /> View
                          </Button>

                          {item.status === 'DRAFT' && canPublish && (
                            <Button
                              size="sm"
                              variant="primary"
                              className="h-7 text-xs px-2.5"
                              onClick={() => {
                                setActionItem(item);
                                setActionType('PUBLISH');
                              }}
                            >
                              <Send className="w-3 h-3 mr-1" /> Publish
                            </Button>
                          )}

                          {item.status === 'PUBLISHED' && canPublish && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs px-2"
                              onClick={() => {
                                setActionItem(item);
                                setActionType('ARCHIVE');
                              }}
                            >
                              <Archive className="w-3 h-3" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          /* Grid Card View */
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredAnnouncements.map((item) => (
              <Card
                key={item.id}
                className="hover:border-indigo-500/50 transition-all duration-200 flex flex-col justify-between"
              >
                <CardHeader className="pb-2 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={item.status} size="sm" />
                        <span
                          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                            item.priority === 'URGENT'
                              ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300'
                              : item.priority === 'HIGH'
                              ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300'
                              : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
                          }`}
                        >
                          {item.priority}
                        </span>
                        <span className="text-xs text-zinc-400 font-mono">#{item.category}</span>
                      </div>
                      <h3 className="font-bold text-base text-zinc-900 dark:text-zinc-100 leading-snug">
                        {item.title}
                      </h3>
                    </div>
                  </div>

                  {/* Scope / Audience Badge */}
                  <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
                    <Radio className="w-3.5 h-3.5 text-indigo-500" />
                    <span>Audience: </span>
                    <strong className="text-zinc-800 dark:text-zinc-200">
                      {item.scope === 'ALL'
                        ? 'Organization-Wide'
                        : item.scope === 'VERTICAL'
                        ? `Vertical: ${item.vertical_name || 'Division'}`
                        : item.scope === 'EVENT'
                        ? `Event: ${item.event_name || 'Specific'}`
                        : `User: ${item.target_username || 'Target'}`}
                    </strong>
                  </div>
                </CardHeader>

                <CardContent className="pt-2 pb-4 space-y-4">
                  <p className="text-sm text-zinc-600 dark:text-zinc-300 line-clamp-3 whitespace-pre-wrap">
                    {item.content}
                  </p>

                  <div className="flex items-center justify-between pt-3 border-t border-zinc-100 dark:border-zinc-800 text-xs text-zinc-400">
                    <div className="flex items-center gap-1">
                      <User className="w-3.5 h-3.5" />
                      <span>{item.author_username || 'Author'}</span>
                      <span>•</span>
                      <span>{new Date(item.created_at).toLocaleDateString()}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline" onClick={() => setSelectedItem(item)}>
                        <Eye className="w-3.5 h-3.5 mr-1" /> View
                      </Button>

                      {item.status === 'DRAFT' && canPublish && (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => {
                            setActionItem(item);
                            setActionType('PUBLISH');
                          }}
                        >
                          <Send className="w-3.5 h-3.5 mr-1" /> Publish
                        </Button>
                      )}

                      {item.status === 'PUBLISHED' && canPublish && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setActionItem(item);
                            setActionType('ARCHIVE');
                          }}
                        >
                          <Archive className="w-3.5 h-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* View Modal */}
        {selectedItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="relative w-[95vw] sm:w-[88vw] md:w-[75vw] lg:w-[62vw] max-w-2xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden">
              <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-start justify-between bg-white dark:bg-zinc-900">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={selectedItem.status} size="sm" />
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                      Priority: {selectedItem.priority}
                    </span>
                    <span className="text-xs text-zinc-400 font-mono">#{selectedItem.category}</span>
                  </div>
                  <h2 className="text-base sm:text-xl font-bold text-zinc-900 dark:text-zinc-100">{selectedItem.title}</h2>
                </div>
                <button
                  onClick={() => setSelectedItem(null)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-3">
                <div className="p-3 bg-zinc-50 dark:bg-zinc-800/60 rounded-xl text-xs space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Target Audience:</span>
                    <strong className="text-zinc-800 dark:text-zinc-200">
                      {selectedItem.scope === 'ALL'
                        ? 'All Members (Organization-Wide)'
                        : selectedItem.scope === 'VERTICAL'
                        ? `Vertical: ${selectedItem.vertical_name || 'Division'}`
                        : selectedItem.scope === 'EVENT'
                        ? `Event: ${selectedItem.event_name || 'Specific'}`
                        : `Target User: ${selectedItem.target_username}`}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Published By:</span>
                    <span className="text-zinc-700 dark:text-zinc-300">
                      {selectedItem.author_username} ({new Date(selectedItem.created_at).toLocaleString()})
                    </span>
                  </div>
                </div>

                <div className="p-4 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-100 dark:border-zinc-800 text-sm text-zinc-800 dark:text-zinc-200 leading-relaxed whitespace-pre-wrap">
                  {selectedItem.content}
                </div>
              </div>

              <div className="shrink-0 flex justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                <Button variant="outline" onClick={() => setSelectedItem(null)}>
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
                  <Megaphone className="w-5 h-5 text-indigo-600" />
                  Issue New Announcement
                </h3>
                <button
                  onClick={() => setIsCreateOpen(false)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreateAnnouncement} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4">
                  {createError && <Alert variant="danger">{createError}</Alert>}

                  <Input
                    label="Title"
                    required
                    placeholder="e.g. Schedule Update for Annual State Cup"
                    value={createForm.title}
                    onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                  />

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Category (Optional)</label>
                      <input
                        type="text"
                        placeholder="e.g. OPERATIONS, LOGISTICS, GENERAL"
                        value={createForm.category}
                        onChange={(e) => setCreateForm({ ...createForm, category: e.target.value.toUpperCase() })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Priority Level (Optional)</label>
                      <select
                        value={createForm.priority}
                        onChange={(e) => setCreateForm({ ...createForm, priority: e.target.value as AnnouncementPriority })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="LOW">Low</option>
                        <option value="NORMAL">Normal</option>
                        <option value="HIGH">High</option>
                        <option value="URGENT">Urgent (Broadcast)</option>
                      </select>
                    </div>
                  </div>

                  <div className="p-4 bg-zinc-50 dark:bg-zinc-800/40 rounded-xl space-y-3 border border-zinc-200 dark:border-zinc-700/60">
                    <UniversalAudienceSelector
                      usage="audience"
                      label="Target Audience Scope"
                      required
                      description="Select entire organization, vertical division, role group, or specific recipient."
                      value={selectedAudienceItems}
                      onChange={(items) => {
                        setSelectedAudienceItems(items);
                        if (items.some((it) => it.type === 'ALL')) {
                          setCreateForm((prev) => ({ ...prev, scope: 'ALL', vertical_id: '', target_user_id: '' }));
                        } else if (items.some((it) => it.type === 'VERTICAL')) {
                          const vItem = items.find((it) => it.type === 'VERTICAL');
                          setCreateForm((prev) => ({ ...prev, scope: 'VERTICAL', vertical_id: vItem?.rawId || '', target_user_id: '' }));
                        } else if (items.some((it) => it.type === 'ROLE_VERTICAL')) {
                          const rvItem = items.find((it) => it.type === 'ROLE_VERTICAL');
                          setCreateForm((prev) => ({
                            ...prev,
                            scope: 'VERTICAL',
                            vertical_id: rvItem?.metadata?.vertical_id || '',
                            target_user_id: '',
                          }));
                        } else if (items.some((it) => it.type === 'USER')) {
                          const uItem = items.find((it) => it.type === 'USER');
                          setCreateForm((prev) => ({ ...prev, scope: 'USER', target_user_id: uItem?.rawId || '', vertical_id: '' }));
                        }
                      }}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      Content & Details <span className="text-rose-500">*</span>
                    </label>
                    <textarea
                      rows={5}
                      required
                      placeholder="Full announcement body and operational instructions..."
                      value={createForm.content}
                      onChange={(e) => setCreateForm({ ...createForm, content: e.target.value })}
                      className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    <input
                      type="checkbox"
                      id="publish_now_toggle"
                      checked={createForm.publish_now}
                      onChange={(e) => setCreateForm({ ...createForm, publish_now: e.target.checked })}
                      className="w-4 h-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    <label htmlFor="publish_now_toggle" className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      Publish immediately (dispatches notifications to audience)
                    </label>
                  </div>
                </div>

                {/* Fixed Footer Action Buttons */}
                <div className="shrink-0 flex justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                  <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" isLoading={createLoading}>
                    {createForm.publish_now ? 'Publish Announcement' : 'Save as Draft'}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Action Confirmation Dialog */}
        <ConfirmDialog
          isOpen={!!actionItem && !!actionType}
          title={actionType === 'PUBLISH' ? 'Publish Announcement' : 'Archive Announcement'}
          description={`Are you sure you want to ${actionType?.toLowerCase()} "${actionItem?.title}"?`}
          variant={actionType === 'ARCHIVE' ? 'danger' : 'primary'}
          confirmLabel={actionType === 'PUBLISH' ? 'Publish Now' : 'Archive'}
          isLoading={actionLoading}
          onConfirm={handleAction}
          onCancel={() => {
            setActionItem(null);
            setActionType(null);
          }}
        />
      </div>
    </AppShell>
  );
}
