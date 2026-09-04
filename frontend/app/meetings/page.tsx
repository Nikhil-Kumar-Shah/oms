'use client';

/**
 * Operational Meetings & Actions Workspace (/meetings)
 * Meeting schedules, RSVP tracking, participant rosters, minutes,
 * action item assignments, and direct 1-click task conversion.
 */

import React, { useState, useEffect } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { EmptyState } from '@/components/common/EmptyState';
import { UniversalAudienceSelector, AudienceItem, VerticalSelector } from '@/components/selectors';
import { UniversalAudienceSelection } from '@/types/organization';
import { useAuth } from '@/providers/AuthProvider';
import { meetingsApi, organizationApi, eventsApi, ApiException } from '@/lib/api';
import {
  MeetingResponse,
  MeetingType,
  RSVPStatus,
  MeetingActionItem,
} from '@/types/meeting';
import { Vertical } from '@/types/organization';
import { EventResponse } from '@/types/event';
import {
  Users,
  Calendar as CalendarIcon,
  MapPin,
  Video,
  Plus,
  RefreshCw,
  CheckCircle2,
  XCircle,
  HelpCircle,
  CheckSquare,
  ArrowRight,
} from 'lucide-react';

const MEETING_TYPE_LABELS: Record<MeetingType, string> = {
  INTERNAL_SYNC: 'Internal Sync',
  VERTICAL_REVIEW: 'Vertical Review',
  CORE_COORDINATION: 'Core Coordination',
  CROSS_VERTICAL: 'Cross-Vertical',
  EVENT_BRIEFING: 'Event Briefing',
  DEBRIEF: 'Post-Event Debrief',
  EMERGENCY: 'Emergency Sync',
  EVENT_TEAM_SYNC: 'Event Team Sync',
  ORIENTING: 'Orientation',
  OTHER: 'Operational Meeting',
};

const RSVP_BADGES: Record<RSVPStatus, { label: string; bg: string; text: string }> = {
  ACCEPTED: { label: 'Accepted', bg: 'bg-emerald-100 dark:bg-emerald-950/60', text: 'text-emerald-700 dark:text-emerald-300' },
  DECLINED: { label: 'Declined', bg: 'bg-rose-100 dark:bg-rose-950/60', text: 'text-rose-700 dark:text-rose-300' },
  TENTATIVE: { label: 'Tentative', bg: 'bg-amber-100 dark:bg-amber-950/60', text: 'text-amber-700 dark:text-amber-300' },
  PENDING: { label: 'Awaiting RSVP', bg: 'bg-zinc-100 dark:bg-zinc-800', text: 'text-zinc-600 dark:text-zinc-400' },
};

