'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Badge } from '@/components/ui/Badge';
import { notificationsApi } from '@/lib/api';
import { NotificationResponse } from '@/types/communication';
import {
  LogOut,
  ChevronDown,
  Menu,
  Layers,
  User,
  Lock,
  Bell,
  CheckCheck,
  ExternalLink,
  ListTodo,
  AlertCircle,
  ShieldAlert,
  Megaphone,
  FileText,
  Clock,
  Sparkles,
  GitPullRequest,
  Users,
} from 'lucide-react';

interface HeaderProps {
  onToggleSidebar?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout, primaryVertical, roleNames, hasPermission, hasRole } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [recentNotifs, setRecentNotifs] = useState<NotificationResponse[]>([]);
  const [isNotifLoading, setIsNotifLoading] = useState<boolean>(false);
  const notifRef = useRef<HTMLDivElement>(null);

  const isAdmin = hasRole('ADMIN');
  const primaryRole = roleNames[0] || 'VOLUNTEER';
  const hasNotificationAccess = Boolean(user && (isAdmin || hasPermission('notifications.read')));
  const isAdminDashboard = Boolean((pathname === '/' && isAdmin) || pathname?.startsWith('/admin'));

  // Fetch unread count
  const fetchUnreadCount = useCallback(async () => {
    if (!user || !hasNotificationAccess) return;
    try {
      const res = await notificationsApi.getUnreadCount();
      setUnreadCount(res.unread_count);
    } catch {
      // Background silent fallback
    }
  }, [user, hasNotificationAccess]);

  // Fetch recent notifications when popup opens
  const fetchRecentNotifications = async () => {
    if (!hasNotificationAccess) return;
    setIsNotifLoading(true);
    try {
      const res = await notificationsApi.list({ limit: 5 });
      setRecentNotifs(res.items);
      setUnreadCount(res.unread_count);
    } catch {
      // Ignored
    } finally {
      setIsNotifLoading(false);
    }
  };

  // Reset state when user logs out or switches accounts, and start polling for active user
  useEffect(() => {
    if (!user || !hasNotificationAccess) {
      setUnreadCount(0);
      setRecentNotifs([]);
      setNotifOpen(false);
      return;
    }

    setUnreadCount(0);
    setRecentNotifs([]);
    setNotifOpen(false);
    fetchUnreadCount();

    // 20-second polling fallback strictly for active authenticated session
    const interval = setInterval(fetchUnreadCount, 20000);
    return () => clearInterval(interval);
  }, [user?.id, hasNotificationAccess, fetchUnreadCount]);


  const handleToggleNotif = () => {
    if (!notifOpen) {
      fetchRecentNotifications();
    }
    setNotifOpen(!notifOpen);
    setDropdownOpen(false);
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setUnreadCount(0);
      setRecentNotifs((prev) =>
        prev.map((n) => ({ ...n, read_status: 'READ', is_read: true, read_at: new Date().toISOString() }))
      );
    } catch {
      // Ignored
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


  const handleNotificationClick = async (notif: NotificationResponse) => {
    if (notif.read_status === 'UNREAD') {
      try {
        await notificationsApi.markRead(notif.id);
        setUnreadCount((c) => Math.max(0, c - 1));
        setRecentNotifs((prev) =>
          prev.map((n) => (n.id === notif.id ? { ...n, read_status: 'READ', is_read: true } : n))
        );
      } catch {
        // Ignored
      }
    }
    setNotifOpen(false);

    // Navigate to resource if accessible, otherwise go to notifications page
    const link = getResourceLink(notif.related_resource_type, notif.related_resource_id);
    if (link) {
      router.push(link);
    } else {
      router.push('/notifications');
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'TASK':
      case 'TASK_ASSIGNED':
      case 'TASK_STATUS_CHANGED':
      case 'TASK_ESCALATED':
        return <ListTodo className="w-4 h-4 text-indigo-500 shrink-0" />;
      case 'REQUIREMENT':
      case 'REQUIREMENT_CREATED':
      case 'REQUIREMENT_ASSIGNED':
      case 'REQUIREMENT_ESCALATED':
        return <GitPullRequest className="w-4 h-4 text-rose-500 shrink-0" />;
      case 'MEETING':
      case 'MEETING_INVITE':
      case 'MEETING_RESCHEDULED':
        return <Users className="w-4 h-4 text-amber-500 shrink-0" />;
      case 'ISSUE':
      case 'ISSUE_CREATED':
      case 'ISSUE_ASSIGNED':
      case 'ISSUE_RESOLVED':
        return <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />;
      case 'ANNOUNCEMENT':
      case 'ANNOUNCEMENT_PUBLISHED':
        return <Megaphone className="w-4 h-4 text-sky-500 shrink-0" />;
      case 'FORM':
      case 'FORM_ASSIGNED':
      case 'REPORT':
      case 'REPORT_SUBMITTED':
      case 'REPORT_REVIEWED':
        return <FileText className="w-4 h-4 text-emerald-500 shrink-0" />;
      default:
        return <Bell className="w-4 h-4 text-zinc-500 shrink-0" />;
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
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md px-4 sm:px-6 transition-colors">
      {/* Left: Mobile Toggle, Desktop Sidebar Toggle & Brand */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {/* Mobile menu hamburger button */}
        <button
          type="button"
          onClick={onToggleSidebar}
          className="p-2 rounded-lg text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 lg:hidden cursor-pointer shrink-0"
          aria-label="Toggle navigation drawer"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2.5 min-w-0">
          <div className="min-w-0">
            <span className="font-bold text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 tracking-tight block truncate">
              Paradox Sports Department
            </span>
            <span className="hidden sm:block text-[10px] text-zinc-500 dark:text-zinc-400 -mt-0.5 truncate">
              Sports Operations Portal
            </span>
          </div>
        </div>

        {/* Vertical Scope Indicator */}
        {primaryVertical && (
          <div className="hidden md:flex items-center gap-1.5 ml-2 px-2.5 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800/80 text-zinc-700 dark:text-zinc-300 text-xs border border-zinc-200 dark:border-zinc-700 shrink-0">
            <Layers className="w-3.5 h-3.5 text-amber-500 shrink-0" />
            <span className="font-medium truncate max-w-[140px]">{primaryVertical.name}</span>
          </div>
        )}
      </div>

      {/* Right: Theme Toggle, Notification Bell & User Menu */}
      <div className="flex items-center gap-3">
        <ThemeToggle />

        {/* NOTIFICATION BELL & QUICK VIEW POPUP (Hidden on Admin Dashboard) */}
        {hasNotificationAccess && !isAdminDashboard && (
          <div className="relative" ref={notifRef}>
            <button
              type="button"
              onClick={handleToggleNotif}
              className="relative p-2 rounded-xl text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              aria-label="Notifications"
              aria-expanded={notifOpen}
            >
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white shadow-sm ring-2 ring-white dark:ring-zinc-900">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>

            {/* Quick View Popup Dropdown */}
            {notifOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setNotifOpen(false)}
                  aria-hidden="true"
                />
                <div className="absolute right-0 mt-2 w-[calc(100vw-2rem)] max-w-sm sm:w-96 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-2xl z-50 overflow-hidden animate-in fade-in zoom-in-95">
                  {/* Popup Header */}
                  <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
                    <div className="flex items-center gap-2">
                      <Bell className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                      <span className="text-xs font-bold text-zinc-900 dark:text-zinc-100">Notifications</span>
                      {unreadCount > 0 && (
                        <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 rounded-md">
                          {unreadCount} unread
                        </span>
                      )}
                    </div>

                    {unreadCount > 0 && (
                      <button
                        type="button"
                        onClick={handleMarkAllRead}
                        className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 flex items-center gap-1"
                      >
                        <CheckCheck className="w-3.5 h-3.5" />
                        Mark all read
                      </button>
                    )}
                  </div>

                  {/* Notification List */}
                  <div className="max-h-80 overflow-y-auto divide-y divide-zinc-100 dark:divide-zinc-800/80">
                    {isNotifLoading ? (
                      <div className="p-6 text-center text-xs text-zinc-400">Loading notifications...</div>
                    ) : recentNotifs.length === 0 ? (
                      <div className="p-8 text-center space-y-2">
                        <div className="w-8 h-8 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mx-auto text-zinc-400">
                          <Bell className="w-4 h-4" />
                        </div>
                        <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400">No notifications yet</p>
                        <p className="text-[11px] text-zinc-400">You&apos;re completely up to date.</p>
                      </div>
                    ) : (
                      recentNotifs.map((notif) => {
                        const isUnread = notif.read_status === 'UNREAD';
                        return (
                          <div
                            key={notif.id}
                            onClick={() => handleNotificationClick(notif)}
                            className={`flex items-start gap-3 p-3 text-xs cursor-pointer transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/60 ${
                              isUnread ? 'bg-indigo-50/30 dark:bg-indigo-950/20' : ''
                            }`}
                          >
                            <div className="mt-0.5">{getNotificationIcon(notif.notification_type)}</div>
                            <div className="flex-1 min-w-0 space-y-0.5">
                              <div className="flex items-center justify-between gap-1">
                                <p className={`text-xs font-semibold truncate ${isUnread ? 'text-zinc-900 dark:text-zinc-100' : 'text-zinc-600 dark:text-zinc-400'}`}>
                                  {notif.title}
                                </p>
                                {isUnread && <span className="w-2 h-2 rounded-full bg-indigo-600 shrink-0" />}
                              </div>
                              <p className="text-[11px] text-zinc-500 dark:text-zinc-400 line-clamp-2 leading-relaxed">
                                {notif.message}
                              </p>
                              <span className="text-[10px] text-zinc-400 block pt-0.5">
                                {new Date(notif.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>

                  {/* Popup Footer */}
                  <div className="p-2 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50 text-center">
                    <Link
                      href="/notifications"
                      onClick={() => setNotifOpen(false)}
                      className="inline-flex items-center justify-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline py-1 w-full"
                    >
                      View All Notifications
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              </>
            )}
          </div>
        )}


        {/* User Profile Dropdown */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2.5 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            aria-expanded={dropdownOpen}
          >
            <div className="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 flex items-center justify-center font-semibold text-xs border border-indigo-200 dark:border-indigo-800">
              {user?.full_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
            </div>
            <div className="hidden md:block text-left">
              <div className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 leading-tight">
                {user?.full_name || user?.username}
              </div>
              <div className="text-[10px] text-zinc-500 dark:text-zinc-400 leading-tight">
                {user?.email}
              </div>
            </div>
            <ChevronDown className="w-4 h-4 text-zinc-400 hidden md:block" />
          </button>

          {/* Dropdown Menu */}
          {dropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setDropdownOpen(false)}
                aria-hidden="true"
              />
              <div className="absolute right-0 mt-2 w-[calc(100vw-2rem)] max-w-[280px] sm:w-64 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xl z-50 py-2 animate-in fade-in zoom-in-95">
                {/* Header Info */}
                <div className="px-4 py-2.5 border-b border-zinc-100 dark:border-zinc-800">
                  <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                    {user?.full_name || user?.username}
                  </p>
                  <p className="text-[11px] text-zinc-500 dark:text-zinc-400 truncate mt-0.5">
                    {user?.email}
                  </p>
                  <div className="flex items-center gap-1.5 mt-2">
                    <Badge role={primaryRole} size="sm" />
                    {user?.account_status && (
                      <span className="text-[10px] text-zinc-500 dark:text-zinc-400 uppercase font-mono">
                        {user.account_status}
                      </span>
                    )}
                  </div>
                </div>

                {/* Vertical List */}
                {user?.verticals && user.verticals.length > 0 && (
                  <div className="px-4 py-2 border-b border-zinc-100 dark:border-zinc-800">
                    <p className="text-[10px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-1">
                      Assigned Verticals
                    </p>
                    <div className="space-y-1">
                      {user.verticals.map((v) => (
                        <div
                          key={v.id}
                          className="flex items-center justify-between text-xs text-zinc-700 dark:text-zinc-300"
                        >
                          <span className="truncate">{v.name}</span>
                          {v.is_primary && (
                            <span className="text-[9px] bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 px-1.5 py-0.5 rounded-xs font-medium">
                              Primary
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="p-1.5 space-y-1">
                  <Link
                    href="/profile"
                    onClick={() => setDropdownOpen(false)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                  >
                    <User className="w-4 h-4 text-indigo-500" />
                    <span>My Profile</span>
                  </Link>

                  <Link
                    href="/profile"
                    onClick={() => setDropdownOpen(false)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                  >
                    <Lock className="w-4 h-4 text-purple-500" />
                    <span>Change Password</span>
                  </Link>

                  <div className="pt-1 border-t border-zinc-100 dark:border-zinc-800">
                    <button
                      type="button"
                      onClick={async () => {
                        setDropdownOpen(false);
                        await logout();
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Sign out</span>
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
