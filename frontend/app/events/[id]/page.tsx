'use client';

import React, { useState, useEffect, useCallback, useMemo, use } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Calendar,
  Clock,
  MapPin,
  Shield,
  Flag,
  Users,
  Check,
  XCircle,
  AlertCircle,
  X,
  Activity,
  CheckCircle2,
  Edit3,
  Phone,
  Mail,
  Building2,
  Sparkles,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { StatusBadge } from '@/components/common/StatusBadge';
import { POCGroupCard } from '@/components/events/POCGroupCard';
import {
  EventResponse,
  EventDashboardResponse,
  POCGroupResponse,
  EventStatus,
  EventTransitionRequest,
} from '@/types/event';
import { UserSummary } from '@/types/organization';
import { eventsApi, usersApi } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';

// Canonical Lifecycle Phases
export type EventLifecyclePhase =
  | 'Planning'
  | 'In Progress'
  | 'Execution'
  | 'Event Started'
  | 'Event Closed'
  | 'Completed'
  | 'Cancelled';

export const LIFECYCLE_TIMELINE_PHASES: EventLifecyclePhase[] = [
  'Planning',
  'In Progress',
  'Execution',
  'Event Started',
  'Event Closed',
  'Completed',
];

export const PHASE_DEFAULT_PROGRESS: Record<EventLifecyclePhase, number> = {
  'Planning': 25,
  'In Progress': 45,
  'Execution': 65,
  'Event Started': 80,
  'Event Closed': 95,
  'Completed': 100,
  'Cancelled': 0,
};

