'use client';

/**
 * Minimal & Professional Event Team Workspace.
 * Scoped strictly to designated match/tournament duties, announcements, and team communications.
 */

import React from 'react';
import Link from 'next/link';
import { UnifiedMyWorkResponse } from '@/types/workspace';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  Flag,
  Calendar,
  MapPin,
  Megaphone,
  Bell,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';

export interface EventTeamWorkspaceProps {
  myWork: UnifiedMyWorkResponse | null;
  isLoading: boolean;
}

export const EventTeamWorkspace: React.FC<EventTeamWorkspaceProps> = ({ myWork, isLoading }) => {
  const duties = myWork?.event_duties || [];

  return (
    <div className="space-y-4">
      {/* Quick Team Links */}
      <div className="flex flex-wrap items-center gap-2">
        <Link href="/events">
          <Button variant="primary" size="sm" leftIcon={<Flag className="w-3.5 h-3.5" />}>
            My Events
          </Button>
        </Link>
        <Link href="/announcements">
          <Button variant="outline" size="sm" leftIcon={<Megaphone className="w-3.5 h-3.5 text-indigo-500" />}>
            Official Announcements
          </Button>
        </Link>
        <Link href="/notifications">
          <Button variant="outline" size="sm" leftIcon={<Bell className="w-3.5 h-3.5 text-amber-500" />}>
            Notifications
          </Button>
        </Link>
      </div>

      {/* Designated Event Duties */}
      {duties.length > 0 ? (
        <Card>
          <CardHeader className="py-3 px-4 flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <Flag className="w-4 h-4 text-emerald-500" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider">
                Designated Event Duties ({duties.length})
              </CardTitle>
            </div>
            <Link href="/events">
              <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                View Details
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800 text-xs">
              {duties.map((duty) => (
                <div
                  key={duty.event_id}
                  className="p-3.5 flex items-center justify-between gap-3"
                >
                  <div className="space-y-1 min-w-0">
                    <p className="font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                      {duty.title}
                    </p>
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-zinc-500 dark:text-zinc-400">
                      <span className="flex items-center gap-1 font-mono text-[10px]">
                        <Calendar className="w-3 h-3 text-zinc-400" />
                        {duty.planned_date}
                      </span>
                      {duty.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-zinc-400" />
                          {duty.location}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="purple" size="sm">{duty.role}</Badge>
                    <Badge variant="success" size="sm">{duty.event_status}</Badge>
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
            <span>Event Operations Scope Active • No upcoming matches or duties scheduled for your roster today.</span>
          </div>
          <Link href="/events">
            <Button size="sm" variant="ghost" rightIcon={<ArrowRight className="w-3 h-3" />}>
              Browse Event Calendar
            </Button>
          </Link>
        </div>
      )}
    </div>
  );
};
