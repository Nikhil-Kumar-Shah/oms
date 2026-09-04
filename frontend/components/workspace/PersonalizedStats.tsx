'use client';

/**
 * PersonalizedStats – Minimal, professional, zero-filler metrics cards.
 * ONLY renders active metrics (value > 0).
 * Eliminates empty filler cards (no "0" counters) and duplicate signals.
 */

import React from 'react';
import Link from 'next/link';
import { UnifiedMyWorkResponse, MyWorkUserContext } from '@/types/workspace';
import { CanonicalRole } from '@/types/user';
import { useAuth } from '@/hooks/useAuth';
import {
  CheckSquare,
  Clock,
  FileText,
  ShieldAlert,
  ArrowUpRight,
  Flame,
  TrendingUp,
  Inbox,
  ClipboardList,
  Calendar,
} from 'lucide-react';

interface PersonalizedStatsProps {
  myWork: UnifiedMyWorkResponse;
  userCtx: MyWorkUserContext;
}

interface StatCard {
  id: string;
  label: string;
  value: number;
  icon: React.ReactNode;
  accent: string;
  link: string;
}

function buildCards(
  myWork: UnifiedMyWorkResponse,
  userCtx: MyWorkUserContext,
  hasPermission: (p: string) => boolean,
  hasRole: (r: CanonicalRole) => boolean
): StatCard[] {
  const cards: StatCard[] = [];
  const role = userCtx.primary_role?.toLowerCase() ?? '';
  const isExec = hasRole('ADMIN') || role.includes('admin') || role.includes('core') || role.includes('deputy');

  /* 1. Active Assigned Tasks (Only if user has active tasks) */
  const tasksCount = (myWork.tasks ?? []).length;
  if (tasksCount > 0) {
    cards.push({
      id: 'my_tasks',
      label: 'My Tasks',
      value: tasksCount,
      icon: <CheckSquare className="w-4 h-4" />,
      accent: 'from-blue-500 to-indigo-600',
      link: '/tasks',
    });
  }

  /* 2. Overdue Tasks (Only if > 0) */
  const overdueTasks = (myWork.overdue ?? []).length;
  if (overdueTasks > 0) {
    cards.push({
      id: 'overdue',
      label: 'Overdue Tasks',
      value: overdueTasks,
      icon: <Clock className="w-4 h-4" />,
      accent: 'from-rose-500 to-red-600',
      link: '/tasks?filter=overdue',
    });
  }

  /* 3. Pending Tasks (Only if > 0) */
  const pendingTasks = (myWork.tasks ?? []).filter(
    (t) => t.status === 'NOT_STARTED' || t.status === 'TODO'
  ).length;
  if (pendingTasks > 0) {
    cards.push({
      id: 'pending',
      label: 'Pending Tasks',
      value: pendingTasks,
      icon: <Inbox className="w-4 h-4" />,
      accent: 'from-amber-500 to-orange-600',
      link: '/tasks?filter=pending',
    });
  }

  /* 4. Active Issues & Escalations (De-duplicated: Never double count an issue) */
  const activeIssues = myWork.active_issues ?? [];
  const escalationsCount = activeIssues.filter((i) => i.status === 'ESCALATED').length;
  const standardIssuesCount = activeIssues.filter((i) => i.status !== 'ESCALATED').length;

  if (escalationsCount > 0 && (hasPermission('issues.read') || isExec)) {
    cards.push({
      id: 'escalations',
      label: 'Active Escalations',
      value: escalationsCount,
      icon: <Flame className="w-4 h-4" />,
      accent: 'from-rose-600 to-red-700',
      link: '/issues',
    });
  }

  if (standardIssuesCount > 0 && (hasPermission('issues.read') || isExec)) {
    cards.push({
      id: 'issues',
      label: 'Open Issues',
      value: standardIssuesCount,
      icon: <ShieldAlert className="w-4 h-4" />,
      accent: 'from-orange-500 to-amber-600',
      link: '/issues',
    });
  }

  /* 5. Pending Forms (Only if user has pending submissions > 0) */
  const formsCount = myWork.pending_forms?.length ?? 0;
  if ((hasPermission('forms.read') || hasPermission('forms.submit')) && formsCount > 0) {
    cards.push({
      id: 'forms',
      label: 'Pending Forms',
      value: formsCount,
      icon: <FileText className="w-4 h-4" />,
      accent: 'from-emerald-500 to-teal-600',
      link: '/forms',
    });
  }


  /* 7. Upcoming Meetings (Only if > 0) */
  const meetingsCount = myWork.meetings?.length ?? 0;
  if ((hasPermission('meetings.read') || hasPermission('meetings.rsvp')) && meetingsCount > 0) {
    cards.push({
      id: 'meetings',
      label: 'Upcoming Meetings',
      value: meetingsCount,
      icon: <Calendar className="w-4 h-4" />,
      accent: 'from-sky-500 to-cyan-600',
      link: '/meetings',
    });
  }

  /* 8. Event Team In-Progress Duties (Only if event team profile and > 0) */
  if (userCtx.event_team_profile && (userCtx.event_team_profile as any).team_name) {
    const inProgress = (myWork.tasks ?? []).filter((t) => t.status === 'IN_PROGRESS').length;
    if (inProgress > 0) {
      cards.push({
        id: 'team_in_progress',
        label: 'In Progress',
        value: inProgress,
        icon: <TrendingUp className="w-4 h-4" />,
        accent: 'from-cyan-500 to-blue-600',
        link: '/tasks',
      });
    }
  }

  return cards;
}

export const PersonalizedStats: React.FC<PersonalizedStatsProps> = ({
  myWork,
  userCtx,
}) => {
  const { hasPermission, hasRole } = useAuth();
  const cards = buildCards(myWork, userCtx, hasPermission, hasRole);

  // If user has zero active items, completely omit this section (no empty filler cards)
  if (cards.length === 0) return null;

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
          Operational Metrics
        </h2>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2.5">
        {cards.map((card) => (
          <Link
            key={card.id}
            href={card.link}
            className="group block rounded-xl border border-zinc-200/90 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3.5 transition-all hover:border-zinc-300 dark:hover:border-zinc-700 hover:shadow-xs"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="space-y-1 min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 truncate">
                  {card.label}
                </p>
                <p className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                  {card.value}
                </p>
              </div>

              <div className={`p-1.5 rounded-lg bg-gradient-to-br ${card.accent} text-white shrink-0`}>
                {card.icon}
              </div>
            </div>

            <div className="mt-2.5 flex items-center gap-1 text-[10px] font-medium text-zinc-400 group-hover:text-zinc-600 dark:group-hover:text-zinc-300 transition-colors">
              <span>View details</span>
              <ArrowUpRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};