export default function MeetingsPage() {
  const { user, hasPermission, primaryVertical } = useAuth();

  const [meetings, setMeetings] = useState<MeetingResponse[]>([]);
  const [, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'upcoming' | 'past'>('upcoming');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Aux data
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [, setEvents] = useState<EventResponse[]>([]);

  // Selected Detail Modal
  const [selectedMeeting, setSelectedMeeting] = useState<MeetingResponse | null>(null);
  const [, setDetailLoading] = useState<boolean>(false);
  const [rsvpLoading, setRsvpLoading] = useState<boolean>(false);

  // Action Item Creation state in Detail Modal
  const [newActionDesc, setNewActionDesc] = useState<string>('');
  const [newActionAssignee, setNewActionAssignee] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<boolean>(false);

  // Schedule Meeting Modal State
  const [isScheduleOpen, setIsScheduleOpen] = useState<boolean>(false);
  const [scheduleLoading, setScheduleLoading] = useState<boolean>(false);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [selectedParticipants, setSelectedParticipants] = useState<Array<{ value: string; label: string }>>([]);
  const [selectedAudience, setSelectedAudience] = useState<AudienceItem[]>([]);
  const [structuredAudience, setStructuredAudience] = useState<UniversalAudienceSelection>({});
  const [scheduleForm, setScheduleForm] = useState<{
    title: string;
    description: string;
    meeting_type: MeetingType;
    meeting_date: string;
    start_time: string;
    end_time: string;
    location: string;
    meeting_url: string;
    vertical_id: string;
    event_id: string;
    remarks: string;
  }>({
    title: '',
    description: '',
    meeting_type: 'INTERNAL_SYNC',
    meeting_date: new Date().toISOString().split('T')[0],
    start_time: '10:00',
    end_time: '11:00',
    location: '',
    meeting_url: '',
    vertical_id: primaryVertical?.id || '',
    event_id: '',
    remarks: '',
  });

  useEffect(() => {
    organizationApi.listVerticals({ status: 'ACTIVE' }).then((r) => setVerticals(r.items || [])).catch(() => {});
    eventsApi.list({ limit: 50 }).then((r) => setEvents(r.items || [])).catch(() => {});
  }, []);

  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        const res = await meetingsApi.list({
          meeting_type: typeFilter !== 'ALL' ? (typeFilter as MeetingType) : undefined,
          limit: 100,
        });
        if (!ignore) {
          setMeetings(res.items || []);
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
  }, [typeFilter, refreshTrigger]);

  const fetchMeetings = () => {
    setLoading(true);
    setErrorMsg(null);
    setRefreshTrigger((prev) => prev + 1);
  };

  const openDetail = async (m: MeetingResponse) => {
    setSelectedMeeting(m);
    setDetailLoading(true);
    try {
      const fresh = await meetingsApi.getById(m.id);
      setSelectedMeeting(fresh);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleRSVP = async (rsvp_status: RSVPStatus) => {
    if (!selectedMeeting) return;
    setRsvpLoading(true);
    try {
      const updated = await meetingsApi.rsvp(selectedMeeting.id, { rsvp_status });
      setSelectedMeeting(updated);
      setSuccessMsg(`RSVP updated to ${rsvp_status}`);
      fetchMeetings();
    } catch (err) {
      if (err instanceof ApiException) setErrorMsg(err.message);
    } finally {
      setRsvpLoading(false);
    }
  };

  const handleAddActionItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMeeting || !newActionDesc.trim()) return;
    setActionLoading(true);
    try {
      await meetingsApi.addActionItem(selectedMeeting.id, {
        description: newActionDesc.trim(),
        assignee_id: newActionAssignee || undefined,
        priority: 'MEDIUM',
      });
      const fresh = await meetingsApi.getById(selectedMeeting.id);
      setSelectedMeeting(fresh);
      setNewActionDesc('');
      setNewActionAssignee('');
      setSuccessMsg('Action item recorded.');
    } catch (err) {
      if (err instanceof ApiException) setErrorMsg(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleConvertToTask = async (action: MeetingActionItem) => {
    if (!selectedMeeting) return;
    try {
      await meetingsApi.convertActionToTask(action.id, {
        vertical_id: selectedMeeting.vertical_id,
        assigned_to_id: action.assignee_id,
        title: action.description,
      });
      const fresh = await meetingsApi.getById(selectedMeeting.id);
      setSelectedMeeting(fresh);
      setSuccessMsg('Action item converted into Master Task!');
    } catch (err) {
      if (err instanceof ApiException) setErrorMsg(err.message);
    }
  };

  const handleScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduleForm.title.trim()) {
      setScheduleError('Please enter a meeting title.');
      return;
    }

    setScheduleLoading(true);
    setScheduleError(null);
    try {
      await meetingsApi.create({
        title: scheduleForm.title.trim(),
        description: scheduleForm.description.trim() || undefined,
        meeting_type: scheduleForm.meeting_type,
        meeting_date: scheduleForm.meeting_date,
        start_time: scheduleForm.start_time
          ? scheduleForm.start_time.length === 5
            ? `${scheduleForm.start_time}:00`
            : scheduleForm.start_time
          : undefined,
        end_time: scheduleForm.end_time
          ? scheduleForm.end_time.length === 5
            ? `${scheduleForm.end_time}:00`
            : scheduleForm.end_time
          : undefined,
        location: scheduleForm.location.trim() || undefined,
        meeting_url: scheduleForm.meeting_url.trim() || undefined,
        vertical_id: scheduleForm.vertical_id || undefined,
        event_id: scheduleForm.event_id || undefined,
        participant_ids: structuredAudience.user_ids || [],
        include_all_organization: !!structuredAudience.include_all,
        target_vertical_ids: structuredAudience.vertical_ids || [],
        target_roles: structuredAudience.role_ids || [],
        target_role_vertical_pairs: structuredAudience.role_vertical_pairs || [],
        remarks: scheduleForm.remarks.trim() || undefined,
      });

      setSuccessMsg('Meeting scheduled successfully.');
      setIsScheduleOpen(false);
      setScheduleForm({
        title: '',
        description: '',
        meeting_type: 'INTERNAL_SYNC',
        meeting_date: new Date().toISOString().split('T')[0],
        start_time: '10:00',
        end_time: '11:00',
        location: '',
        meeting_url: '',
        vertical_id: primaryVertical?.id || '',
        event_id: '',
        remarks: '',
      });
      setSelectedParticipants([]);
      setSelectedAudience([]);
      setStructuredAudience({});
      fetchMeetings();
    } catch (err) {
      if (err instanceof ApiException) setScheduleError(err.message);
      else if (err instanceof Error) setScheduleError(err.message);
    } finally {
      setScheduleLoading(false);
    }
  };

  const todayStr = new Date().toISOString().split('T')[0];
  const displayedMeetings = meetings.filter((m) => {
    if (activeTab === 'upcoming') {
      return m.meeting_date >= todayStr && m.status !== 'CANCELLED';
    } else {
      return m.meeting_date < todayStr || m.status === 'CANCELLED' || m.status === 'COMPLETED';
    }
  });

  const canCreate = hasPermission('meetings.create');

  return (
    <AppShell requiredPermission="meetings.read" isEventTeamAllowed={true}>
      <div className="space-y-6">

        {/* Header Title Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-sky-950/25 via-indigo-950/15 to-transparent border border-sky-200/50 dark:border-sky-900/40">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400">
                <Users className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                Meetings & Coordination
              </h1>
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Department schedules, match briefings, attendee RSVP tracking, minutes, and action items.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchMeetings}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
            {canCreate && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setScheduleError(null);
                  setScheduleForm((prev) => ({
                    ...prev,
                    vertical_id: primaryVertical?.id || verticals[0]?.id || '',
                  }));
                  setIsScheduleOpen(true);
                }}
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                Schedule Meeting
              </Button>
            )}
          </div>
        </div>

        {/* Notices */}
        {errorMsg && (
          <Alert variant="danger" title="Notice" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" title="Success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {/* Tabs & Filters */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('upcoming')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'upcoming'
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:text-zinc-900'
              }`}
            >
              Upcoming Meetings
            </button>
            <button
              onClick={() => setActiveTab('past')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'past'
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:text-zinc-900'
              }`}
            >
              Past & Completed
            </button>
          </div>

          <div className="w-full sm:w-48">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full px-3 py-1.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="ALL">All Meeting Types</option>
              <option value="INTERNAL_SYNC">Internal Sync</option>
              <option value="CROSS_VERTICAL">Cross-Vertical</option>
              <option value="EVENT_BRIEFING">Event Briefing</option>
              <option value="DEBRIEF">Post-Event Debrief</option>
              <option value="EMERGENCY">Emergency Sync</option>
            </select>
          </div>
        </div>

        {/* Meeting Cards Grid */}
        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center gap-2 text-zinc-400">
            <Spinner size="lg" />
            <p className="text-xs">Loading meetings roster...</p>
          </div>
        ) : displayedMeetings.length === 0 ? (
          <EmptyState
            title={activeTab === 'upcoming' ? 'No upcoming meetings scheduled' : 'No past meeting records'}
            description={
              activeTab === 'upcoming'
                ? 'There are currently no upcoming operational syncs or event briefings scheduled.'
                : 'No completed or archived meetings found.'
            }
            actionLabel={canCreate && activeTab === 'upcoming' ? 'Schedule Meeting' : undefined}
            onAction={canCreate && activeTab === 'upcoming' ? () => setIsScheduleOpen(true) : undefined}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {displayedMeetings.map((m) => {
              const myParticipant = m.participants?.find((p) => p.user_id === user?.id);
              const rsvp = myParticipant?.rsvp_status || (m.organizer_id === user?.id ? 'ACCEPTED' : 'PENDING');
              const rsvpBadge = RSVP_BADGES[rsvp] || RSVP_BADGES.PENDING;

              return (
                <Card
                  key={m.id}
                  className="hover:border-sky-300 dark:hover:border-sky-800 transition-all cursor-pointer flex flex-col justify-between"
                  onClick={() => openDetail(m)}
                >
                  <CardHeader className="p-4 pb-2 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
                        {MEETING_TYPE_LABELS[m.meeting_type] || m.meeting_type}
                      </span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${rsvpBadge.bg} ${rsvpBadge.text}`}>
                        {rsvpBadge.label}
                      </span>
                    </div>

                    <CardTitle className="text-sm font-bold text-zinc-900 dark:text-zinc-100 line-clamp-1">
                      {m.title}
                    </CardTitle>
                  </CardHeader>

                  <CardContent className="p-4 pt-0 space-y-3 text-xs">
                    {m.description && (
                      <p className="text-zinc-500 dark:text-zinc-400 line-clamp-2 text-[11px]">
                        {m.description}
                      </p>
                    )}

                    <div className="space-y-1.5 text-[11px] text-zinc-600 dark:text-zinc-400">
                      <div className="flex items-center gap-1.5 font-medium text-zinc-800 dark:text-zinc-200">
                        <CalendarIcon className="w-3.5 h-3.5 text-sky-500" />
                        <span>{new Date(m.meeting_date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>
                        {m.start_time && <span>• {m.start_time.slice(0, 5)}</span>}
                      </div>

                      {m.location && (
                        <div className="flex items-center gap-1.5 truncate">
                          <MapPin className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                          <span className="truncate">{m.location}</span>
                        </div>
                      )}

                      {m.meeting_url && (
                        <div className="flex items-center gap-1.5 text-sky-600 dark:text-sky-400 font-medium">
                          <Video className="w-3.5 h-3.5 shrink-0" />
                          <span>Video Conference</span>
                        </div>
                      )}
                    </div>

                    <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800 flex items-center justify-between text-[11px]">
                      <span className="text-zinc-400">
                        {m.participants?.length || 0} attendees
                      </span>
                      <span className="text-sky-600 dark:text-sky-400 font-semibold flex items-center gap-1">
                        View Details <ArrowRight className="w-3 h-3" />
                      </span>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {/* ------------------------------------------------------------------ */}
        {/* 1. MEETING DETAIL & ACTION ITEMS MODAL                             */}
        {/* ------------------------------------------------------------------ */}
        <Modal
          isOpen={!!selectedMeeting}
          onClose={() => setSelectedMeeting(null)}
          title={selectedMeeting?.title || 'Meeting Details'}
          description={`${MEETING_TYPE_LABELS[selectedMeeting?.meeting_type || 'INTERNAL_SYNC']} • ${selectedMeeting ? new Date(selectedMeeting.meeting_date).toLocaleDateString() : ''}`}
          size="lg"
        >
          {selectedMeeting && (
            <div className="space-y-5 text-xs">
              {/* Meeting Meta Card */}
              <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <span className="text-zinc-400 block text-[10px] uppercase font-bold">Date & Time</span>
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                      {new Date(selectedMeeting.meeting_date).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                    </span>
                    {selectedMeeting.start_time && (
                      <p className="text-zinc-500 text-[11px]">
                        {selectedMeeting.start_time.slice(0, 5)} {selectedMeeting.end_time ? `- ${selectedMeeting.end_time.slice(0, 5)}` : ''}
                      </p>
                    )}
                  </div>

                  <div>
                    <span className="text-zinc-400 block text-[10px] uppercase font-bold">Organizer</span>
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                      {selectedMeeting.organizer_name || `@${selectedMeeting.organizer_username}`}
                    </span>
                    {selectedMeeting.vertical_name && (
                      <p className="text-zinc-500 text-[11px]">{selectedMeeting.vertical_name}</p>
                    )}
                  </div>
                </div>

                {selectedMeeting.location && (
                  <div className="flex items-center gap-1.5 text-zinc-700 dark:text-zinc-300">
                    <MapPin className="w-3.5 h-3.5 text-zinc-400" />
                    <span>Location: <strong>{selectedMeeting.location}</strong></span>
                  </div>
                )}

                {selectedMeeting.meeting_url && (
                  <div className="flex items-center gap-2">
                    <Video className="w-3.5 h-3.5 text-sky-500" />
                    <a
                      href={selectedMeeting.meeting_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sky-600 dark:text-sky-400 font-semibold underline truncate"
                    >
                      Join Video Meeting: {selectedMeeting.meeting_url}
                    </a>
                  </div>
                )}
              </div>

              {/* RSVP Action Bar */}
              <div className="p-3.5 rounded-xl bg-sky-50 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-800 flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <span className="font-bold text-sky-950 dark:text-sky-200 text-xs">Your Attendance Response:</span>
                  <p className="text-[11px] text-sky-700 dark:text-sky-400">
                    Confirm your attendance to notify the meeting organizer.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRSVP('ACCEPTED')}
                    disabled={rsvpLoading}
                    leftIcon={<CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                  >
                    Accept
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRSVP('TENTATIVE')}
                    disabled={rsvpLoading}
                    leftIcon={<HelpCircle className="w-3.5 h-3.5 text-amber-500" />}
                  >
                    Tentative
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRSVP('DECLINED')}
                    disabled={rsvpLoading}
                    leftIcon={<XCircle className="w-3.5 h-3.5 text-rose-500" />}
                  >
                    Decline
                  </Button>
                </div>
              </div>

              {/* Description */}
              {selectedMeeting.description && (
                <div className="space-y-1">
                  <label className="font-bold text-zinc-700 dark:text-zinc-300 block uppercase tracking-wider text-[10px]">
                    Agenda & Objectives
                  </label>
                  <p className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800 leading-relaxed whitespace-pre-line text-zinc-900 dark:text-zinc-100">
                    {selectedMeeting.description}
                  </p>
                </div>
              )}

              {/* Attendees Roster */}
              <div className="space-y-2">
                <label className="font-bold text-zinc-700 dark:text-zinc-300 block uppercase tracking-wider text-[10px]">
                  Attendees Roster ({selectedMeeting.participants?.length || 0})
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-36 overflow-y-auto p-1">
                  {selectedMeeting.participants?.map((p) => {
                    const badge = RSVP_BADGES[p.rsvp_status] || RSVP_BADGES.PENDING;
                    return (
                      <div
                        key={p.id}
                        className="flex items-center justify-between p-2 rounded-lg bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-[11px]"
                      >
                        <span className="font-medium text-zinc-800 dark:text-zinc-200">
                          {p.full_name || `@${p.username}`}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${badge.bg} ${badge.text}`}>
                          {badge.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Action Items & 1-Click Task Conversion */}
              <div className="space-y-3 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                    <CheckSquare className="w-4 h-4 text-indigo-500" />
                    Meeting Action Items ({selectedMeeting.action_items?.length || 0})
                  </h4>
                </div>

                {selectedMeeting.action_items?.length === 0 ? (
                  <p className="text-zinc-400 italic text-[11px]">No action items recorded for this meeting.</p>
                ) : (
                  <div className="space-y-2">
                    {selectedMeeting.action_items?.map((act) => (
                      <div
                        key={act.id}
                        className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 flex items-center justify-between gap-3 text-xs"
                      >
                        <div className="space-y-0.5 min-w-0">
                          <p className="font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                            {act.description}
                          </p>
                          <div className="text-[10px] text-zinc-500 flex items-center gap-2">
                            <span>Assignee: {act.assignee_full_name || `@${act.assignee_username}` || 'Unassigned'}</span>
                          </div>
                        </div>

                        <div>
                          {act.is_converted ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-semibold text-[10px]">
                              <CheckCircle2 className="w-3 h-3" /> Master Task Created
                            </span>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleConvertToTask(act)}
                              leftIcon={<CheckSquare className="w-3 h-3 text-indigo-500" />}
                            >
                              Convert to Task
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add Action Item Form */}
                <form onSubmit={handleAddActionItem} className="flex gap-2 pt-1">
                  <input
                    type="text"
                    placeholder="Add an operational action item..."
                    value={newActionDesc}
                    onChange={(e) => setNewActionDesc(e.target.value)}
                    className="flex-1 px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  />
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={!newActionDesc.trim() || actionLoading}
                    isLoading={actionLoading}
                    leftIcon={<Plus className="w-3 h-3" />}
                  >
                    Add Action
                  </Button>
                </form>
              </div>

              <div className="flex justify-end pt-2">
                <Button variant="outline" size="sm" onClick={() => setSelectedMeeting(null)}>
                  Close
                </Button>
              </div>
            </div>
          )}
        </Modal>

        {/* ------------------------------------------------------------------ */}
        {/* 2. SCHEDULE MEETING MODAL                                         */}
        {/* ------------------------------------------------------------------ */}
        <Modal
          isOpen={isScheduleOpen}
          onClose={() => setIsScheduleOpen(false)}
          title="Schedule Operational Meeting"
          description="Coordinate match briefings, sync sessions, or cross-division alignments."
        >
          <form onSubmit={handleScheduleSubmit} className="space-y-4 text-xs">
            {scheduleError && (
              <Alert variant="danger" title="Validation Notice">
                {scheduleError}
              </Alert>
            )}

            <Input
              label="Meeting Title"
              required
              placeholder="e.g. Ground Logistics Briefing - Matchday 3"
              value={scheduleForm.title}
              onChange={(e) => setScheduleForm({ ...scheduleForm, title: e.target.value })}
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300">
                  Meeting Type *
                </label>
                <select
                  value={scheduleForm.meeting_type}
                  onChange={(e) => setScheduleForm({ ...scheduleForm, meeting_type: e.target.value as MeetingType })}
                  className="w-full px-3 py-2 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
                >
                  <option value="INTERNAL_SYNC">Internal Sync</option>
                  <option value="VERTICAL_REVIEW">Vertical Review</option>
                  <option value="CORE_COORDINATION">Core Coordination</option>
                  <option value="CROSS_VERTICAL">Cross-Vertical</option>
                  <option value="EVENT_BRIEFING">Event Briefing</option>
                  <option value="DEBRIEF">Post-Event Debrief</option>
                  <option value="EMERGENCY">Emergency Sync</option>
                  <option value="EVENT_TEAM_SYNC">Event Team Sync</option>
                  <option value="ORIENTING">Orientation</option>
                  <option value="OTHER">Operational Meeting</option>
                </select>
              </div>

              <Input
                label="Meeting Date *"
                type="date"
                required
                value={scheduleForm.meeting_date}
                onChange={(e) => setScheduleForm({ ...scheduleForm, meeting_date: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                label="Start Time (Optional)"
                type="time"
                value={scheduleForm.start_time}
                onChange={(e) => setScheduleForm({ ...scheduleForm, start_time: e.target.value })}
              />
              <Input
                label="End Time (Optional)"
                type="time"
                value={scheduleForm.end_time}
                onChange={(e) => setScheduleForm({ ...scheduleForm, end_time: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                label="Physical Location (Optional)"
                placeholder="e.g. Main Conference Room A"
                value={scheduleForm.location}
                onChange={(e) => setScheduleForm({ ...scheduleForm, location: e.target.value })}
              />
              <Input
                label="Video Meeting Link (Optional)"
                placeholder="https://meet.google.com/..."
                value={scheduleForm.meeting_url}
                onChange={(e) => setScheduleForm({ ...scheduleForm, meeting_url: e.target.value })}
              />
            </div>

            <div className="space-y-1">
              <label className="block font-semibold text-zinc-700 dark:text-zinc-300">
                Agenda & Objectives (Optional)
              </label>
              <textarea
                rows={3}
                placeholder="Outline discussion points, required preparation, or documents to review..."
                value={scheduleForm.description}
                onChange={(e) => setScheduleForm({ ...scheduleForm, description: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>

            {/* Invite Attendees UniversalAudienceSelector */}
            <UniversalAudienceSelector
              usage="audience"
              label="Invite Attendees & Audience Groups"
              description="Invite entire divisions, role groups (e.g. Football → Volunteers), or specific users."
              placeholder="Search and add attendees or audience groups..."
              value={selectedAudience}
              onChange={(items, structured) => {
                setSelectedAudience(items);
                setStructuredAudience(structured);
              }}
            />

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsScheduleOpen(false)}
                disabled={scheduleLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={scheduleLoading}
              >
                Schedule Meeting
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </AppShell>
  );
}
