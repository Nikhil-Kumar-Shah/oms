'use client';

import React from 'react';
import { MyWorkStats } from '@/types/workspace';
import { CheckSquare, ShieldAlert, Users, Flag, AlertOctagon, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface WorkspaceStatsProps {
  stats?: MyWorkStats;
  isLoading?: boolean;
}

export const WorkspaceStats: React.FC<WorkspaceStatsProps> = ({ stats, isLoading }) => {
  const items = [
    {
      label: 'Active Tasks',
      value: stats?.active_tasks ?? 0,
      icon: <CheckSquare className="w-4 h-4 text-indigo-500" />,
      bg: 'bg-indigo-50 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800/50',
    },
    {
      label: 'Completed Tasks',
      value: stats?.completed_tasks ?? 0,
      icon: <CheckSquare className="w-4 h-4 text-emerald-500" />,
      bg: 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/50',
    },
    {
      label: 'Created by Me',
      value: stats?.created_by_me_tasks ?? 0,
      icon: <Users className="w-4 h-4 text-purple-500" />,
      bg: 'bg-purple-50 dark:bg-purple-950/40 border-purple-200 dark:border-purple-800/50',
    },
    {
      label: 'Blocked Tasks',
      value: stats?.blocked_tasks ?? 0,
      icon: <AlertOctagon className="w-4 h-4 text-rose-500" />,
      bg: 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800/50',
    },
    {
      label: 'Overdue Tasks',
      value: stats?.overdue_tasks ?? 0,
      icon: <Clock className="w-4 h-4 text-orange-500" />,
      bg: 'bg-orange-50 dark:bg-orange-950/40 border-orange-200 dark:border-orange-800/50',
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">

      {items.map((item) => (
        <div
          key={item.label}
          className={cn('p-3.5 rounded-xl border flex flex-col justify-between transition-all', item.bg)}
        >
          <div className="flex items-center justify-between text-zinc-600 dark:text-zinc-400">
            <span className="text-[11px] font-medium leading-tight">{item.label}</span>
            {item.icon}
          </div>
          <div className="mt-2 text-xl font-bold text-zinc-900 dark:text-zinc-100">
            {isLoading ? (
              <span className="inline-block w-6 h-5 bg-zinc-200 dark:bg-zinc-700 animate-pulse rounded-xs" />
            ) : (
              item.value
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
