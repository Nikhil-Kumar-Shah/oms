'use client';

/**
 * Minimal & Professional Operational Workspace (Coordinators & Volunteers).
 * Zero-filler layout: No empty sections, direct actionable quick links, and clean workload status.
 */

import React from 'react';
import Link from 'next/link';
import { UnifiedMyWorkResponse } from '@/types/workspace';
import { useAuth } from '@/hooks/useAuth';
import { canAssignTask } from '@/lib/permissions';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  CheckSquare,
  Clock,
  Calendar,
  Users,
  ShieldAlert,
  ArrowRight,
  Plus,
  FileText,
  CheckCircle2,
} from 'lucide-react';

export interface OperationalWorkspaceProps {
  myWork: UnifiedMyWorkResponse | null;
  isLoading: boolean;
}

export const OperationalWorkspace: React.FC<OperationalWorkspaceProps> = ({ myWork, isLoading }) => {
  const { user, hasPermission } = useAuth();
  const tasks = myWork?.tasks || [];
  const upcomingMeetings = myWork?.meetings || [];
  const pendingForms = myWork?.pending_forms || [];

  const canReadTasks = hasPermission('tasks.read');
  const canCreateTask = hasPermission('tasks.create') || canAssignTask(user);
  const canSubmitReport = hasPermission('reports.submit');
  const canCreateMeeting = hasPermission('meetings.create');
  const canCreateIssue = hasPermission('issues.create');
  const canAccessForms = hasPermission('forms.read') || hasPermission('forms.submit');

  return (
    <div className="space-y-4">
      {/* Personalized Quick Actions (Gated strictly by permission) */}
      <div className="flex flex-wrap items-center gap-2">
        {canReadTasks && (
          <Link href="/tasks">
            <Button variant="primary" size="sm" leftIcon={<CheckSquare className="w-3.5 h-3.5" />}>
              My Tasks
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
        {canSubmitReport && (
          <Link href="/reports">
            <Button variant="outline" size="sm" leftIcon={<FileText className="w-3.5 h-3.5 text-blue-500" />}>
              Daily Report
            </Button>
          </Link>
        )}
        {canCreateIssue && (
          <Link href="/issues">
            <Button variant="outline" size="sm" leftIcon={<ShieldAlert className="w-3.5 h-3.5 text-rose-500" />}>
              Raise Issue
            </Button>
          </Link>
        )}
        {canCreateMeeting && (
          <Link href="/meetings">
            <Button variant="outline" size="sm" leftIcon={<Calendar className="w-3.5 h-3.5 text-indigo-500" />}>
              Schedule Meeting
            </Button>
          </Link>
        )}
        {canAccessForms && pendingForms.length > 0 && (
          <Link href="/forms">
            <Button variant="outline" size="sm" leftIcon={<FileText className="w-3.5 h-3.5 text-emerald-500" />}>
              Pending Forms ({pendingForms.length})
            </Button>
          </Link>
        )}
      </div>

      {/* Active Workload: Render tasks if present, otherwise clean compact zero-filler prompt */}
      {tasks.length > 0 ? (
        <Card>
          <CardHeader className="py-3 px-4 flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-indigo-500" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider">
                Assigned Operational Tasks ({tasks.length})
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
                    <Badge
                      variant={
                        task.status === 'COMPLETED'
                          ? 'success'
                          : task.status === 'BLOCKED'
                          ? 'danger'
                          : 'info'
                      }
                      size="sm"
                    >
                      {task.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/40 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 text-xs text-zinc-600 dark:text-zinc-400">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span>Operational Workload Clear • You have no active pending tasks assigned.</span>
          </div>
          {canCreateTask && (
            <Link href="/tasks">
              <Button size="sm" variant="ghost" rightIcon={<ArrowRight className="w-3 h-3" />}>
                Browse Vertical Tasks
              </Button>
            </Link>
          )}
        </div>
      )}

      {/* Upcoming Meetings (Only rendered when user actually has scheduled meetings) */}
      {upcomingMeetings.length > 0 && (
        <Card>
          <CardHeader className="py-3 px-4 flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-sky-500" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider">
                Upcoming Meetings ({upcomingMeetings.length})
              </CardTitle>
            </div>
            <Link href="/meetings">
              <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                All Meetings
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800 text-xs">
              {upcomingMeetings.slice(0, 3).map((meeting) => (
                <div key={meeting.id} className="p-3 flex items-center justify-between gap-3">
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                    {meeting.title}
                  </p>
                  <span className="text-[11px] text-zinc-500 font-mono shrink-0">
                    {meeting.meeting_date}
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
