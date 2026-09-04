'use client';

/**
 * PriorityQueue - "Requires Immediate Attention" section
 * Renders urgent/overdue/critical items at the top of the command center.
 * Only renders when there are items to show; cleanly omitted otherwise.
 */

import React from 'react';
import Link from 'next/link';
import { MyWorkPriorityItem } from '@/types/workspace';
import { Button } from '@/components/ui/Button';
import {
  AlertOctagon,
  Clock,
  FileText,
  ShieldAlert,
  CheckSquare,
  ArrowRight,
  Flame,
  AlertTriangle,
} from 'lucide-react';

interface PriorityQueueProps {
  items: MyWorkPriorityItem[];
}

const urgencyConfig: Record<string, { bg: string; border: string; icon: React.ReactNode; badge: string }> = {
  OVERDUE: {
    bg: 'bg-rose-50/80 dark:bg-rose-950/30',
    border: 'border-rose-200 dark:border-rose-800/50',
    icon: <Clock className="w-4 h-4 text-rose-500" />,
    badge: 'bg-rose-100 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800/50',
  },
  CRITICAL: {
    bg: 'bg-orange-50/80 dark:bg-orange-950/30',
    border: 'border-orange-200 dark:border-orange-800/50',
    icon: <Flame className="w-4 h-4 text-orange-500" />,
    badge: 'bg-orange-100 dark:bg-orange-950/50 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-800/50',
  },
  APPROVAL_NEEDED: {
    bg: 'bg-amber-50/80 dark:bg-amber-950/30',
    border: 'border-amber-200 dark:border-amber-800/50',
    icon: <ShieldAlert className="w-4 h-4 text-amber-500" />,
    badge: 'bg-amber-100 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800/50',
  },
  DEADLINE_SOON: {
    bg: 'bg-yellow-50/80 dark:bg-yellow-950/30',
    border: 'border-yellow-200 dark:border-yellow-800/50',
    icon: <AlertTriangle className="w-4 h-4 text-yellow-600" />,
    badge: 'bg-yellow-100 dark:bg-yellow-950/50 text-yellow-700 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800/50',
  },
  ACTION_REQUIRED: {
    bg: 'bg-purple-50/80 dark:bg-purple-950/30',
    border: 'border-purple-200 dark:border-purple-800/50',
    icon: <AlertOctagon className="w-4 h-4 text-purple-500" />,
    badge: 'bg-purple-100 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800/50',
  },
};

const itemTypeIcon: Record<string, React.ReactNode> = {
  TASK: <CheckSquare className="w-3.5 h-3.5" />,
  ISSUE: <ShieldAlert className="w-3.5 h-3.5" />,
  FORM: <FileText className="w-3.5 h-3.5" />,
  REVIEW: <ShieldAlert className="w-3.5 h-3.5" />,
  APPROVAL: <ShieldAlert className="w-3.5 h-3.5" />,
};

export const PriorityQueue: React.FC<PriorityQueueProps> = ({ items }) => {
  if (!items || items.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="p-1.5 rounded-lg bg-rose-500/15 text-rose-600 dark:text-rose-400">
          <AlertOctagon className="w-4 h-4" />
        </div>
        <h2 className="text-xs font-bold uppercase tracking-wider text-rose-700 dark:text-rose-400">
          Requires Immediate Attention ({items.length})
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.slice(0, 8).map((item) => {
          const config = urgencyConfig[item.urgency] || urgencyConfig.ACTION_REQUIRED;

          return (
            <div
              key={item.id}
              className={`p-4 rounded-xl border ${config.bg} ${config.border} flex items-start justify-between gap-3 transition-all hover:shadow-sm`}
            >
              <div className="flex items-start gap-3 min-w-0 flex-1">
                <div className="shrink-0 mt-0.5">{config.icon}</div>
                <div className="space-y-1.5 min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${config.badge}`}
                    >
                      {item.urgency_label}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[10px] text-zinc-500 dark:text-zinc-400 font-medium">
                      {itemTypeIcon[item.item_type]}
                      {item.item_type}
                    </span>
                  </div>
                  <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                    {item.title}
                  </p>
                  {item.detail && (
                    <p className="text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed line-clamp-2">
                      {item.detail}
                    </p>
                  )}
                  {item.due_date && (
                    <p className="text-[10px] text-zinc-500 dark:text-zinc-400 font-mono">
                      Due: {new Date(item.due_date).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>

              <Link href={(item.action_link || '/').replace(/^\/workspace\//, '/')} className="shrink-0">
                <Button
                  size="sm"
                  variant={item.urgency === 'OVERDUE' || item.urgency === 'CRITICAL' ? 'danger' : 'outline'}
                  rightIcon={<ArrowRight className="w-3 h-3" />}
                >
                  {item.action_label}
                </Button>
              </Link>
            </div>
          );
        })}
      </div>
    </div>
  );
};
