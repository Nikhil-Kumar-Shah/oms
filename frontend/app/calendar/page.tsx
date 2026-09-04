'use client';

/**
 * Connected Operational Calendar (/calendar)
 * Paradox Sports OMS - Phase 10G Architecture
 * Features:
 * - Master Calendar vs Personal Calendar separation
 * - Real-time synchronization of Tasks, Meetings, Events, and Activities
 * - Reusable Universal Audience Selector for organizational activities
 * - Zero-duplicate backend projection
 */

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { StatusBadge } from '@/components/common/StatusBadge';
import { PriorityBadge } from '@/components/common/PriorityBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { UniversalAudienceSelector, AudienceItem } from '@/components/ui/UniversalAudienceSelector';
import { UniversalAudienceSelection } from '@/types/organization';
import { useAuth } from '@/hooks/useAuth';
import { calendarApi, ApiException } from '@/lib/api';
import {
  CalendarResponse,
  CalendarCreate,
  ActivityCategory,
  CalendarPriority,
  DeadlineType,
} from '@/types/calendar';
import {
  Calendar as CalendarIcon,
  Plus,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  X,
  List,
  Grid,
  Users as UsersIcon,
  User as UserIcon,
  CheckCircle2,
  Trash2,
  Lock,
  Globe,
  Tag,
} from 'lucide-react';