export default function EventDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const eventId = resolvedParams.id;
  const { user, roleNames } = useAuth();

  // Role Checks: strictly Sports Core and Deputy Core only, no one else
  const isSportsCoreOrDeputy = roleNames.some((r) =>
    ['SPORTS_CORE', 'DEPUTY_CORE', 'CORE'].includes(r)
  );
  const isEventTeam = roleNames.includes('EVENT_TEAM');

  // Authoritative permissions: Strictly Sports Core and Deputy Core, no one else
  const canManagePOC = isSportsCoreOrDeputy && !isEventTeam;
  const canManageLifecycle = isSportsCoreOrDeputy && !isEventTeam;

  // Data state
  const [event, setEvent] = useState<EventResponse | null>(null);
  const [dashboard, setDashboard] = useState<EventDashboardResponse | null>(null);
  const [pocGroup, setPocGroup] = useState<POCGroupResponse | null>(null);
  const [eligibleUsers, setEligibleUsers] = useState<UserSummary[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Lifecycle Update Modal State (Strictly Sports Core / Deputy Core only)
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [modalPhase, setModalPhase] = useState<EventLifecyclePhase>('Planning');
  const [modalProgress, setModalProgress] = useState<number>(25);
  const [modalRemarks, setModalRemarks] = useState('');
  const [isUpdatingLifecycle, setIsUpdatingLifecycle] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  const loadEventData = useCallback(async () => {
    try {
      const [dashRes, pocRes, usersRes] = await Promise.all([
        eventsApi.getDashboard(eventId),
        eventsApi.getPOCGroup(eventId).catch(() => null),
        usersApi.listUsers({ limit: 100 }).catch(() => ({ total: 0, items: [] })),
      ]);

      setDashboard(dashRes);
      setEvent(dashRes.event);
      setPocGroup(pocRes);
      setEligibleUsers(usersRes.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load event workspace';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    loadEventData();
  }, [loadEventData]);

  // Compute Data-Driven Lifecycle Phase & Progress
  const lifecycleData = useMemo(() => {
    if (!event) {
      return {
        phase: 'Planning' as EventLifecyclePhase,
        progress: 0,
        isCancelled: false,
        phaseIndex: 0,
        statusBadge: 'PLANNING' as EventStatus,
      };
    }

    // Terminal Cancelled State
    if (event.status === 'CANCELLED') {
      return {
        phase: 'Cancelled' as EventLifecyclePhase,
        progress: 0,
        isCancelled: true,
        phaseIndex: -1,
        statusBadge: 'CANCELLED' as EventStatus,
      };
    }

    // Terminal Completed State
    if (event.status === 'COMPLETED' || event.status === 'ARCHIVED') {
      return {
        phase: 'Completed' as EventLifecyclePhase,
        progress: 100,
        isCancelled: false,
        phaseIndex: 5,
        statusBadge: 'COMPLETED' as EventStatus,
      };
    }

    // Explicit phase stored in resource_links
    const savedPhase = event.resource_links?.lifecycle_phase as EventLifecyclePhase | undefined;
    const savedProgress = typeof event.resource_links?.progress === 'number'
      ? event.resource_links.progress
      : null;

    if (savedPhase && LIFECYCLE_TIMELINE_PHASES.includes(savedPhase)) {
      const idx = LIFECYCLE_TIMELINE_PHASES.indexOf(savedPhase);
      return {
        phase: savedPhase,
        progress: savedProgress ?? PHASE_DEFAULT_PROGRESS[savedPhase],
        isCancelled: false,
        phaseIndex: idx,
        statusBadge: event.status,
      };
    }

    // In Planning or Not Started
    if (event.status === 'PLANNING' || event.status === 'NOT_STARTED') {
      const hasHeadPoc = !!(event.primary_poc_id || pocGroup?.head_poc);
      const hasTeam = !!(event.event_team_user_id || event.event_team_name);
      const defaultProg = hasHeadPoc && hasTeam ? 35 : hasHeadPoc || hasTeam ? 25 : 15;
      return {
        phase: 'Planning' as EventLifecyclePhase,
        progress: savedProgress ?? defaultProg,
        isCancelled: false,
        phaseIndex: 0,
        statusBadge: 'PLANNING' as EventStatus,
      };
    }

    // In Progress
    if (event.status === 'IN_PROGRESS') {
      return {
        phase: 'In Progress' as EventLifecyclePhase,
        progress: savedProgress ?? 45,
        isCancelled: false,
        phaseIndex: 1,
        statusBadge: 'IN_PROGRESS' as EventStatus,
      };
    }

    return {
      phase: 'Planning' as EventLifecyclePhase,
      progress: 25,
      isCancelled: false,
      phaseIndex: 0,
      statusBadge: event.status,
    };
  }, [event, pocGroup]);

  // Open Lifecycle Update Modal
  const handleOpenUpdateModal = () => {
    if (!event) return;
    setModalPhase(lifecycleData.phase);
    setModalProgress(lifecycleData.progress);
    setModalRemarks('');
    setUpdateError(null);
    setIsUpdateModalOpen(true);
  };

  // Handle Lifecycle Phase & Status Update
  const handleSaveLifecycle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!event) return;

    setIsUpdatingLifecycle(true);
    setUpdateError(null);

    try {
      // 1. Determine target backend status
      let targetBackendStatus: EventStatus = event.status;
      if (modalPhase === 'Cancelled') {
        targetBackendStatus = 'CANCELLED';
      } else if (modalPhase === 'Completed') {
        targetBackendStatus = 'COMPLETED';
      } else if (modalPhase === 'Planning') {
        targetBackendStatus = 'PLANNING';
      } else {
        // 'In Progress', 'Execution', 'Event Started', 'Event Closed'
        targetBackendStatus = 'IN_PROGRESS';
      }

      // 2. Perform backend transition if status changed
      if (targetBackendStatus !== event.status) {
        // If transitioning from PLANNING to COMPLETED, backend requires PLANNING -> IN_PROGRESS -> COMPLETED
        if (event.status === 'PLANNING' && targetBackendStatus === 'COMPLETED') {
          await eventsApi.transition(eventId, {
            status: 'IN_PROGRESS',
            remarks: 'Auto-advanced to In Progress prior to completion',
          });
        }
        await eventsApi.transition(eventId, {
          status: targetBackendStatus,
          remarks: modalRemarks.trim() || undefined,
        });
      }

      // 3. Persist lifecycle_phase & progress in resource_links
      const currentLinks = (event.resource_links as Record<string, unknown>) || {};
      const updatedLinks = {
        ...currentLinks,
        lifecycle_phase: modalPhase,
        progress: modalProgress,
      };

      await eventsApi.update(eventId, {
        resource_links: updatedLinks,
      });

      setSuccessMessage(`Lifecycle updated to "${modalPhase}" (${modalProgress}% Complete).`);
      setIsUpdateModalOpen(false);
      await loadEventData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update event lifecycle.';
      setUpdateError(msg);
    } finally {
      setIsUpdatingLifecycle(false);
    }
  };

  // Extract external contacts from resource_links
  const resourceLinks = (event?.resource_links as Record<string, unknown>) || {};
  const externalHead = resourceLinks.event_head as
    | { name?: string; phone?: string; email?: string }
    | undefined;
  const externalContacts = (resourceLinks.additional_pocs as Array<{
    name: string;
    phone?: string;
    email?: string;
    designation?: string;
  }>) || [];

  if (isLoading) {
    return (
      <AppShell isEventTeamAllowed={true}>
        <div className="flex h-96 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        </div>
      </AppShell>
    );
  }

  if (error || !event) {
    return (
      <AppShell isEventTeamAllowed={true}>
        <div className="space-y-4 p-4">
          <Link
            href="/events"
            className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Events Catalog
          </Link>
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 dark:border-rose-900/30 dark:bg-rose-950/20">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-rose-600 dark:text-rose-400" />
              <h3 className="text-sm font-bold text-rose-800 dark:text-rose-300">
                {error || 'Event not found'}
              </h3>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      isEventTeamAllowed={true}
      customCrumbs={[
        { label: 'Events', href: '/events' },
        { label: event.name },
      ]}
    >
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        {/* Navigation & Header Actions */}
        <div className="flex items-center justify-between">
          <Link
            href="/events"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-indigo-400"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Events Catalog
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-slate-400">
              Event Ref: <span className="font-mono">{event.id.slice(0, 8)}</span>
            </span>
          </div>
        </div>

        {/* Global Notifications */}
        {successMessage && (
          <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span>{successMessage}</span>
            </div>
            <button
              onClick={() => setSuccessMessage(null)}
              className="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* ========================================================================= */}
        {/* EVENT IDENTITY & STATUS HEADER                                            */}
        {/* ========================================================================= */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md bg-indigo-50 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                  {event.vertical_name || 'General Operations'}
                </span>
                <span className="rounded-md bg-slate-100 px-2.5 py-0.5 text-xs font-semibold uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {event.event_type || 'TOURNAMENT'}
                </span>
                <StatusBadge status={event.status} size="sm" />
              </div>
              <h1 className="text-2xl font-black text-slate-900 dark:text-white sm:text-3xl tracking-tight">
                {event.name}
              </h1>
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 dark:text-slate-400 pt-1">
                {event.planned_date && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5 text-slate-400" />
                    {event.planned_date}
                  </span>
                )}
                {event.start_time && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                    {event.start_time} {event.end_time ? `– ${event.end_time}` : ''}
                  </span>
                )}
                {event.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5 text-slate-400" />
                    {event.location}
                  </span>
                )}
              </div>
            </div>

            {/* Authoritative Action: Only Sports Core and Deputy Core / Admin can update lifecycle */}
            {canManageLifecycle && (
              <div className="flex items-center gap-2 pt-2 md:pt-0 shrink-0">
                <button
                  onClick={handleOpenUpdateModal}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
                >
                  <Edit3 className="h-3.5 w-3.5" />
                  <span>Update Lifecycle Phase</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* PROFESSIONAL EVENT STATUS & PROGRESS DASHBOARD (HERO)                     */}
        {/* ========================================================================= */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-6">
          {/* Top Status & Progress Bar Row */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Current Operational Lifecycle Phase
              </span>
              <div className="flex items-center gap-2.5 mt-0.5">
                <div
                  className={`h-2.5 w-2.5 rounded-full ${
                    lifecycleData.isCancelled
                      ? 'bg-rose-500'
                      : lifecycleData.progress === 100
                      ? 'bg-emerald-500'
                      : 'bg-indigo-600 animate-pulse'
                  }`}
                />
                <span className="text-lg font-bold text-slate-900 dark:text-white">
                  {lifecycleData.phase}
                </span>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
                    lifecycleData.isCancelled
                      ? 'bg-rose-50 text-rose-600 dark:bg-rose-950/50 dark:text-rose-400'
                      : lifecycleData.progress === 100
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                      : 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300'
                  }`}
                >
                  {lifecycleData.isCancelled
                    ? 'CANCELLED'
                    : `${lifecycleData.phase} · ${lifecycleData.progress}% Complete`}
                </span>
              </div>
            </div>

            {/* Numeric Progress KPI */}
            <div className="text-right sm:border-l sm:border-slate-100 sm:pl-6 dark:sm:border-slate-800">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Overall Progress
              </span>
              <div className="text-2xl font-black text-indigo-600 dark:text-indigo-400 mt-0.5">
                {lifecycleData.progress}%
              </div>
            </div>
          </div>

          {/* Animated Progress Bar */}
          <div className="space-y-1.5">
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800/80">
              <div
                className={`h-full transition-all duration-700 rounded-full ${
                  lifecycleData.isCancelled
                    ? 'bg-rose-500'
                    : lifecycleData.progress === 100
                    ? 'bg-emerald-500'
                    : 'bg-gradient-to-r from-indigo-500 via-indigo-600 to-emerald-500'
                }`}
                style={{ width: `${Math.min(Math.max(lifecycleData.progress, 2), 100)}%` }}
              />
            </div>
          </div>

          {/* ===================================================================== */}
          {/* EVENT LIFECYCLE TIMELINE:                                              */}
          {/* Planning → In Progress → Execution → Event Started → Event Closed → Completed */}
          {/* ===================================================================== */}
          <div className="pt-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-4 flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
              Event Lifecycle Progress Timeline
            </h4>

            {lifecycleData.isCancelled ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-4 text-xs text-rose-800 dark:border-rose-900/40 dark:bg-rose-950/20 dark:text-rose-300 flex items-center gap-3">
                <XCircle className="h-5 w-5 text-rose-600 shrink-0" />
                <div>
                  <span className="font-bold">Terminal State: Event Cancelled</span>
                  <p className="text-slate-600 dark:text-slate-400 mt-0.5">
                    This event has been marked as Cancelled. Operational and team assignments are suspended.
                  </p>
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto pb-2">
                <div className="flex items-center min-w-[620px] justify-between relative">
                  {LIFECYCLE_TIMELINE_PHASES.map((p, idx) => {
                    const isCompleted = idx < lifecycleData.phaseIndex;
                    const isCurrent = idx === lifecycleData.phaseIndex;
                    const isUpcoming = idx > lifecycleData.phaseIndex;

                    return (
                      <div key={p} className="flex-1 flex flex-col items-center relative group">
                        {/* Connector line to right (except last step) */}
                        {idx < LIFECYCLE_TIMELINE_PHASES.length - 1 && (
                          <div
                            className={`absolute top-4 left-1/2 w-full h-0.5 -z-0 ${
                              isCompleted
                                ? 'bg-emerald-500'
                                : isCurrent
                                ? 'bg-gradient-to-r from-indigo-600 to-slate-200 dark:to-slate-700'
                                : 'bg-slate-200 dark:bg-slate-800'
                            }`}
                          />
                        )}

                        {/* Step Circle */}
                        <div
                          className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-all ${
                            isCompleted
                              ? 'bg-emerald-500 text-white shadow-sm ring-4 ring-emerald-50 dark:ring-emerald-950/30'
                              : isCurrent
                              ? 'bg-indigo-600 text-white shadow-md ring-4 ring-indigo-500/20 ring-offset-2 dark:ring-offset-slate-900 animate-pulse'
                              : 'border-2 border-slate-200 bg-white text-slate-400 dark:border-slate-800 dark:bg-slate-900'
                          }`}
                        >
                          {isCompleted ? (
                            <Check className="h-4 w-4 stroke-[3]" />
                          ) : (
                            <span>{idx + 1}</span>
                          )}
                        </div>

                        {/* Step Label */}
                        <div className="mt-2 text-center">
                          <p
                            className={`text-xs ${
                              isCurrent
                                ? 'font-black text-indigo-600 dark:text-indigo-400'
                                : isCompleted
                                ? 'font-semibold text-slate-800 dark:text-slate-200'
                                : 'font-medium text-slate-400 dark:text-slate-500'
                            }`}
                          >
                            {p}
                          </p>
                          <span className="text-[10px]">
                            {isCurrent && (
                              <span className="inline-block rounded-full bg-indigo-50 px-2 py-0.2 text-[9px] font-bold text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-300">
                                ACTIVE
                              </span>
                            )}
                            {isCompleted && (
                              <span className="text-emerald-600 dark:text-emerald-400 text-[10px]">
                                Completed
                              </span>
                            )}
                            {isUpcoming && (
                              <span className="text-slate-400 text-[10px]">
                                Pending
                              </span>
                            )}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* COMPACT KEY EVENT INFORMATION GRID                                        */}
        {/* Answers: What is the event? Who is responsible? Who are the POCs?        */}
        {/* ========================================================================= */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Card 1: What is the event? (Logistics & Description) */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2.5 border-b border-slate-100 pb-3 dark:border-slate-800">
                <div className="rounded-lg bg-indigo-50 p-2 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400">
                  <Flag className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Event Overview & Logistics
                  </h3>
                  <p className="text-[11px] text-slate-400">Core parameters and location</p>
                </div>
              </div>

              <div className="mt-4 space-y-3 text-xs">
                <div>
                  <span className="font-semibold text-slate-500 dark:text-slate-400">
                    Event Name:
                  </span>
                  <p className="font-bold text-slate-900 dark:text-white mt-0.5">
                    {event.name}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="font-semibold text-slate-500 dark:text-slate-400">
                      Vertical Division:
                    </span>
                    <p className="font-medium text-slate-800 dark:text-slate-200 mt-0.5">
                      {event.vertical_name || 'General Operations'}
                    </p>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-500 dark:text-slate-400">
                      Event Type:
                    </span>
                    <p className="font-medium text-slate-800 dark:text-slate-200 mt-0.5">
                      {event.event_type || 'TOURNAMENT'}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="font-semibold text-slate-500 dark:text-slate-400">
                      Planned Date:
                    </span>
                    <p className="font-medium text-slate-800 dark:text-slate-200 mt-0.5">
                      {event.planned_date || 'TBD'}
                    </p>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-500 dark:text-slate-400">
                      Venue / Location:
                    </span>
                    <p className="font-medium text-slate-800 dark:text-slate-200 mt-0.5 truncate">
                      {event.location || 'Venue TBD'}
                    </p>
                  </div>
                </div>

                <div>
                  <span className="font-semibold text-slate-500 dark:text-slate-400">
                    Operational Description:
                  </span>
                  <p className="mt-1 leading-relaxed text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-lg">
                    {event.description || 'No detailed description specified.'}
                  </p>
                </div>
              </div>
            </div>

            {event.remarks && (
              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Remarks: </span>
                {event.remarks}
              </div>
            )}
          </div>

          {/* Card 2: Who is responsible? (Event Team Account & External Leadership) */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
            <div className="flex items-center gap-2.5 border-b border-slate-100 pb-3 dark:border-slate-800">
              <div className="rounded-lg bg-amber-50 p-2 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400">
                <Shield className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  Event Team & External Leadership
                </h3>
                <p className="text-[11px] text-slate-400">Designated team identity and organizers</p>
              </div>
            </div>

            {/* Event Team Account Identity */}
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Dedicated Event Team Account
              </span>
              {event.event_team_username || event.event_team_name ? (
                <div className="mt-1.5 p-3 rounded-xl border border-amber-200/80 bg-amber-50/50 dark:border-amber-900/40 dark:bg-amber-950/20 flex items-center justify-between">
                  <div>
                    <p className="font-bold text-xs text-slate-900 dark:text-white">
                      {event.event_team_name || event.event_team_username}
                    </p>
                    <p className="text-[11px] text-amber-700 dark:text-amber-400 font-medium">
                      @{event.event_team_username}
                    </p>
                  </div>
                  <span className="rounded bg-amber-100 px-2 py-0.5 text-[9px] font-bold text-amber-800 dark:bg-amber-900/60 dark:text-amber-300">
                    EVENT_TEAM
                  </span>
                </div>
              ) : (
                <div className="mt-1.5 p-3 rounded-lg bg-slate-50 text-xs italic text-slate-400 dark:bg-slate-800/40">
                  No Event Team account linked to this event.
                </div>
              )}
            </div>

            {/* External Event Head (Event Contact) */}
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Primary Event Contact (External Head)
              </span>
              {externalHead?.name ? (
                <div className="mt-1.5 p-3 rounded-xl border border-slate-100 bg-slate-50/60 dark:border-slate-800 dark:bg-slate-800/30 text-xs space-y-1">
                  <div className="font-bold text-slate-900 dark:text-white">
                    {externalHead.name}
                  </div>
                  {externalHead.phone && (
                    <div className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                      <Phone className="h-3 w-3 text-slate-400" />
                      <span>{externalHead.phone}</span>
                    </div>
                  )}
                  {externalHead.email && (
                    <div className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                      <Mail className="h-3 w-3 text-slate-400" />
                      <span>{externalHead.email}</span>
                    </div>
                  )}
                </div>
              ) : (
                <p className="mt-1 text-xs italic text-slate-400">
                  No external event head registered.
                </p>
              )}
            </div>

            {/* Additional External Contacts */}
            {externalContacts.length > 0 && (
              <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Additional External Contacts ({externalContacts.length})
                </span>
                <div className="mt-1.5 space-y-1 max-h-32 overflow-y-auto pr-1">
                  {externalContacts.map((c, i) => (
                    <div
                      key={i}
                      className="p-2 rounded border border-slate-100 bg-slate-50/40 text-[11px] flex items-center justify-between dark:border-slate-800 dark:bg-slate-800/20"
                    >
                      <span className="font-medium text-slate-800 dark:text-slate-200 truncate">
                        {c.name}
                      </span>
                      <div className="flex items-center gap-2 text-slate-400 text-[10px]">
                        {c.phone && <span>{c.phone}</span>}
                        {c.email && <span>{c.email}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Card 3: Who are the POCs? (Internal Operational Supervision) */}
          <div className="lg:col-span-1">
            <POCGroupCard
              pocGroup={pocGroup}
              eventId={event.id}
              verticalId={event.vertical_id}
              canManage={canManagePOC}
              eligibleUsers={eligibleUsers}
              onUpdated={loadEventData}
            />
          </div>
        </div>

        {/* ========================================================================= */}
        {/* LIFECYCLE PHASE & STATUS TRANSITION MODAL                                 */}
        {/* (Strictly for Sports Core / Deputy Core / Admin)                          */}
        {/* ========================================================================= */}
        {isUpdateModalOpen && canManageLifecycle && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    Update Event Lifecycle Phase
                  </h3>
                </div>
                <button
                  onClick={() => setIsUpdateModalOpen(false)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {updateError && (
                <div className="mt-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 dark:bg-rose-950/30 dark:border-rose-900 dark:text-rose-300">
                  {updateError}
                </div>
              )}

              <form onSubmit={handleSaveLifecycle} className="mt-4 space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                    Target Lifecycle Phase
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      'Planning',
                      'In Progress',
                      'Execution',
                      'Event Started',
                      'Event Closed',
                      'Completed',
                      'Cancelled',
                    ].map((phaseName) => {
                      const isSel = modalPhase === phaseName;
                      const isCancel = phaseName === 'Cancelled';
                      return (
                        <button
                          key={phaseName}
                          type="button"
                          onClick={() => {
                            setModalPhase(phaseName as EventLifecyclePhase);
                            setModalProgress(
                              PHASE_DEFAULT_PROGRESS[phaseName as EventLifecyclePhase]
                            );
                          }}
                          className={`p-2.5 rounded-xl border text-left font-medium transition-all ${
                            isSel
                              ? isCancel
                                ? 'border-rose-500 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                                : 'border-indigo-600 bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300 ring-1 ring-indigo-500'
                              : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-300'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span>{phaseName}</span>
                            {isSel && <Check className="h-3.5 w-3.5" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                      Progress Completion (%)
                    </label>
                    <span className="font-bold text-indigo-600 dark:text-indigo-400">
                      {modalProgress}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={modalProgress}
                    onChange={(e) => setModalProgress(Number(e.target.value))}
                    className="w-full accent-indigo-600 cursor-pointer"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Transition Remarks (Optional Audit Log)
                  </label>
                  <textarea
                    rows={2}
                    value={modalRemarks}
                    onChange={(e) => setModalRemarks(e.target.value)}
                    placeholder="Enter notes on operational progress, milestones achieved, or transition reasons..."
                    className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                  <button
                    type="button"
                    onClick={() => setIsUpdateModalOpen(false)}
                    disabled={isUpdatingLifecycle}
                    className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isUpdatingLifecycle}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 shadow-sm"
                  >
                    {isUpdatingLifecycle ? 'Updating...' : 'Save Lifecycle Update'}
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
