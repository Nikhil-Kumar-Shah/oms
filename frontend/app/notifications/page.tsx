'use client';

/**
 * Notifications Center (/notifications)
 * Real-time operational alerts, priority notifications, and task updates.
 */

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { EmptyState } from '@/components/common/EmptyState';
import { notificationsApi, ApiException } from '@/lib/api';
import { NotificationResponse, NotificationType } from '@/types/communication';
import {
  Bell,
  CheckCheck,
  Check,
  Trash2,
  ExternalLink,
  Clock,
  AlertCircle,
  Megaphone,
  ShieldAlert,
  ListTodo,
  FileText,
  Sparkles,
  Inbox,
  Filter,
} from 'lucide-react';

export default function NotificationsPage() {
  const router = useRouter();
  const { user, roleNames, hasPermission, hasRole } = useAuth();
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);

  const isAdmin = hasRole('ADMIN');


  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'UNREAD' | 'READ'>('ALL');
  const [filterType, setFilterType] = useState<string>('ALL');
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [isMarkingAll, setIsMarkingAll] = useState<boolean>(false);


  const fetchNotifications = useCallback(async () => {
    try {
      const params: { read_status?: string; notification_type?: string; limit: number } = { limit: 100 };
      if (filterStatus === 'UNREAD') params.read_status = 'UNREAD';
      if (filterStatus === 'READ') params.read_status = 'READ';
      if (filterType !== 'ALL') params.notification_type = filterType;

      const res = await notificationsApi.list(params);
      setNotifications(res.items);
      setUnreadCount(res.unread_count);
      setTotalCount(res.total);
      setLoading(false);
    } catch (err: unknown) {
      const msg = err instanceof ApiException ? err.message : 'Failed to load notifications';
      setErrorMsg(msg);
      setLoading(false);
    }
  }, [filterStatus, filterType]);

  useEffect(() => {
    if (!user) {
      setNotifications([]);
      setUnreadCount(0);
      setTotalCount(0);
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchNotifications();
  }, [user?.id, fetchNotifications, refreshTrigger]);


  const handleMarkRead = async (id: string) => {
    // Optimistic UI update
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read_status: 'READ', is_read: true, read_at: new Date().toISOString() } : n))
    );
    setUnreadCount((c) => Math.max(0, c - 1));

    try {
      await notificationsApi.markRead(id);
    } catch {
      // Re-sync on failure
      setRefreshTrigger((prev) => prev + 1);
    }
  };

  const handleDismiss = async (id: string) => {
    // Optimistic UI update
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    try {
      await notificationsApi.dismiss(id);
      setRefreshTrigger((prev) => prev + 1);
    } catch {
      setRefreshTrigger((prev) => prev + 1);
    }
  };

  const handleMarkAllRead = async () => {
    setIsMarkingAll(true);
    // Optimistic UI update
    setNotifications((prev) =>
      prev.map((n) => ({ ...n, read_status: 'READ', is_read: true, read_at: new Date().toISOString() }))
    );
    setUnreadCount(0);

    try {
      await notificationsApi.markAllRead();
      setRefreshTrigger((prev) => prev + 1);
    } catch {
      setRefreshTrigger((prev) => prev + 1);
    } finally {
      setIsMarkingAll(false);
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'TASK':
      case 'TASK_ASSIGNED':
      case 'TASK_STATUS_CHANGED':
      case 'TASK_ESCALATED':
        return <ListTodo className="w-5 h-5 text-indigo-500" />;
      case 'REQUIREMENT':
      case 'REQUIREMENT_ASSIGNED':
        return <Sparkles className="w-5 h-5 text-amber-500" />;
      case 'MEETING':
      case 'MEETING_INVITATION':
        return <Clock className="w-5 h-5 text-purple-500" />;
      case 'ISSUE_CREATED':
      case 'ISSUE_ESCALATED':
      case 'ISSUE_RESOLVED':
        return <AlertCircle className="w-5 h-5 text-rose-500" />;
      case 'DIRECTIVE':
      case 'DIRECTIVE_ISSUED':
        return <ShieldAlert className="w-5 h-5 text-amber-500" />;
      case 'ANNOUNCEMENT':
      case 'ANNOUNCEMENT_PUBLISHED':
        return <Megaphone className="w-5 h-5 text-sky-500" />;
      case 'FORM':
      case 'FORM_ASSIGNED':
      case 'REPORT':
      case 'REPORT_SUBMITTED':
      case 'REPORT_REVIEWED':
        return <FileText className="w-5 h-5 text-emerald-500" />;
      default:
        return <Bell className="w-5 h-5 text-zinc-500" />;
    }
  };

  const canAccessResource = (type?: string | null): boolean => {
    if (!type) return false;
    if (isAdmin) return true;
    const isPureEventTeam = roleNames.includes('EVENT_TEAM') && !roleNames.includes('ADMIN');

    switch (type.toUpperCase()) {
      case 'TASK':
        return !isPureEventTeam && hasPermission('tasks.read');
      case 'REQUIREMENT':
        return !isPureEventTeam && hasPermission('requirements.read');
      case 'MEETING':
        return hasPermission('meetings.read');
      case 'ISSUE':
        return hasPermission('issues.read');
      case 'EVENT':
        return hasPermission('events.read');
      case 'DIRECTIVE':
        return hasPermission('directives.read');
      case 'ANNOUNCEMENT':
        return hasPermission('announcements.read');
      case 'FORM':
      case 'FORM_RESPONSE':
        return !isPureEventTeam && hasPermission('forms.read');
      case 'REPORT':
      case 'DAILY_REPORT':
        return !isPureEventTeam && hasPermission('reports.read');
      case 'COMMUNICATION':
        return roleNames.some((r) => ['ADMIN', 'SPORTS_CORE', 'DEPUTY_CORE'].includes(r));
      default:
        return true;
    }
  };


  const getResourceLink = (type?: string | null, id?: string | null) => {
    if (!type || !canAccessResource(type)) return null;
    switch (type.toUpperCase()) {
      case 'TASK':
        return id ? `/tasks/${id}` : '/tasks';
      case 'REQUIREMENT':
        return '/requirements';
      case 'MEETING':
        return '/meetings';
      case 'ISSUE':
        return id ? `/issues/${id}` : '/issues';
      case 'EVENT':
        return id ? `/events/${id}` : '/events';
      case 'DIRECTIVE':
        return '/directives';
      case 'ANNOUNCEMENT':
        return '/announcements';
      case 'FORM':
      case 'FORM_RESPONSE':
        return '/forms';
      case 'REPORT':
      case 'DAILY_REPORT':
        return '/reports';
      default:
        return null;
    }
  };


  return (
    <AppShell isEventTeamAllowed={true}>
      <div className="space-y-6 max-w-5xl mx-auto pb-12">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-5">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
              <span className="p-2 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl">
                <Bell className="w-5 h-5" />
              </span>
              Notifications Center
              {unreadCount > 0 && (
                <span className="ml-2 px-2.5 py-0.5 text-xs font-bold rounded-full bg-indigo-600 text-white shadow-xs">
                  {unreadCount} unread
                </span>
              )}
            </h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Operational updates, task assignments, escalations, directives, meetings, and system notifications.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleMarkAllRead}
                disabled={isMarkingAll}
                className="text-xs"
              >
                <CheckCheck className="w-4 h-4 mr-1.5" />
                Mark All as Read
              </Button>
            )}
          </div>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="Notification Error" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        {/* Tab & Type Filters */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-200 dark:border-zinc-800 pb-3">
          {/* Status Tabs */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setFilterStatus('ALL')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                filterStatus === 'ALL'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-xs'
                  : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
              }`}
            >
              All ({totalCount})
            </button>
            <button
              onClick={() => setFilterStatus('UNREAD')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                filterStatus === 'UNREAD'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-xs'
                  : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
              }`}
            >
              Unread ({unreadCount})
            </button>
            <button
              onClick={() => setFilterStatus('READ')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                filterStatus === 'READ'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-xs'
                  : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
              }`}
            >
              Read
            </button>
          </div>

          {/* Type Filter Dropdown */}
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-zinc-400" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="text-xs p-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="ALL">All Categories</option>
              <option value="TASK">Tasks</option>
              <option value="REQUIREMENT">Requirements</option>
              <option value="MEETING">Meetings</option>
              <option value="DIRECTIVE">Directives</option>
              <option value="ANNOUNCEMENT">Announcements</option>
              <option value="FORM">Forms</option>
              <option value="SYSTEM">System Alerts</option>
            </select>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="p-16 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : notifications.length === 0 ? (
          <EmptyState
            icon={<Inbox className="w-8 h-8 text-zinc-400" />}
            title={
              filterStatus === 'UNREAD'
                ? 'No unread notifications'
                : filterStatus === 'READ'
                ? 'No read notifications'
                : 'No notifications'
            }
            description={
              filterStatus === 'UNREAD'
                ? "You have caught up with all unread operational notifications."
                : 'No notifications have been dispatched to your account.'
            }
          />
        ) : (
          <div className="space-y-3">
            {notifications.map((item) => {
              const isUnread = item.read_status === 'UNREAD';
              const resourceLink = getResourceLink(item.related_resource_type, item.related_resource_id);

              return (
                <div
                  key={item.id}
                  className={`p-4 rounded-2xl border transition-all duration-200 flex items-start gap-4 ${
                    isUnread
                      ? 'bg-white dark:bg-zinc-900 border-indigo-200 dark:border-indigo-900/60 shadow-sm ring-1 ring-indigo-500/20'
                      : 'bg-zinc-50/70 dark:bg-zinc-900/40 border-zinc-200 dark:border-zinc-800/80 opacity-85'
                  }`}
                >
                  <div className="p-2.5 rounded-xl bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 shadow-2xs shrink-0 mt-0.5">
                    {getNotificationIcon(item.notification_type)}
                  </div>

                  <div className="flex-1 space-y-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 truncate">
                        <h4
                          className={`text-sm truncate ${
                            isUnread
                              ? 'font-bold text-zinc-900 dark:text-zinc-100'
                              : 'font-semibold text-zinc-700 dark:text-zinc-300'
                          }`}
                        >
                          {item.title}
                        </h4>
                        {isUnread && (
                          <span className="w-2 h-2 rounded-full bg-indigo-600 shrink-0" />
                        )}
                      </div>
                      <span className="text-[11px] text-zinc-400 shrink-0 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(item.created_at).toLocaleDateString()}{' '}
                        {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>

                    <p className="text-xs text-zinc-600 dark:text-zinc-400 whitespace-pre-wrap leading-relaxed">
                      {item.message}
                    </p>

                    <div className="flex items-center gap-3 pt-2">
                      {resourceLink && (
                        <button
                          type="button"
                          onClick={() => {
                            if (isUnread) handleMarkRead(item.id);
                            router.push(resourceLink);
                          }}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
                        >
                          View Resource <ExternalLink className="w-3 h-3" />
                        </button>
                      )}

                      {isUnread && (
                        <button
                          type="button"
                          onClick={() => handleMarkRead(item.id)}
                          className="inline-flex items-center gap-1 text-xs font-medium text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                        >
                          <Check className="w-3 h-3" /> Mark Read
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() => handleDismiss(item.id)}
                        className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-rose-600 dark:hover:text-rose-400 ml-auto"
                      >
                        <Trash2 className="w-3 h-3" /> Dismiss
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
