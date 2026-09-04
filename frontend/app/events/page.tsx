'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import {
  Flag,
  Plus,
  Search,
  Filter,
  Calendar,
  MapPin,
  Shield,
  ArrowRight,
  AlertCircle,
  X,
  User,
  Users,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { StatusBadge } from '@/components/common/StatusBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { UniversalAudienceSelector, AudienceItem } from '@/components/ui/UniversalAudienceSelector';
import { EventResponse, EventCreate } from '@/types/event';
import { Vertical } from '@/types/organization';
import { eventsApi, organizationApi } from '@/lib/api';
import { useAuth } from '@/providers/AuthProvider';
import { canCreateEvent } from '@/lib/permissions';

export default function EventsPage() {
  const { user } = useAuth();
  const canCreate = canCreateEvent(user);

  const [events, setEvents] = useState<EventResponse[]>([]);
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [verticalFilter, setVerticalFilter] = useState<string>('ALL');

  // Create Modal
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Minimal Event Creation state (Phase 11)
  const [eventTitle, setEventTitle] = useState('');
  const [selectedVerticalItems, setSelectedVerticalItems] = useState<AudienceItem[]>([]);
  const [selectedEventTeamItems, setSelectedEventTeamItems] = useState<AudienceItem[]>([]);
  const [selectedPocHeadItems, setSelectedPocHeadItems] = useState<AudienceItem[]>([]);
  const [selectedAdditionalPocItems, setSelectedAdditionalPocItems] = useState<AudienceItem[]>([]);
  const [eventDescription, setEventDescription] = useState('');
  const [eventHeadName, setEventHeadName] = useState('');
  const [eventHeadPhone, setEventHeadPhone] = useState('');
  const [eventHeadEmail, setEventHeadEmail] = useState('');

  const loadData = useCallback(async () => {
    try {
      const [eventsRes, vertsRes] = await Promise.all([
        eventsApi.list({ limit: 100 }),
        organizationApi.listVerticals(),
      ]);
      setEvents(eventsRes.items);
      setVerticals(vertsRes.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load events';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const [eventsRes, vertsRes] = await Promise.all([
          eventsApi.list({ limit: 100 }),
          organizationApi.listVerticals(),
        ]);
        if (!ignore) {
          setEvents(eventsRes.items);
          setVerticals(vertsRes.items);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = err instanceof Error ? err.message : 'Failed to load events';
          setError(msg);
        }
      } finally {
        if (!ignore) setIsLoading(false);
      }
    }
    init();
    return () => {
      ignore = true;
    };
  }, []);

  // Filtered Events
  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      const matchesSearch =
        searchQuery === '' ||
        e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (e.location && e.location.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (e.primary_poc_username && e.primary_poc_username.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesStatus = statusFilter === 'ALL' || e.status === statusFilter;
      const matchesVertical = verticalFilter === 'ALL' || e.vertical_id === verticalFilter;

      return matchesSearch && matchesStatus && matchesVertical;
    });
  }, [events, searchQuery, statusFilter, verticalFilter]);

  // KPI calculations
  const stats = useMemo(() => {
    const total = events.length;
    const planning = events.filter((e) => e.status === 'PLANNING' || e.status === 'NOT_STARTED').length;
    const inProgress = events.filter((e) => e.status === 'IN_PROGRESS').length;
    const completed = events.filter((e) => e.status === 'COMPLETED').length;
    return { total, planning, inProgress, completed };
  }, [events]);

  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventTitle.trim()) {
      setCreateError('Event Title is required.');
      return;
    }
    const verticalId = selectedVerticalItems[0]?.rawId;
    if (!verticalId) {
      setCreateError('Vertical Division is required.');
      return;
    }
    const eventTeamUserId = selectedEventTeamItems[0]?.rawId;
    if (!eventTeamUserId) {
      setCreateError('Event Team Account is required.');
      return;
    }
    const pocHeadUserId = selectedPocHeadItems[0]?.rawId;
    if (!pocHeadUserId) {
      setCreateError('POC Head is required.');
      return;
    }
    if (!eventHeadName.trim()) {
      setCreateError('Event Head Name is required.');
      return;
    }
    if (!eventHeadPhone.trim()) {
      setCreateError('Event Head Phone is required.');
      return;
    }
    if (!eventHeadEmail.trim()) {
      setCreateError('Event Head Email is required.');
      return;
    }

    setIsSubmitting(true);
    setCreateError(null);

    try {
      const payload: EventCreate = {
        name: eventTitle.trim(),
        description: eventDescription.trim() || undefined,
        vertical_id: verticalId,
        event_team_user_id: eventTeamUserId,
        poc_head_user_id: pocHeadUserId,
        primary_poc_id: pocHeadUserId,
        additional_poc_user_ids: selectedAdditionalPocItems.map((it) => it.rawId),
        event_head_name: eventHeadName.trim(),
        event_head_phone: eventHeadPhone.trim(),
        event_head_email: eventHeadEmail.trim(),
      };

      await eventsApi.create(payload);

      setIsCreateModalOpen(false);
      setEventTitle('');
      setEventDescription('');
      setSelectedVerticalItems([]);
      setSelectedEventTeamItems([]);
      setSelectedPocHeadItems([]);
      setSelectedAdditionalPocItems([]);
      setEventHeadName('');
      setEventHeadPhone('');
      setEventHeadEmail('');
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create event';
      setCreateError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppShell requiredPermission="events.read" isEventTeamAllowed={true}>

      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Events & Tournaments
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Department event lifecycle management, readiness sign-offs, and POC governance
            </p>
          </div>

          {canCreate && (
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            >
              <Plus className="h-4 w-4" />
              Create Event
            </button>
          )}
        </div>

        {/* KPI Summary Cards */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Total Events
            </p>
            <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">
              {stats.total}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
              Planning Phase
            </p>
            <p className="mt-2 text-2xl font-bold text-amber-600 dark:text-amber-400">
              {stats.planning}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
              In Execution
            </p>
            <p className="mt-2 text-2xl font-bold text-indigo-600 dark:text-indigo-400">
              {stats.inProgress}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              Completed
            </p>
            <p className="mt-2 text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {stats.completed}
            </p>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by event name, location, or POC..."
              className="w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-4 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:bg-white focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:focus:bg-slate-900"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 dark:border-slate-700 dark:bg-slate-800">
              <Filter className="h-3.5 w-3.5 text-slate-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-transparent text-xs font-medium text-slate-700 focus:outline-none dark:text-slate-200"
              >
                <option value="ALL">All Statuses</option>
                <option value="PLANNING">Planning</option>
                <option value="NOT_STARTED">Not Started</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="COMPLETED">Completed</option>
                <option value="CANCELLED">Cancelled</option>
                <option value="ARCHIVED">Archived</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 dark:border-slate-700 dark:bg-slate-800">
              <select
                value={verticalFilter}
                onChange={(e) => setVerticalFilter(e.target.value)}
                className="bg-transparent text-xs font-medium text-slate-700 focus:outline-none dark:text-slate-200"
              >
                <option value="ALL">All Verticals</option>
                {verticals.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Content Area */}
        {error && (
          <div className="flex items-center gap-2 rounded-xl bg-rose-50 p-4 text-sm text-rose-700 dark:bg-rose-950/30 dark:text-rose-400">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {isLoading ? (
          <div className="flex min-h-[300px] items-center justify-center rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-col items-center gap-2">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
              <p className="text-xs text-slate-500 dark:text-slate-400">Loading events...</p>
            </div>
          </div>
        ) : filteredEvents.length === 0 ? (
          <EmptyState
            icon={Flag}
            title="No Events Found"
            description="No matching events or tournaments were found for the selected filters."
            actionLabel={canCreate ? 'Create First Event' : undefined}
            onAction={canCreate ? () => setIsCreateModalOpen(true) : undefined}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredEvents.map((event) => (
              <div
                key={event.id}
                className="group relative flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-indigo-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-800"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-bold text-slate-900 group-hover:text-indigo-600 dark:text-white dark:group-hover:text-indigo-400">
                        {event.name}
                      </h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {event.vertical_name || 'General Operations'}
                      </p>
                    </div>
                    <StatusBadge status={event.status} size="sm" />
                  </div>

                  {/* Metadata items */}
                  <div className="mt-4 space-y-2 text-xs text-slate-600 dark:text-slate-400">
                    <div className="flex items-center gap-2">
                      <Shield className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                      <span>
                        POC Head:{' '}
                        <strong className="text-slate-700 dark:text-slate-300">
                          {event.primary_poc_username ? `@${event.primary_poc_username}` : 'Unassigned'}
                        </strong>
                      </span>
                    </div>

                    {event.event_team_username && (
                      <div className="flex items-center gap-2">
                        <Users className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                        <span>
                          Event Team: <strong className="text-slate-700 dark:text-slate-300">@{event.event_team_username}</strong>
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Action */}
                <div className="mt-5 border-t border-slate-100 pt-4 dark:border-slate-800">
                  <Link
                    href={`/events/${event.id}`}
                    className="flex w-full items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-indigo-50 hover:text-indigo-600 dark:bg-slate-800/60 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-indigo-400"
                  >
                    <span>Event Workspace</span>
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create Event Modal */}
        {isCreateModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-3 sm:p-4 md:p-6 backdrop-blur-sm">
            <div className="relative w-[95vw] sm:w-[92vw] md:w-[82vw] lg:w-[72vw] xl:w-[68vw] max-w-5xl max-h-[88vh] flex flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900 overflow-hidden">
              <div className="shrink-0 px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-white dark:bg-slate-900">
                <div className="flex items-center gap-2">
                  <Flag className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                  <div>
                    <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                      Create &amp; Configure Operational Event
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Configure event details, leadership, POC structures, and team assignments.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setIsCreateModalOpen(false)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <form onSubmit={handleCreateEvent} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-5">
                  {createError && (
                    <div className="flex items-center gap-2 rounded-lg bg-rose-50 p-3 text-xs text-rose-700 dark:bg-rose-950/30 dark:text-rose-400">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      <span>{createError}</span>
                    </div>
                  )}

                  {/* 1. Event Identification */}
                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Event Title <span className="text-rose-500 font-bold">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={eventTitle}
                        onChange={(e) => setEventTitle(e.target.value)}
                        placeholder="e.g. Annual Inter-College Football Championship"
                        className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Operational Scope &amp; Description <span className="text-slate-400 font-normal">(Optional)</span>
                      </label>
                      <textarea
                        rows={2}
                        value={eventDescription}
                        onChange={(e) => setEventDescription(e.target.value)}
                        placeholder="Summary of event operational scope, tournament format, or department guidelines..."
                        className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                      />
                    </div>
                  </div>

                  {/* 2. Scope & Account Configuration */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <UniversalAudienceSelector
                      mode="VERTICAL"
                      usage="general"
                      label="Vertical Division"
                      required
                      placeholder="Select Vertical Division..."
                      value={selectedVerticalItems}
                      onChange={(items) => {
                        setSelectedVerticalItems(items);
                        // Clear POCs if vertical changes
                        setSelectedPocHeadItems([]);
                        setSelectedAdditionalPocItems([]);
                      }}
                    />

                    <UniversalAudienceSelector
                      mode="EVENT_TEAM"
                      usage="general"
                      label="Event Team Account"
                      required
                      placeholder="Select Event Team Account..."
                      value={selectedEventTeamItems}
                      onChange={(items) => setSelectedEventTeamItems(items)}
                    />
                  </div>

                  {/* 3. Internal POCs */}
                  <div className="space-y-2 pt-1 border-t border-slate-100 dark:border-slate-800">
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <UniversalAudienceSelector
                        mode="USER"
                        usage="general"
                        label="POC Head"
                        required
                        placeholder="Search and select internal POC Head..."
                        value={selectedPocHeadItems}
                        onChange={(items) => {
                          setSelectedPocHeadItems(items);
                          if (items[0]) {
                            setSelectedAdditionalPocItems((prev) => prev.filter((p) => p.rawId !== items[0].rawId));
                          }
                        }}
                      />

                      <UniversalAudienceSelector
                        mode="USER"
                        multi={true}
                        usage="general"
                        label="Additional Internal POCs (Optional)"
                        placeholder="Search and select additional internal POCs..."
                        value={selectedAdditionalPocItems}
                        onChange={(items) => {
                          const filtered = selectedPocHeadItems[0]
                            ? items.filter((it) => it.rawId !== selectedPocHeadItems[0].rawId)
                            : items;
                          setSelectedAdditionalPocItems(filtered);
                        }}
                      />
                    </div>
                  </div>

                  {/* 4. External Event Team Contact Details */}
                  <div className="space-y-3 pt-1 border-t border-slate-100 dark:border-slate-800">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                        External Event Team Contact
                      </h4>
                      <p className="text-[11px] text-slate-400">
                        External organizer / team representative contact details (not platform accounts).
                      </p>
                    </div>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                          Event Head Name <span className="text-rose-500 font-bold">*</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={eventHeadName}
                          onChange={(e) => setEventHeadName(e.target.value)}
                          placeholder="e.g. David Miller"
                          className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                          Event Head Phone <span className="text-rose-500 font-bold">*</span>
                        </label>
                        <input
                          type="tel"
                          required
                          value={eventHeadPhone}
                          onChange={(e) => setEventHeadPhone(e.target.value)}
                          placeholder="e.g. +91 9876543210"
                          className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                          Event Head Email <span className="text-rose-500 font-bold">*</span>
                        </label>
                        <input
                          type="email"
                          required
                          value={eventHeadEmail}
                          onChange={(e) => setEventHeadEmail(e.target.value)}
                          placeholder="e.g. david@phoenix.org"
                          className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Fixed Footer with Action Buttons */}
                <div className="shrink-0 flex justify-end gap-3 px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/70">
                  <button
                    type="button"
                    onClick={() => setIsCreateModalOpen(false)}
                    className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors shadow-sm"
                  >
                    {isSubmitting ? 'Creating Event...' : 'Create Event'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
