'use client';

/**
 * Minimal & Professional Executive Command Center (SPORTS_CORE & DEPUTY_CORE)
 * Strictly permission-gated: Only renders tabs and modules the user is explicitly authorized to access.
 * Zero directives, zero governance clutter.
 */

import React from 'react';
import Link from 'next/link';
import { UnifiedMyWorkResponse } from '@/types/workspace';
import { useAuth } from '@/hooks/useAuth';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  CheckSquare,
  Calendar,
  Layers,
  ArrowRight,
  Clock,
  ShieldAlert,
  FileText,
  BarChart3,
  Users,
  Plus,
} from 'lucide-react';

export interface ExecutiveWorkspaceProps {
  myWork: UnifiedMyWorkResponse | null;
  isLoading: boolean;
}

export const ExecutiveWorkspace: React.FC<ExecutiveWorkspaceProps> = ({ myWork, isLoading }) => {
  const { hasPermission } = useAuth();
  const tasks = myWork?.tasks || [];
  const upcomingMeetings = myWork?.meetings || [];

  // Strictly check permissions for all tabs/actions before displaying anything
  const canReadTasks = hasPermission('tasks.read');
  const canCreateTask = hasPermission('tasks.create');
  const canReadCalendar = hasPermission('calendar.read');
  const canReadIssues = hasPermission('issues.read');
  const canReadReports = hasPermission('reports.read');
  const canReadAnalytics = hasPermission('analytics.read');
  const canReadMeetings = hasPermission('meetings.read');

  return (
    <div className="space-y-4">
      {/* Executive Permitted Actions (Only show tabs the user is actually allowed to access) */}
      <div className="flex flex-wrap items-center gap-2">
        {canReadTasks && (
          <Link href="/tasks">
            <Button variant="primary" size="sm" leftIcon={<CheckSquare className="w-3.5 h-3.5" />}>
              Master Tasks
            </Button>
          </Link>
        )}
        {canCreateTask && (
          <Link href="/tasks">
            <Button variant="outline" size="sm" leftIcon={<Plus className="w-3.5 h-3.5" />}>
              Create Task
            </Button>
          </Link>
        )}
        {canReadCalendar && (
          <Link href="/calendar">
            <Button variant="outline" size="sm" leftIcon={<Calendar className="w-3.5 h-3.5 text-indigo-500" />}>
              Master Calendar
            </Button>
          </Link>
        )}
        {canReadIssues && (
          <Link href="/issues">
            <Button variant="outline" size="sm" leftIcon={<ShieldAlert className="w-3.5 h-3.5 text-rose-500" />}>
              Issue Register
            </Button>
          </Link>
        )}
        {canReadReports && (
          <Link href="/reports">
            <Button variant="outline" size="sm" leftIcon={<FileText className="w-3.5 h-3.5 text-blue-500" />}>
              Work Reports
            </Button>
          </Link>
        )}
        {canReadAnalytics && (
          <Link href="/analytics">
            <Button variant="outline" size="sm" leftIcon={<BarChart3 className="w-3.5 h-3.5 text-emerald-500" />}>
              Analytics
            </Button>
          </Link>
        )}
        {canReadMeetings && (
          <Link href="/meetings">
            <Button variant="outline" size="sm" leftIcon={<Users className="w-3.5 h-3.5 text-sky-500" />}>
              Meetings
            </Button>
          </Link>
        )}
      </div>

      {/* Strategic Operational Supervision (Only if user has permission AND tasks exist) */}
      {canReadTasks && tasks.length > 0 && (
        <Card>
          <CardHeader className="py-3 px-4 flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-500" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider">
                Cross-Vertical Tasks Under Supervision ({tasks.length})
              </CardTitle>
            </div>
            <Link href="/tasks">
              <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                View All
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800 text-xs">
              {tasks.slice(0, 5).map((task) => (
                <div key={task.id} className="p-3 flex items-center justify-between gap-3">
                  <div className="space-y-0.5 min-w-0">
                    <p className="font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                      {task.title}
                    </p>
                    <div className="flex items-center gap-2 text-[11px] text-zinc-500 dark:text-zinc-400">
                      {task.vertical_name && <span>{task.vertical_name}</span>}
                      {task.deadline && (
                        <span className="flex items-center gap-1 font-mono text-[10px]">
                          <Clock className="w-3 h-3 text-zinc-400" />
                          {new Date(task.deadline).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Badge variant={task.status === 'COMPLETED' ? 'success' : task.status === 'BLOCKED' ? 'danger' : 'info'} size="sm">
                      {task.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Upcoming Meetings (Only if user has permission AND meetings exist) */}
      {canReadMeetings && upcomingMeetings.length > 0 && (
        <Card>
          <CardHeader className="py-3 px-4 flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-sky-500" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider">
                Upcoming Executive Sessions ({upcomingMeetings.length})
              </CardTitle>
            </div>
            <Link href="/meetings">
              <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                View Calendar
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800 text-xs">
              {upcomingMeetings.slice(0, 3).map((m) => (
                <div key={m.id} className="p-3 flex items-center justify-between gap-3">
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                    {m.title}
                  </p>
                  <span className="text-[11px] text-zinc-500 font-mono shrink-0">
                    {m.meeting_date}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
