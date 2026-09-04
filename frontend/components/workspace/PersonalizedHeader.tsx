'use client';

import React from 'react';
import { UnifiedMyWorkResponse } from '@/types/workspace';
import { UserProfile, CanonicalRole, VerticalMembership } from '@/types/user';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  Layers,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Flag,
  ArrowRight,
} from 'lucide-react';

interface PersonalizedHeaderProps {
  user: UserProfile | null;
  myWork: UnifiedMyWorkResponse | null;
  roleNames: CanonicalRole[];
  primaryVertical: VerticalMembership | null;
  isLoading: boolean;
  onRefresh: () => void;
  onJumpToPriority?: () => void;
}

export const PersonalizedHeader: React.FC<PersonalizedHeaderProps> = ({
  user,
  myWork,
  roleNames,
  primaryVertical,
  isLoading,
  onRefresh,
  onJumpToPriority,
}) => {
  const context = myWork?.context;
  const primaryRole = (context?.primary_role || roleNames[0] || 'VOLUNTEER') as CanonicalRole;
  const eventTeamProfile = context?.event_team_profile;
  const priorityCount = myWork?.priority_queue?.length || 0;
  const hasUrgentAction = context?.requires_immediate_attention || priorityCount > 0;
  const attentionSummary =
    context?.attention_summary ||
    (priorityCount > 0
      ? `You have ${priorityCount} priority item${priorityCount > 1 ? 's' : ''} requiring your immediate action.`
      : 'All caught up! No urgent items or overdue deadlines requiring your attention right now.');

  return (
    <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm p-5 sm:p-6 shadow-xs transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* User Identity & Scope */}
        <div className="space-y-1.5 min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Welcome, {user?.full_name || user?.username}
            </h1>
            <Badge role={primaryRole} size="md" />
            {user?.account_status && user.account_status !== 'ACTIVE' && (
              <Badge variant="danger" size="sm">
                {user.account_status}
              </Badge>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
            {primaryVertical ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium">
                <Layers className="w-3.5 h-3.5 text-zinc-400" />
                <span>{primaryVertical.name}</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                <Layers className="w-3.5 h-3.5 text-zinc-400" />
                <span>Organization Scope</span>
              </span>
            )}

            {eventTeamProfile && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/50 text-amber-700 dark:text-amber-300 font-semibold">
                <Flag className="w-3.5 h-3.5 text-amber-500" />
                <span>Team: {eventTeamProfile.team_name}</span>
                {eventTeamProfile.event_name && (
                  <span className="text-amber-600 dark:text-amber-400 font-normal">
                    • {eventTeamProfile.event_name}
                  </span>
                )}
              </span>
            )}
          </div>
        </div>

        {/* Status Badge & Actions */}
        <div className="flex items-center gap-2.5 shrink-0 self-start sm:self-center">
          {hasUrgentAction ? (
            <button
              onClick={onJumpToPriority}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/50 text-rose-700 dark:text-rose-300 text-xs font-semibold hover:bg-rose-100 dark:hover:bg-rose-900/40 transition-colors cursor-pointer"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-rose-500 animate-pulse" />
              <span>{priorityCount} Action{priorityCount !== 1 ? 's' : ''} Needed</span>
              <ArrowRight className="w-3 h-3 text-rose-400" />
            </button>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/50 text-emerald-700 dark:text-emerald-300 text-xs font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <span>All Systems On Track</span>
            </span>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            title="Refresh workspace telemetry"
          >
            Sync
          </Button>
        </div>
      </div>

      {/* Concise Attention Line */}
      {hasUrgentAction && (
        <div className="mt-3 pt-3 border-t border-zinc-100 dark:border-zinc-800/80 flex items-center gap-2 text-xs text-rose-700 dark:text-rose-300">
          <span className="font-semibold uppercase tracking-wider text-[10px] px-1.5 py-0.5 rounded bg-rose-100 dark:bg-rose-900/40">
            Immediate Attention
          </span>
          <span className="truncate">{attentionSummary}</span>
        </div>
      )}
    </div>
  );
};
