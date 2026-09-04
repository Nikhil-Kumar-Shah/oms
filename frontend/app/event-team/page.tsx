'use client';

/**
 * Event Team Workspace (/event-team)
 * Requirements:
 * - Admin creates unactivated credentials (unable to log in).
 * - Sports Core / Deputy Core activates account with minimal form:
 *   Event Team Name, Event Head Name, Phone, Email, Event Team Account selector,
 *   Head POC (Universal Selector), Additional POCs (Universal Selector).
 * - Relationship: Event Team -> Event Team Account -> Event Head -> POCs.
 * - Clean Dashboard navigation: Event Overview | POC & Team Roster (No Checkpoints, No Linked Operations).
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Users2,
  Flag,
  Mail,
  Phone,
  Plus,
  CheckCircle2,
  AlertCircle,
  Shield,
  Calendar,
  Layers,
  Search,
  ListTodo,
  Video,
  FileCheck2,
  AlertOctagon,
  RefreshCw,
  UserCheck,
  ExternalLink,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { StatusBadge } from '@/components/common/StatusBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { UserSelector } from '@/components/selectors/UserSelector';
import { EventTeamProfileResponse, UnactivatedAccountResponse } from '@/types/event_team';
import { eventTeamsApi, eventsApi } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { EventResponse } from '@/types/event';

export default function EventTeamPage() {
  const { user, roleNames } = useAuth();

  // Role Checks
  const isAdmin = roleNames.includes('ADMIN');
  const isCoreOrDeputy = roleNames.some((r) => ['SPORTS_CORE', 'DEPUTY_CORE', 'CORE'].includes(r));
  const isEventTeamUser = roleNames.includes('EVENT_TEAM');
  const canActivate = isCoreOrDeputy || isAdmin;

  // State
  const [teams, setTeams] = useState<EventTeamProfileResponse[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<EventTeamProfileResponse | null>(null);
  const [unactivatedAccounts, setUnactivatedAccounts] = useState<UnactivatedAccountResponse[]>([]);
  const [eventsList, setEventsList] = useState<EventResponse[]>([]);
  const [activeDashboardTab, setActiveDashboardTab] = useState<'overview' | 'roster'>('overview');

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>('');

  // Admin: Create Credentials Modal State
  const [isCredsModalOpen, setIsCredsModalOpen] = useState<boolean>(false);
  const [credsForm, setCredsForm] = useState({
    username: '',
    password: '',
    email: '',
    team_name: '',
  });
  const [credsSubmitting, setCredsSubmitting] = useState<boolean>(false);
  const [credsError, setCredsError] = useState<string | null>(null);

  // Sports Core / Deputy Core: Activate Modal State
  const [isActivateModalOpen, setIsActivateModalOpen] = useState<boolean>(false);
  const [activateForm, setActivateForm] = useState({
    team_name: '',
    head_name: '',
    head_phone: '',
    head_email: '',
    user_id: '',
    event_id: '',
  });
  const [headPocId, setHeadPocId] = useState<string>('');
  const [additionalPocIds, setAdditionalPocIds] = useState<string[]>([]);
  const [activateSubmitting, setActivateSubmitting] = useState<boolean>(false);
  const [activateError, setActivateError] = useState<string | null>(null);

  // Load Initial Data
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      if (isEventTeamUser) {
        // Event Team account views their own profile
        const myProfile = await eventTeamsApi.getMyTeam();
        setSelectedTeam(myProfile);
        setTeams([myProfile]);
      } else {
        // Staff view
        const [teamsRes, unactivatedRes, eventsRes] = await Promise.all([
          eventTeamsApi.list({ limit: 100 }),
          canActivate ? eventTeamsApi.getUnactivatedAccounts() : Promise.resolve([]),
          eventsApi.list({ limit: 100 }).catch(() => ({ items: [] })),
        ]);

        const items = teamsRes.items || [];
        setTeams(items);
        setUnactivatedAccounts(unactivatedRes || []);
        setEventsList(eventsRes.items || []);

        // Default selection
        if (items.length > 0 && !selectedTeam) {
          setSelectedTeam(items[0]);
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load Event Team information');
    } finally {
      setIsLoading(false);
    }
  }, [isEventTeamUser, canActivate, selectedTeam]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Admin Credentials Creation
  const handleCreateCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!credsForm.username.trim() || !credsForm.password.trim()) {
      setCredsError('Username and password are required.');
      return;
    }

    setCredsSubmitting(true);
    setCredsError(null);
    try {
      await eventTeamsApi.createCredentials({
        username: credsForm.username.trim(),
        password: credsForm.password.trim(),
        email: credsForm.email.trim() || undefined,
        team_name: credsForm.team_name.trim() || undefined,
      });

      setSuccessMsg(`Event Team credentials created for @${credsForm.username}. Account is unactivated.`);
      setIsCredsModalOpen(false);
      setCredsForm({ username: '', password: '', email: '', team_name: '' });
      loadData();
    } catch (err: any) {
      setCredsError(err.message || 'Failed to create credentials.');
    } finally {
      setCredsSubmitting(false);
    }
  };

  // Handle Sports Core / Deputy Core Activation
  const handleActivateEventTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      !activateForm.team_name.trim() ||
      !activateForm.head_name.trim() ||
      !activateForm.head_phone.trim() ||
      !activateForm.head_email.trim() ||
      !activateForm.user_id
    ) {
      setActivateError('All required fields (Team Name, Head Name, Phone, Email, Account) must be completed.');
      return;
    }

    if (!headPocId) {
      setActivateError('Please select a Head POC using the Universal Selector.');
      return;
    }

    if (!activateForm.event_id) {
      setActivateError('Please select an Event to assign this Event Team to. Event assignment is mandatory for activation.');
      return;
    }

    setActivateSubmitting(true);
    setActivateError(null);
    try {

      const activated = await eventTeamsApi.activate({
        team_name: activateForm.team_name.trim(),
        head_name: activateForm.head_name.trim(),
        head_phone: activateForm.head_phone.trim(),
        head_email: activateForm.head_email.trim(),
        user_id: activateForm.user_id,
        head_poc_id: headPocId,
        additional_poc_ids: additionalPocIds,
        event_id: activateForm.event_id,
      });

      setSuccessMsg(`Event Team "${activated.team_name}" successfully activated! The team may now log in.`);
      setIsActivateModalOpen(false);
      setActivateForm({
        team_name: '',
        head_name: '',
        head_phone: '',
        head_email: '',
        user_id: '',
        event_id: '',
      });
      setHeadPocId('');
      setAdditionalPocIds([]);
      setSelectedTeam(activated);
      loadData();
    } catch (err: any) {
      setActivateError(err.message || 'Failed to activate Event Team account.');
    } finally {
      setActivateSubmitting(false);
    }
  };

  // Filtered teams list for staff
  const filteredTeams = useMemo(() => {
    if (!searchFilter.trim()) return teams;
    const q = searchFilter.toLowerCase();
    return teams.filter(
      (t) =>
        t.team_name.toLowerCase().includes(q) ||
        (t.head_name && t.head_name.toLowerCase().includes(q)) ||
        (t.username && t.username.toLowerCase().includes(q)) ||
        (t.event_name && t.event_name.toLowerCase().includes(q))
    );
  }, [teams, searchFilter]);

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        {/* Top Action Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Users2 className="w-5 h-5 text-primary" />
              Event Team Workspace
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Account activation, POC assignments, and operational activity summaries.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              disabled={isLoading}
              className="gap-1.5 text-xs h-8"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>

            {/* Admin Credential Creation */}
            {isAdmin && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setCredsError(null);
                  setIsCredsModalOpen(true);
                }}
                className="gap-1.5 text-xs h-8"
              >
                <Plus className="w-3.5 h-3.5" />
                Create Team Account
              </Button>
            )}

            {/* Sports Core / Deputy Core Activation */}
            {canActivate && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setActivateError(null);
                  setIsActivateModalOpen(true);
                }}
                className="gap-1.5 text-xs h-8"
              >
                <UserCheck className="w-3.5 h-3.5" />
                Activate Event Team
              </Button>
            )}
          </div>
        </div>

        {/* Global Notifications */}
        {successMsg && (
          <Alert variant="success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}
        {errorMsg && (
          <Alert variant="danger" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        {/* Unactivated Accounts Notice for Core / Admin */}
        {canActivate && unactivatedAccounts.length > 0 && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center justify-between text-xs text-amber-700 dark:text-amber-400">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
              <span>
                <strong>{unactivatedAccounts.length}</strong> Event Team {unactivatedAccounts.length === 1 ? 'account' : 'accounts'} awaiting activation by Sports Core / Deputy Core.
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setActivateError(null);
                setIsActivateModalOpen(true);
              }}
              className="text-xs h-7 border-amber-500/40 text-amber-700 dark:text-amber-300 hover:bg-amber-500/10"
            >
              Activate Now
            </Button>
          </div>
        )}

        {/* Main Content Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Event Teams Browser (Hidden for pure EVENT_TEAM user) */}
          {!isEventTeamUser && (
            <div className="lg:col-span-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Event Teams ({teams.length})
                </span>
              </div>

              {/* Search Bar */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search team, head, event..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Teams List */}
              {isLoading ? (
                <div className="py-12 flex justify-center">
                  <Spinner size="md" />
                </div>
              ) : filteredTeams.length === 0 ? (
                <div className="p-4 text-center text-xs text-muted-foreground border border-dashed border-border rounded-lg">
                  No Event Teams found matching criteria.
                </div>
              ) : (
                <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                  {filteredTeams.map((t) => {
                    const isSelected = selectedTeam?.id === t.id;
                    const isAct = t.is_activated !== false;

                    return (
                      <div
                        key={t.id}
                        onClick={() => setSelectedTeam(t)}
                        className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col gap-1.5 select-none ${
                          isSelected
                            ? 'border-primary bg-primary/5 shadow-sm'
                            : 'border-border bg-card hover:border-border/80'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs text-foreground truncate">
                            {t.team_name}
                          </span>
                          <Badge
                            variant={isAct ? 'default' : 'default'}
                            className={`text-[9px] ${
                              isAct ? 'bg-emerald-500/10 text-emerald-600' : 'bg-amber-500/10 text-amber-600'
                            }`}
                          >
                            {isAct ? 'ACTIVATED' : 'UNACTIVATED'}
                          </Badge>
                        </div>

                        <div className="text-[11px] text-muted-foreground flex items-center justify-between">
                          <span>Head: {t.head_name || 'Not set'}</span>
                          {t.head_poc_username && (
                            <span className="text-primary font-medium">
                              POC: @{t.head_poc_username}
                            </span>
                          )}
                        </div>

                        {t.event_name && (
                          <div className="text-[10px] text-muted-foreground flex items-center gap-1 truncate pt-1 border-t border-border/40">
                            <Flag className="w-3 h-3 text-primary shrink-0" />
                            <span className="truncate">{t.event_name}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Right Column: Clean Event Team Dashboard */}
          <div className={isEventTeamUser ? 'lg:col-span-12 space-y-4' : 'lg:col-span-8 space-y-4'}>
            {isEventTeamUser && (!selectedTeam || !selectedTeam.is_activated || !selectedTeam.event_id || !selectedTeam.head_poc_id) ? (
              <div className="p-8 text-center max-w-lg mx-auto bg-card rounded-2xl border border-amber-200 dark:border-amber-800 shadow-sm space-y-4 my-8">
                <div className="w-14 h-14 rounded-2xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 flex items-center justify-center mx-auto">
                  <AlertOctagon className="w-8 h-8" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-lg font-bold text-foreground">
                    Event Team Account Pending Activation (HTTP 403)
                  </h2>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Your Event Team account has been provisioned, but operational access is currently restricted.
                    Sports Core or Deputy Core must finalize your Event association and designate your responsible Head POC before this dashboard becomes accessible.
                  </p>
                </div>
                <div className="p-3 bg-muted/40 rounded-xl text-left text-[11px] text-muted-foreground space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">Account Status:</span>
                    <Badge variant="default" className="bg-amber-500/10 text-amber-600 text-[10px]">
                      Pending Activation (Inactive)
                    </Badge>
                  </div>
                  <p>Required activation criteria: Assigned Event, designated Head POC, and formal Core leadership activation.</p>
                </div>
              </div>
            ) : !selectedTeam ? (
              <EmptyState
                icon={Users2}
                title="No Event Team Selected"
                description="Select an Event Team from the roster or activate a new account."
              />
            ) : (
              <div className="space-y-4">
                {/* Team Header Card */}
                <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-2">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-bold text-foreground">
                          {selectedTeam.team_name}
                        </h2>
                        <Badge
                          variant="default"
                          className={`text-xs ${
                            selectedTeam.is_activated !== false
                              ? 'bg-emerald-500/10 text-emerald-600'
                              : 'bg-amber-500/10 text-amber-600'
                          }`}
                        >
                          {selectedTeam.is_activated !== false ? 'Active Account' : 'Pending Activation'}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Account: <span className="font-semibold text-foreground">@{selectedTeam.username}</span>
                        {selectedTeam.event_name && (
                          <>
                            {' '}• Event: <span className="font-semibold text-foreground">{selectedTeam.event_name}</span>
                          </>
                        )}
                      </p>
                    </div>

                    {/* Operational Hierarchy Pill */}
                    <div className="text-xs bg-muted/30 px-3 py-1.5 rounded-md border border-border text-muted-foreground">
                      <span className="font-medium text-foreground">{selectedTeam.head_name || 'Event Head'}</span>
                      <span className="mx-1">→</span>
                      <span className="font-medium text-primary">{selectedTeam.head_poc_name || 'Head POC'}</span>
                    </div>
                  </div>
                </div>

                {/* Dashboard Navigation Tabs: ONLY Event Overview | POC & Team Roster */}
                <div className="flex border-b border-border gap-3">
                  <button
                    onClick={() => setActiveDashboardTab('overview')}
                    className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold border-b-2 transition-colors ${
                      activeDashboardTab === 'overview'
                        ? 'border-primary text-primary'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Flag className="w-3.5 h-3.5" />
                    Event Overview
                  </button>

                  <button
                    onClick={() => setActiveDashboardTab('roster')}
                    className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold border-b-2 transition-colors ${
                      activeDashboardTab === 'roster'
                        ? 'border-primary text-primary'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Users2 className="w-3.5 h-3.5" />
                    POC & Team Roster
                  </button>
                </div>

                {/* TAB 1: EVENT OVERVIEW */}
                {activeDashboardTab === 'overview' && (
                  <div className="space-y-4">
                    {/* Operational Activity KPI Counters */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="p-3.5 rounded-lg border border-border bg-card">
                        <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                          <span>Requirements</span>
                          <FileCheck2 className="w-3.5 h-3.5 text-primary" />
                        </div>
                        <div className="text-xl font-bold text-foreground mt-1">
                          {selectedTeam.requirements_count || 0}
                        </div>
                      </div>

                      <div className="p-3.5 rounded-lg border border-border bg-card">
                        <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                          <span>Operational Issues</span>
                          <AlertOctagon className="w-3.5 h-3.5 text-rose-500" />
                        </div>
                        <div className="text-xl font-bold text-foreground mt-1">
                          {selectedTeam.issues_count || 0}
                        </div>
                      </div>

                      <div className="p-3.5 rounded-lg border border-border bg-card">
                        <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                          <span>Meetings</span>
                          <Video className="w-3.5 h-3.5 text-blue-500" />
                        </div>
                        <div className="text-xl font-bold text-foreground mt-1">
                          {selectedTeam.meetings_count || 0}
                        </div>
                      </div>

                      <div className="p-3.5 rounded-lg border border-border bg-card">
                        <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                          <span>Assigned Roster</span>
                          <Users2 className="w-3.5 h-3.5 text-emerald-500" />
                        </div>
                        <div className="text-xl font-bold text-foreground mt-1">
                          {(selectedTeam.members_summary?.length || 0) + (selectedTeam.additional_pocs?.length || 0) + 1}
                        </div>
                      </div>
                    </div>

                    {/* Event Summary Details */}
                    <div className="p-4 rounded-lg border border-border bg-card space-y-3 text-xs">
                      <h4 className="font-bold text-foreground text-sm flex items-center gap-1.5">
                        <Calendar className="w-4 h-4 text-primary" />
                        Event Information & Operational Schedule
                      </h4>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                        <div>
                          <span className="font-semibold text-muted-foreground">Event Name:</span>{' '}
                          <span className="text-foreground font-medium">
                            {selectedTeam.event_name || 'Unassigned Event'}
                          </span>
                        </div>
                        <div>
                          <span className="font-semibold text-muted-foreground">Event Status:</span>{' '}
                          {selectedTeam.event_status ? (
                            <StatusBadge status={selectedTeam.event_status} />
                          ) : (
                            <span className="text-muted-foreground">None</span>
                          )}
                        </div>
                        <div>
                          <span className="font-semibold text-muted-foreground">Planned Date:</span>{' '}
                          <span className="text-foreground font-medium">
                            {selectedTeam.event_date || 'TBD'}
                          </span>
                        </div>
                        <div>
                          <span className="font-semibold text-muted-foreground">Head POC:</span>{' '}
                          <span className="text-foreground font-medium">
                            {selectedTeam.head_poc_name || 'Unassigned'}
                            {selectedTeam.head_poc_username && ` (@${selectedTeam.head_poc_username})`}
                          </span>
                        </div>
                      </div>

                      {selectedTeam.notes && (
                        <div className="pt-2 border-t border-border/50">
                          <span className="font-semibold text-muted-foreground">Operational Remarks:</span>
                          <p className="mt-1 text-foreground bg-muted/20 p-2.5 rounded">
                            {selectedTeam.notes}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* TAB 2: POC & TEAM ROSTER */}
                {activeDashboardTab === 'roster' && (
                  <div className="space-y-4 text-xs">
                    {/* Event Head Card */}
                    <Card className="border border-border">
                      <CardHeader className="border-b border-border/50 pb-2">
                        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                          Event Head (External Lead)
                        </span>
                      </CardHeader>
                      <CardContent className="pt-3">
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <div>
                            <span className="text-muted-foreground font-medium">Head Name:</span>
                            <div className="text-foreground font-bold mt-0.5">
                              {selectedTeam.head_name || 'Not specified'}
                            </div>
                          </div>
                          <div>
                            <span className="text-muted-foreground font-medium">Phone Number:</span>
                            <div className="text-foreground font-medium mt-0.5 flex items-center gap-1">
                              <Phone className="w-3 h-3 text-muted-foreground" />
                              {selectedTeam.head_phone || 'None'}
                            </div>
                          </div>
                          <div>
                            <span className="text-muted-foreground font-medium">Email Address:</span>
                            <div className="text-foreground font-medium mt-0.5 flex items-center gap-1">
                              <Mail className="w-3 h-3 text-muted-foreground" />
                              {selectedTeam.head_email || 'None'}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Assigned POCs Cards */}
                    <Card className="border border-border">
                      <CardHeader className="border-b border-border/50 pb-2">
                        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                          Designated Points of Contact (POCs)
                        </span>
                      </CardHeader>
                      <CardContent className="pt-3 space-y-3">
                        {/* Head POC */}
                        <div className="p-3 bg-primary/5 rounded-lg border border-primary/20 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-foreground">
                                {selectedTeam.head_poc_name || 'Head POC'}
                              </span>
                              <Badge variant="default" className="text-[9px]">
                                PRIMARY HEAD POC
                              </Badge>
                            </div>
                            <div className="text-muted-foreground mt-0.5">
                              Handle: @{selectedTeam.head_poc_username || 'unassigned'}
                            </div>
                          </div>
                        </div>

                        {/* Additional POCs */}
                        {selectedTeam.additional_pocs && selectedTeam.additional_pocs.length > 0 ? (
                          <div className="space-y-2">
                            <span className="text-muted-foreground font-semibold">Additional POCs:</span>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {selectedTeam.additional_pocs.map((poc) => (
                                <div
                                  key={poc.id}
                                  className="p-2.5 rounded-md border border-border bg-card flex items-center justify-between"
                                >
                                  <div>
                                    <div className="font-medium text-foreground">{poc.name}</div>
                                    <div className="text-muted-foreground text-[11px]">@{poc.username}</div>
                                  </div>
                                  {poc.email && (
                                    <span className="text-muted-foreground text-[10px]">{poc.email}</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-muted-foreground italic text-xs">
                            No additional POCs designated.
                          </p>
                        )}
                      </CardContent>
                    </Card>

                    {/* Assigned Event Team Members Roster */}
                    <Card className="border border-border">
                      <CardHeader className="border-b border-border/50 pb-2">
                        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                          Event Team Members Summary ({selectedTeam.members_summary?.length || 0})
                        </span>
                      </CardHeader>
                      <CardContent className="pt-3">
                        {selectedTeam.members_summary && selectedTeam.members_summary.length > 0 ? (
                          <div className="space-y-1.5">
                            {selectedTeam.members_summary.map((m, idx) => (
                              <div
                                key={idx}
                                className="p-2 rounded border border-border/60 bg-muted/20 flex items-center justify-between"
                              >
                                <span className="font-medium text-foreground">{m.name}</span>
                                <div className="flex items-center gap-2">
                                  <Badge variant="default" className="text-[10px]">
                                    {m.role || 'Member'}
                                  </Badge>
                                  {m.contact && (
                                    <span className="text-muted-foreground">{m.contact}</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-muted-foreground italic text-xs">
                            No team members summary registered for this Event Team.
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* MODAL 1: ADMIN CREATE EVENT TEAM CREDENTIALS (UNACTIVATED)                 */}
        {/* ========================================================================= */}
        <Modal
          isOpen={isCredsModalOpen}
          onClose={() => setIsCredsModalOpen(false)}
          title="Create Event Team Account Credentials"
        >
          <form onSubmit={handleCreateCredentials} className="space-y-3 text-xs">
            {credsError && (
              <Alert variant="danger" onClose={() => setCredsError(null)}>
                {credsError}
              </Alert>
            )}

            <div className="p-2.5 rounded bg-muted/30 border border-border text-muted-foreground space-y-1">
              <span className="font-semibold text-foreground">Admin Provisioning Notice:</span>
              <p>
                Credentials created here remain <strong>unactivated</strong> with login blocked. Sports Core or Deputy Core will activate this account and designate the POC group.
              </p>
            </div>

            <div>
              <label className="block font-semibold text-foreground mb-1">
                Event Team Name (Optional)
              </label>
              <Input
                value={credsForm.team_name}
                onChange={(e) => setCredsForm({ ...credsForm, team_name: e.target.value })}
                placeholder="e.g. Strikers FC"
                className="text-xs h-8"
              />
            </div>

            <div>
              <label className="block font-semibold text-foreground mb-1">
                Username <span className="text-rose-500">*</span>
              </label>
              <Input
                required
                value={credsForm.username}
                onChange={(e) => setCredsForm({ ...credsForm, username: e.target.value })}
                placeholder="e.g. team_strikers"
                className="text-xs h-8"
              />
            </div>

            <div>
              <label className="block font-semibold text-foreground mb-1">
                Password <span className="text-rose-500">*</span>
              </label>
              <Input
                required
                type="password"
                value={credsForm.password}
                onChange={(e) => setCredsForm({ ...credsForm, password: e.target.value })}
                placeholder="Minimum 8 characters"
                className="text-xs h-8"
              />
            </div>

            <div>
              <label className="block font-semibold text-foreground mb-1">
                Account Email (Optional)
              </label>
              <Input
                type="email"
                value={credsForm.email}
                onChange={(e) => setCredsForm({ ...credsForm, email: e.target.value })}
                placeholder="team@example.com"
                className="text-xs h-8"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsCredsModalOpen(false)}
                disabled={credsSubmitting}
                className="text-xs h-8"
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" disabled={credsSubmitting} className="text-xs h-8">
                {credsSubmitting ? 'Creating...' : 'Create Credentials'}
              </Button>
            </div>
          </form>
        </Modal>

        {/* ========================================================================= */}
        {/* MODAL 2: SPORTS CORE / DEPUTY CORE ACTIVATE EVENT TEAM ACCOUNT             */}
        {/* Exact Form: Event Team Name, Event Head Name, Phone, Email,               */}
        {/* Select Event Team Account, Head POC, Additional POCs                      */}
        {/* ========================================================================= */}
        <Modal
          isOpen={isActivateModalOpen}
          onClose={() => setIsActivateModalOpen(false)}
          title="Activate Event Team Account"
        >
          <form onSubmit={handleActivateEventTeam} className="space-y-3 text-xs">
            {activateError && (
              <Alert variant="danger" onClose={() => setActivateError(null)}>
                {activateError}
              </Alert>
            )}

            <div className="p-2.5 rounded bg-primary/5 border border-primary/20 text-muted-foreground">
              Sports Core / Deputy Core activation binds{' '}
              <strong className="text-foreground">Event Team → Account → Event Head → POCs</strong> and enables account login.
            </div>

            {/* 1. Event Team Name */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Event Team Name <span className="text-rose-500">*</span>
              </label>
              <Input
                required
                value={activateForm.team_name}
                onChange={(e) => setActivateForm({ ...activateForm, team_name: e.target.value })}
                placeholder="e.g. Phoenix Titans Basketball"
                className="text-xs h-8"
              />
            </div>

            {/* 2. Event Head Name */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Event Head Name <span className="text-rose-500">*</span>
              </label>
              <Input
                required
                value={activateForm.head_name}
                onChange={(e) => setActivateForm({ ...activateForm, head_name: e.target.value })}
                placeholder="Full name of External Lead / Coach"
                className="text-xs h-8"
              />
            </div>

            {/* 3. Event Head Phone Number */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Event Head Phone Number <span className="text-rose-500">*</span>
              </label>
              <Input
                required
                value={activateForm.head_phone}
                onChange={(e) => setActivateForm({ ...activateForm, head_phone: e.target.value })}
                placeholder="+91 98765 43210"
                className="text-xs h-8"
              />
            </div>

            {/* 4. Event Head Email */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Event Head Email <span className="text-rose-500">*</span>
              </label>
              <Input
                required
                type="email"
                value={activateForm.head_email}
                onChange={(e) => setActivateForm({ ...activateForm, head_email: e.target.value })}
                placeholder="head@titansteam.org"
                className="text-xs h-8"
              />
            </div>

            {/* 5. Select Event Team Account (Created by Admin) */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Select Event Team Account <span className="text-rose-500">*</span>
              </label>
              <select
                required
                value={activateForm.user_id}
                onChange={(e) => setActivateForm({ ...activateForm, user_id: e.target.value })}
                className="w-full text-xs rounded-md border border-input bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">-- Choose unactivated credentials account --</option>
                {unactivatedAccounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    @{acc.username} {acc.email ? `(${acc.email})` : ''} - Created {new Date(acc.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
              {unactivatedAccounts.length === 0 && (
                <p className="text-[11px] text-amber-500 mt-1">
                  No unactivated accounts found. An Admin must create credentials first.
                </p>
              )}
            </div>

            {/* Required Assigned Event */}
            <div>
              <label className="block font-semibold text-foreground mb-1">
                Assign Event <span className="text-rose-500">*</span>
              </label>
              <select
                required
                value={activateForm.event_id}
                onChange={(e) => setActivateForm({ ...activateForm, event_id: e.target.value })}
                className="w-full text-xs rounded-md border border-input bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">-- Select Event (Mandatory) --</option>
                {eventsList.map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.name} ({ev.planned_date})
                  </option>
                ))}
              </select>
            </div>

            {/* 6. Head POC (Universal Selector) */}
            <div className="pt-2 border-t border-border">
              <UserSelector
                label="Head POC *"
                description="Select the primary internal Point of Contact (Single)"
                required
                placeholder="Search and select Head POC..."
                value={headPocId}
                onChange={(val) => setHeadPocId(val as string)}
              />
            </div>

            {/* 7. Additional POCs (Universal Selector) */}
            <div>
              <UserSelector
                label="Additional POCs"
                description="Select secondary internal Points of Contact (Multiple)"
                multi
                placeholder="Search and select additional POCs..."
                value={additionalPocIds}
                onChange={(vals) => setAdditionalPocIds(vals as string[])}
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsActivateModalOpen(false)}
                disabled={activateSubmitting}
                className="text-xs h-8"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={activateSubmitting || unactivatedAccounts.length === 0}
                className="text-xs h-8"
              >
                {activateSubmitting ? 'Activating...' : 'Activate Account'}
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </AppShell>
  );
}