function CalendarContent() {
  const { user, hasRole, hasPermission } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Master calendar permission evaluation
  const canAccessMaster =
    hasPermission('calendar.read_master') ||
    hasRole('ADMIN') ||
    hasRole('SPORTS_CORE') ||
    hasRole('DEPUTY_CORE');

  const canCreateOrganizational =
    hasPermission('calendar.create') ||
    hasRole('ADMIN') ||
    hasRole('SPORTS_CORE') ||
    hasRole('DEPUTY_CORE');

  // Derive active view scope (personal or master)
  const viewParam = searchParams.get('view');
  const activeScope: 'personal' | 'master' =
    canAccessMaster && viewParam === 'master' ? 'master' : 'personal';

  const [items, setItems] = useState<CalendarResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // View mode & Date
  const [viewMode, setViewMode] = useState<'month' | 'list'>('month');
  const [currentDate, setCurrentDate] = useState<Date>(new Date());

  // Category filter
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  // Detail Modal & Actions
  const [selectedItem, setSelectedItem] = useState<CalendarResponse | null>(null);
  const [deleteLoading, setDeleteLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Reschedule inline state
  const [isRescheduleOpen, setIsRescheduleOpen] = useState<boolean>(false);
  const [rescheduleForm, setRescheduleForm] = useState<{
    new_date: string;
    new_start_time: string;
    new_end_time: string;
    reason: string;
  }>({
    new_date: '',
    new_start_time: '09:00',
    new_end_time: '10:00',
    reason: '',
  });

  const openItemDetail = (item: CalendarResponse) => {
    setSelectedItem(item);
    setActionError(null);
    setIsRescheduleOpen(false);
    setRescheduleForm({
      new_date: item.activity_date,
      new_start_time: item.start_time ? item.start_time.slice(0, 5) : '09:00',
      new_end_time: item.end_time ? item.end_time.slice(0, 5) : '10:00',
      reason: '',
    });
  };

  const handleExecuteAction = async (action: 'mark_completed_for_me' | 'complete' | 'in_progress' | 'cancel', remarks?: string) => {
    if (!selectedItem) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await calendarApi.executeAction(selectedItem.id, { action, remarks });
      setSelectedItem(updated);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to update calendar activity');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRescheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItem) return;
    if (!rescheduleForm.new_date) {
      setActionError('New date is required for rescheduling.');
      return;
    }
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await calendarApi.reschedule(selectedItem.id, {
        new_date: rescheduleForm.new_date,
        new_start_time: rescheduleForm.new_start_time ? `${rescheduleForm.new_start_time}:00` : undefined,
        new_end_time: rescheduleForm.new_end_time ? `${rescheduleForm.new_end_time}:00` : undefined,
        reason: rescheduleForm.reason.trim() || undefined,
      });
      setSelectedItem(updated);
      setIsRescheduleOpen(false);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to reschedule calendar activity');
    } finally {
      setActionLoading(false);
    }
  };

  // Group items chronologically for List View: Active -> Today -> Upcoming -> Recent History
  const groupedListItems = React.useMemo(() => {
    const todayStr = new Date().toISOString().split('T')[0];

    const activeList: CalendarResponse[] = [];
    const todayList: CalendarResponse[] = [];
    const upcomingList: CalendarResponse[] = [];
    const historyList: CalendarResponse[] = [];

    items.forEach((item) => {
      if (item.status === 'IN_PROGRESS') {
        activeList.push(item);
      } else if (item.activity_date === todayStr) {
        todayList.push(item);
      } else if (item.activity_date > todayStr) {
        upcomingList.push(item);
      } else {
        historyList.push(item);
      }
    });

    const sortByDateAsc = (a: CalendarResponse, b: CalendarResponse) => {
      const d = a.activity_date.localeCompare(b.activity_date);
      if (d !== 0) return d;
      return (a.start_time || '').localeCompare(b.start_time || '');
    };

    const sortByDateDesc = (a: CalendarResponse, b: CalendarResponse) => {
      const d = b.activity_date.localeCompare(a.activity_date);
      if (d !== 0) return d;
      return (b.start_time || '').localeCompare(a.start_time || '');
    };

    activeList.sort(sortByDateAsc);
    todayList.sort(sortByDateAsc);
    upcomingList.sort(sortByDateAsc);
    historyList.sort(sortByDateDesc);

    return [
      {
        key: 'active',
        title: 'Currently Active',
        items: activeList,
        badge: 'IN PROGRESS',
        badgeColor: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
      },
      {
        key: 'today',
        title: 'Today',
        items: todayList,
        badge: 'TODAY',
        badgeColor: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300',
      },
      {
        key: 'upcoming',
        title: 'Upcoming',
        items: upcomingList,
        badge: 'UPCOMING',
        badgeColor: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
      },
      {
        key: 'history',
        title: 'Recent History',
        items: historyList,
        badge: 'PAST',
        badgeColor: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
      },
    ];
  }, [items]);

  // Create Activity Modal
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [createScopeType, setCreateScopeType] = useState<'personal' | 'organizational'>(
    canCreateOrganizational && activeScope === 'master' ? 'organizational' : 'personal'
  );
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Universal Audience Selection state
  const [audienceItems, setAudienceItems] = useState<AudienceItem[]>([]);
  const [audienceSelection, setAudienceSelection] = useState<UniversalAudienceSelection>({});

  const [createForm, setCreateForm] = useState<{
    title: string;
    description: string;
    activity_date: string;
    start_time: string;
    end_time: string;
    category: ActivityCategory;
    priority: CalendarPriority;
    deadline_type: DeadlineType;
    remarks: string;
    resource_link: string;
  }>({
    title: '',
    description: '',
    activity_date: new Date().toISOString().split('T')[0],
    start_time: '09:00',
    end_time: '10:00',
    category: 'ACTIVITY',
    priority: 'MEDIUM',
    deadline_type: 'INFORMATIONAL',
    remarks: '',
    resource_link: '',
  });

  // Switch view scope
  const handleScopeChange = (newScope: 'personal' | 'master') => {
    if (newScope === 'master' && !canAccessMaster) return;
    const params = new URLSearchParams(searchParams.toString());
    if (newScope === 'master') {
      params.set('view', 'master');
    } else {
      params.delete('view');
    }
    router.push(`/calendar?${params.toString()}`);
  };

  // Fetch calendar items based on active view scope
  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMsg(null);

    calendarApi
      .list({
        view: activeScope,
        category: (categoryFilter as ActivityCategory) || undefined,
        limit: 500,
      })
      .then((data) => {
        if (active) {
          setItems(data.items);
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

    return () => {
      active = false;
    };
  }, [activeScope, categoryFilter, refreshTrigger]);

  // Handle activity creation
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.title.trim()) {
      setCreateError('Activity title is required.');
      return;
    }
    if (!createForm.activity_date) {
      setCreateError('Activity date is required.');
      return;
    }

    const isPersonal = createScopeType === 'personal';

    if (!isPersonal) {
      const hasAudience =
        audienceSelection.include_all ||
        (audienceSelection.vertical_ids && audienceSelection.vertical_ids.length > 0) ||
        (audienceSelection.role_ids && audienceSelection.role_ids.length > 0) ||
        (audienceSelection.user_ids && audienceSelection.user_ids.length > 0);

      if (!hasAudience) {
        setCreateError('Please select at least one target audience (all users, vertical, role, or user).');
        return;
      }
    }

    setCreateLoading(true);
    setCreateError(null);

    const payload: CalendarCreate = {
      title: createForm.title.trim(),
      description: createForm.description.trim() || undefined,
      activity_date: createForm.activity_date,
      start_time: createForm.start_time ? `${createForm.start_time}:00` : undefined,
      end_time: createForm.end_time ? `${createForm.end_time}:00` : undefined,
      category: createForm.category,
      priority: createForm.priority,
      deadline_type: createForm.deadline_type,
      is_personal: isPersonal,
      resource_link: createForm.resource_link.trim() || undefined,
      remarks: createForm.remarks.trim() || undefined,
      all_users: !isPersonal ? audienceSelection.include_all : undefined,
      vertical_ids: !isPersonal && audienceSelection.vertical_ids?.length ? audienceSelection.vertical_ids : undefined,
      role_ids: !isPersonal && audienceSelection.role_ids?.length ? audienceSelection.role_ids : undefined,
      user_ids: !isPersonal && audienceSelection.user_ids?.length ? audienceSelection.user_ids : undefined,
    };

    try {
      await calendarApi.create(payload);
      setIsCreateOpen(false);
      setAudienceItems([]);
      setAudienceSelection({});
      setCreateForm({
        title: '',
        description: '',
        activity_date: new Date().toISOString().split('T')[0],
        start_time: '09:00',
        end_time: '10:00',
        category: 'ACTIVITY',
        priority: 'MEDIUM',
        deadline_type: 'INFORMATIONAL',
        remarks: '',
        resource_link: '',
      });
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setCreateError(err.message);
      else if (err instanceof Error) setCreateError(err.message);
    } finally {
      setCreateLoading(false);
    }
  };

  // Handle entry deletion
  const handleDeleteEntry = async (entryId: string) => {
    if (!confirm('Are you sure you want to delete this calendar activity?')) return;
    setDeleteLoading(true);
    try {
      await calendarApi.delete(entryId);
      setSelectedItem(null);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) alert(err.message);
      else alert('Failed to delete calendar activity');
    } finally {
      setDeleteLoading(false);
    }
  };

  // Month navigation
  const prevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };
  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };

  const monthYearStr = currentDate.toLocaleString('default', { month: 'long', year: 'numeric' });
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Entity badge rendering helper
  const renderEntityBadge = (entityType?: string) => {
    switch (entityType) {
      case 'TASK':
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300">
            Task
          </span>
        );
      case 'MEETING':
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300">
            Meeting
          </span>
        );
      case 'EVENT':
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            Event
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
            Activity
          </span>
        );
    }
  };

  return (
    <AppShell requiredPermission="calendar.read" isEventTeamAllowed={true}>
      <div className="space-y-6">
        {/* Header & Connected Calendar View Switcher */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
              <CalendarIcon className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              {activeScope === 'master' ? 'Master Calendar' : 'My Calendar'}
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {activeScope === 'master'
                ? 'Department-wide operational schedule, tournament milestones, deadlines, and meetings.'
                : 'Your personal activities, assigned tasks, scheduled meetings, and upcoming deadlines.'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* View Mode Toggle: Month vs List */}
            <div className="flex items-center bg-zinc-100 dark:bg-zinc-800 p-1 rounded-xl">
              <button
                onClick={() => setViewMode('month')}
                className={`p-1.5 rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors ${
                  viewMode === 'month'
                    ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                    : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                }`}
              >
                <Grid className="w-4 h-4" />
                <span className="hidden sm:inline">Month</span>
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors ${
                  viewMode === 'list'
                    ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                    : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                }`}
              >
                <List className="w-4 h-4" />
                <span className="hidden sm:inline">List</span>
              </button>
            </div>

            {/* Create Activity Button (Available to all users for personal activity, or org activities for managers) */}
            <Button
              variant="primary"
              onClick={() => {
                setCreateError(null);
                setCreateScopeType(canCreateOrganizational && activeScope === 'master' ? 'organizational' : 'personal');
                setIsCreateOpen(true);
              }}
              leftIcon={<Plus className="w-4 h-4" />}
            >
              Add Activity
            </Button>
          </div>
        </div>

        {/* Connected Calendar Navigation Tabs: My Calendar vs Master Calendar */}
        <div className="flex items-center gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-2">
          <button
            onClick={() => handleScopeChange('personal')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              activeScope === 'personal'
                ? 'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800'
                : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
            }`}
          >
            <UserIcon className="w-4 h-4" />
            My Calendar
          </button>

          {canAccessMaster && (
            <button
              onClick={() => handleScopeChange('master')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                activeScope === 'master'
                  ? 'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800'
                  : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
              }`}
            >
              <Globe className="w-4 h-4" />
              Master Calendar
              <span className="px-1.5 py-0.2 text-[10px] font-bold rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300">
                Core
              </span>
            </button>
          )}
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Calendar Notice">
            {errorMsg}
          </Alert>
        )}

        {/* Toolbar & Filters */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={prevMonth}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-base font-bold text-zinc-900 dark:text-zinc-100 min-w-[160px] text-center">
              {monthYearStr}
            </span>
            <Button variant="outline" size="sm" onClick={nextMonth}>
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="h-9 px-3 text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Categories</option>
              <option value="ACTIVITY">Activity</option>
              <option value="REPORT_DEADLINE">Task Deadline</option>
              <option value="MEETING">Meeting</option>
              <option value="EVENT">Event</option>
              <option value="REVIEW_MEETING">Review Meeting</option>
              <option value="MILESTONE">Milestone</option>
              <option value="ORIENTATION">Orientation</option>
            </select>
          </div>
        </div>

        {/* Calendar View Body */}
        {loading ? (
          <div className="p-16 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : viewMode === 'month' ? (
          /* Month Grid View */
          <Card>
            <CardContent className="p-0 overflow-hidden">
              <div className="grid grid-cols-7 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 text-center py-2 text-xs font-semibold text-zinc-500">
                <span>Sun</span>
                <span>Mon</span>
                <span>Tue</span>
                <span>Wed</span>
                <span>Thu</span>
                <span>Fri</span>
                <span>Sat</span>
              </div>
              <div className="grid grid-cols-7 auto-rows-fr divide-x divide-y divide-zinc-200 dark:divide-zinc-800 text-xs">
                {/* Empty leading cells */}
                {Array.from({ length: firstDay }).map((_, i) => (
                  <div key={`empty-${i}`} className="min-h-[100px] p-2 bg-zinc-50/40 dark:bg-zinc-950/20" />
                ))}

                {/* Day cells */}
                {Array.from({ length: daysInMonth }).map((_, i) => {
                  const dayNum = i + 1;
                  const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
                  const dayItems = items.filter((item) => item.activity_date === dateStr);

                  return (
                    <div
                      key={`day-${dayNum}`}
                      className="min-h-[100px] p-2 hover:bg-zinc-50 dark:hover:bg-zinc-900/30 transition-colors flex flex-col justify-between"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-zinc-700 dark:text-zinc-300">{dayNum}</span>
                        {dayItems.length > 0 && (
                          <span className="w-1.5 h-1.5 rounded-full bg-indigo-600" />
                        )}
                      </div>

                      <div className="space-y-1 overflow-y-auto max-h-24">
                        {dayItems.map((item) => (
                          <button
                            key={`${item.entity_type}-${item.id}`}
                            onClick={() => openItemDetail(item)}
                            className={`w-full text-left p-1 rounded-md text-[11px] font-medium truncate block border transition-all ${
                              item.status === 'IN_PROGRESS'
                                ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
                                : item.status === 'CANCELLED'
                                ? 'line-through opacity-50 bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900/40'
                                : item.status === 'COMPLETED' || item.is_user_completed
                                ? 'opacity-60 bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700'
                                : 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-100 dark:border-indigo-900/40 hover:opacity-80'
                            }`}
                          >
                            <span className="mr-1">{renderEntityBadge(item.entity_type)}</span>
                            {item.start_time ? `${item.start_time.slice(0, 5)} ` : ''}
                            {item.title}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        ) : (
          /* Chronological List View grouped by Active, Today, Upcoming, and Recent History */
          <div className="space-y-6">
            {items.length === 0 ? (
              <Card>
                <CardContent className="p-8">
                  <EmptyState
                    icon={CalendarIcon}
                    title="No Scheduled Items"
                    description={`There are no activities or deadlines matching this view (${activeScope === 'master' ? 'Master' : 'Personal'}).`}
                  />
                </CardContent>
              </Card>
            ) : (
              groupedListItems.map((group) => {
                if (group.items.length === 0) return null;
                const isHistoryGroup = group.key === 'history';

                return (
                  <div key={group.key} className="space-y-2.5">
                    <div className="flex items-center gap-2">
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider ${group.badgeColor}`}>
                        {group.badge}
                      </span>
                      <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                        {group.title}
                      </h3>
                      <span className="text-xs text-zinc-400">({group.items.length})</span>
                    </div>

                    <Card>
                      <CardContent className="p-0">
                        <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
                          {group.items.map((item) => {
                            const isCompleted = item.status === 'COMPLETED' || item.is_user_completed;
                            const isCancelled = item.status === 'CANCELLED';
                            const isInProgress = item.status === 'IN_PROGRESS';
                            const isRescheduled = item.status === 'RESCHEDULED';

                            return (
                              <div
                                key={`${item.entity_type}-${item.id}`}
                                onClick={() => openItemDetail(item)}
                                className={`p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 cursor-pointer transition-all ${
                                  isInProgress
                                    ? 'border-l-4 border-l-emerald-500 bg-emerald-50/20 dark:bg-emerald-950/10 hover:bg-emerald-50/40'
                                    : isCancelled
                                    ? 'opacity-65 hover:opacity-100 bg-rose-50/10 dark:bg-rose-950/10'
                                    : isCompleted || isHistoryGroup
                                    ? 'opacity-60 hover:opacity-100 bg-zinc-50/40 dark:bg-zinc-900/30'
                                    : 'hover:bg-zinc-50/70 dark:hover:bg-zinc-900/40'
                                }`}
                              >
                                <div className="space-y-1 max-w-xl">
                                  <div className="flex flex-wrap items-center gap-2">
                                    {renderEntityBadge(item.entity_type)}
                                    <h4
                                      className={`font-semibold text-zinc-900 dark:text-zinc-100 ${
                                        isCancelled ? 'line-through text-zinc-400 dark:text-zinc-500' : ''
                                      }`}
                                    >
                                      {item.title}
                                    </h4>
                                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700">
                                      {item.category}
                                    </span>
                                    <PriorityBadge priority={item.priority} size="sm" />
                                    <StatusBadge status={item.status} size="sm" />
                                    {item.is_user_completed && (
                                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300 flex items-center gap-1">
                                        <CheckCircle2 className="w-3 h-3" />
                                        Completed by you
                                      </span>
                                    )}
                                    {isRescheduled && item.original_date && (
                                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/60 dark:text-amber-300">
                                        Moved from {item.original_date}
                                      </span>
                                    )}
                                  </div>
                                  {item.description && (
                                    <p className="text-xs text-zinc-500 dark:text-zinc-400 line-clamp-1">{item.description}</p>
                                  )}
                                  <div className="flex items-center gap-2 text-xs text-zinc-400">
                                    <span>{item.vertical_name || (item.is_personal ? 'Personal Activity' : 'Organization Wide')}</span>
                                    <span>•</span>
                                    <span>{item.is_personal ? 'Private' : `Audience: ${item.audience}`}</span>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2 text-xs text-zinc-500 whitespace-nowrap self-end sm:self-center">
                                  <CalendarIcon className="w-3.5 h-3.5" />
                                  <span className="font-medium text-zinc-800 dark:text-zinc-200">{item.activity_date}</span>
                                  {item.start_time && (
                                    <span className="text-zinc-400 font-mono">
                                      {item.start_time.slice(0, 5)} {item.end_time ? `- ${item.end_time.slice(0, 5)}` : ''}
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Item Detail & Actions Modal */}
        {selectedItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="relative w-[95vw] sm:w-[88vw] md:w-[75vw] lg:w-[62vw] max-w-2xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden">
              <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between bg-white dark:bg-zinc-900">
                <div className="flex items-center gap-2">
                  {renderEntityBadge(selectedItem.entity_type)}
                  <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
                    {selectedItem.category}
                  </span>
                  <StatusBadge status={selectedItem.status} size="sm" />
                </div>
                <button
                  onClick={() => setSelectedItem(null)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4">

              {actionError && <Alert variant="danger">{actionError}</Alert>}

              <div className="space-y-2">
                <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">{selectedItem.title}</h3>
                {selectedItem.description && (
                  <p className="text-sm text-zinc-600 dark:text-zinc-300 whitespace-pre-line">{selectedItem.description}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs p-3 rounded-xl bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-100 dark:border-zinc-800">
                <div>
                  <span className="text-zinc-400">Date</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100">{selectedItem.activity_date}</p>
                  {selectedItem.original_date && (
                    <span className="text-[10px] text-amber-600 dark:text-amber-400">
                      Originally: {selectedItem.original_date}
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-zinc-400">Time</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100">
                    {selectedItem.start_time ? selectedItem.start_time.slice(0, 5) : 'All Day'}
                    {selectedItem.end_time ? ` - ${selectedItem.end_time.slice(0, 5)}` : ''}
                  </p>
                </div>
                <div>
                  <span className="text-zinc-400">Vertical Scope</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100">
                    {selectedItem.vertical_name || (selectedItem.is_personal ? 'None (Personal)' : 'Organization Wide')}
                  </p>
                </div>
                <div>
                  <span className="text-zinc-400">Audience</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100">
                    {selectedItem.is_personal ? 'Private to You' : selectedItem.audience}
                  </p>
                </div>
                {selectedItem.is_user_completed && (
                  <div className="col-span-2 p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5 font-medium">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Participation: Marked completed by you</span>
                  </div>
                )}
              </div>

              {/* Linked Entity Actions: Task, Meeting, Event */}
              {selectedItem.entity_type === 'TASK' && selectedItem.entity_id && (
                <div className="p-3 rounded-xl bg-blue-50/60 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 flex items-center justify-between text-xs">
                  <span className="text-blue-800 dark:text-blue-300 font-medium">Underlying Task Item</span>
                  <Link href={`/tasks/${selectedItem.entity_id}?from=calendar`}>
                    <Button size="sm" variant="primary" rightIcon={<ExternalLink className="w-3.5 h-3.5" />}>
                      View Task
                    </Button>
                  </Link>
                </div>
              )}

              {selectedItem.entity_type === 'MEETING' && selectedItem.entity_id && (
                <div className="p-3 rounded-xl bg-purple-50/60 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 flex items-center justify-between text-xs">
                  <span className="text-purple-800 dark:text-purple-300 font-medium">Operational Meeting</span>
                  <Link href="/meetings">
                    <Button size="sm" variant="primary" rightIcon={<ExternalLink className="w-3.5 h-3.5" />}>
                      View Meetings
                    </Button>
                  </Link>
                </div>
              )}

              {selectedItem.entity_type === 'EVENT' && selectedItem.entity_id && (
                <div className="p-3 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 flex items-center justify-between text-xs">
                  <span className="text-emerald-800 dark:text-emerald-300 font-medium">Scheduled Event</span>
                  <Link href={`/events/${selectedItem.entity_id}`}>
                    <Button size="sm" variant="primary" rightIcon={<ExternalLink className="w-3.5 h-3.5" />}>
                      View Event
                    </Button>
                  </Link>
                </div>
              )}

              {/* Inline Reschedule Form */}
              {isRescheduleOpen ? (
                <form onSubmit={handleRescheduleSubmit} className="p-4 rounded-xl bg-amber-50/50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 space-y-3">
                  <h4 className="text-xs font-bold text-amber-900 dark:text-amber-300 uppercase tracking-wide">
                    Reschedule Activity
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-zinc-700 dark:text-zinc-300">New Date *</label>
                      <Input
                        type="date"
                        required
                        value={rescheduleForm.new_date}
                        onChange={(e) => setRescheduleForm({ ...rescheduleForm, new_date: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-zinc-700 dark:text-zinc-300">Start Time</label>
                      <Input
                        type="time"
                        value={rescheduleForm.new_start_time}
                        onChange={(e) => setRescheduleForm({ ...rescheduleForm, new_start_time: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-zinc-700 dark:text-zinc-300">End Time</label>
                      <Input
                        type="time"
                        value={rescheduleForm.new_end_time}
                        onChange={(e) => setRescheduleForm({ ...rescheduleForm, new_end_time: e.target.value })}
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-zinc-700 dark:text-zinc-300">Reason (Optional)</label>
                    <Input
                      placeholder="e.g. Ground maintenance delayed"
                      value={rescheduleForm.reason}
                      onChange={(e) => setRescheduleForm({ ...rescheduleForm, reason: e.target.value })}
                    />
                  </div>
                  <div className="flex items-center justify-end gap-2 pt-1">
                    <Button
                      size="sm"
                      variant="outline"
                      type="button"
                      onClick={() => setIsRescheduleOpen(false)}
                      disabled={actionLoading}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      type="submit"
                      isLoading={actionLoading}
                    >
                      Confirm Reschedule
                    </Button>
                  </div>
                </form>
              ) : null}

              {/* Action Controls & Close */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-zinc-100 dark:border-zinc-800">
                {selectedItem.entity_type === 'CALENDAR_ENTRY' && (
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Creator / Authorized Owner Controls */}
                    {selectedItem.created_by_id === user?.id || canAccessMaster || hasPermission('calendar.update') ? (
                      <>
                        {selectedItem.status !== 'COMPLETED' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleExecuteAction('complete')}
                            isLoading={actionLoading}
                            leftIcon={<CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                          >
                            Complete
                          </Button>
                        )}
                        {selectedItem.status !== 'IN_PROGRESS' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleExecuteAction('in_progress')}
                            isLoading={actionLoading}
                          >
                            In Progress
                          </Button>
                        )}
                        {selectedItem.status !== 'CANCELLED' && !isRescheduleOpen && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setIsRescheduleOpen(true)}
                            disabled={actionLoading}
                          >
                            Reschedule
                          </Button>
                        )}
                        {selectedItem.status !== 'CANCELLED' && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                            onClick={() => handleExecuteAction('cancel')}
                            isLoading={actionLoading}
                          >
                            Cancel
                          </Button>
                        )}
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleDeleteEntry(selectedItem.id)}
                          isLoading={deleteLoading}
                          leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                        >
                          Delete
                        </Button>
                      </>
                    ) : (
                      /* Non-Creator Attendee Participation Control */
                      !selectedItem.is_user_completed && (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => handleExecuteAction('mark_completed_for_me')}
                          isLoading={actionLoading}
                          leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                        >
                          Mark Completed (For Me)
                        </Button>
                      )
                    )}
                  </div>
                )}
              </div>
              </div>

              <div className="shrink-0 flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                <Button variant="outline" size="sm" onClick={() => setSelectedItem(null)}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Create Calendar Item Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="relative w-[95vw] sm:w-[92vw] md:w-[82vw] lg:w-[72vw] xl:w-[68vw] max-w-5xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden">
              <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between bg-white dark:bg-zinc-900">
                <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <CalendarIcon className="w-5 h-5 text-indigo-600" />
                  Schedule Calendar Activity
                </h3>
                <button
                  onClick={() => setIsCreateOpen(false)}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreate} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4">
                  {createError && <Alert variant="danger">{createError}</Alert>}

                  {/* Personal vs Organizational Scope Switcher */}
                  {canCreateOrganizational && (
                    <div className="flex p-1 bg-zinc-100 dark:bg-zinc-800 rounded-xl">
                      <button
                        type="button"
                        onClick={() => setCreateScopeType('personal')}
                        className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                          createScopeType === 'personal'
                            ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                            : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                        }`}
                      >
                        Personal Activity
                      </button>
                      <button
                        type="button"
                        onClick={() => setCreateScopeType('organizational')}
                        className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                          createScopeType === 'organizational'
                            ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                            : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                        }`}
                      >
                        Organizational Activity
                      </button>
                    </div>
                  )}

                  {createScopeType === 'organizational' && (
                    /* Universal Audience Selector for Organizational Activities */
                    <div className="space-y-2">
                      <UniversalAudienceSelector
                        label="Audience / Assignment *"
                        description="Select target verticals, roles, specific users, or entire organization"
                        required
                        allowAllUsers={true}
                        allowVerticals={true}
                        allowRoles={true}
                        allowIndividualUsers={true}
                        value={audienceItems}
                        onChange={(items, structuredVal) => {
                          setAudienceItems(items);
                          setAudienceSelection(structuredVal);
                        }}
                      />
                    </div>
                  )}

                  <Input
                    label="Activity Title *"
                    required
                    placeholder="e.g., Weekly Sprint Review"
                    value={createForm.title}
                    onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                  />

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Category</label>
                      <select
                        value={createForm.category}
                        onChange={(e) => setCreateForm({ ...createForm, category: e.target.value as ActivityCategory })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="ACTIVITY">Activity</option>
                        <option value="EVENT">Event</option>
                        <option value="MEETING">Meeting</option>
                        <option value="REPORT_DEADLINE">Report Deadline</option>
                        <option value="REVIEW_MEETING">Review Meeting</option>
                        <option value="MILESTONE">Milestone</option>
                        <option value="ORIENTATION">Orientation</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Priority</label>
                      <select
                        value={createForm.priority}
                        onChange={(e) => setCreateForm({ ...createForm, priority: e.target.value as CalendarPriority })}
                        className="w-full h-10 px-3 py-2 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="LOW">Low</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="HIGH">High</option>
                        <option value="CRITICAL">Critical</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <Input
                      label="Date *"
                      type="date"
                      required
                      value={createForm.activity_date}
                      onChange={(e) => setCreateForm({ ...createForm, activity_date: e.target.value })}
                    />
                    <Input
                      label="Start Time"
                      type="time"
                      value={createForm.start_time}
                      onChange={(e) => setCreateForm({ ...createForm, start_time: e.target.value })}
                    />
                    <Input
                      label="End Time"
                      type="time"
                      value={createForm.end_time}
                      onChange={(e) => setCreateForm({ ...createForm, end_time: e.target.value })}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Description</label>
                    <textarea
                      rows={3}
                      placeholder="Activity objectives, agenda, or location details..."
                      value={createForm.description}
                      onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                      className="w-full p-3 text-sm bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                {/* Fixed Footer Action Buttons */}
                <div className="shrink-0 flex justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                  <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" isLoading={createLoading}>
                    Schedule Activity
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

export default function CalendarPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center">
          <Spinner size="lg" />
        </div>
      }
    >
      <CalendarContent />
    </Suspense>
  );
}
