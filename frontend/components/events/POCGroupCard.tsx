'use client';

/**
 * Event POC Group & Coordination Card & Management Modal
 * Standardized on canonical UniversalAudienceSelector for Head POC and POC Members
 */

import React, { useState } from 'react';
import { UserCheck, Users, Shield, X, AlertCircle } from 'lucide-react';
import { POCGroupResponse, POCGroupAssignRequest } from '@/types/event';
import { UserSummary } from '@/types/organization';
import { eventsApi } from '@/lib/api';
import { UniversalAudienceSelector, AudienceItem } from '@/components/ui/UniversalAudienceSelector';

interface POCGroupCardProps {
  pocGroup: POCGroupResponse | null;
  eventId: string;
  verticalId?: string;
  canManage: boolean;
  eligibleUsers: UserSummary[];
  onUpdated: () => void;
}

export function POCGroupCard({
  pocGroup,
  eventId,
  verticalId,
  canManage,
  eligibleUsers,
  onUpdated,
}: POCGroupCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [headPocSelection, setHeadPocSelection] = useState<AudienceItem[]>([]);
  const [membersSelection, setMembersSelection] = useState<AudienceItem[]>([]);
  const [notes, setNotes] = useState<string>(pocGroup?.head_poc?.notes || '');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleOpenModal = () => {
    const initialHead: AudienceItem[] = pocGroup?.head_poc
      ? [
          {
            id: `USER:${pocGroup.head_poc.user_id}`,
            type: 'USER',
            rawId: pocGroup.head_poc.user_id,
            label: pocGroup.head_poc.full_name || pocGroup.head_poc.username || 'POC Lead',
            sublabel: pocGroup.head_poc.username ? `@${pocGroup.head_poc.username}` : undefined,
          },
        ]
      : [];
    setHeadPocSelection(initialHead);

    const initialMembers: AudienceItem[] = (pocGroup?.poc_members || []).map((m) => ({
      id: `USER:${m.user_id}`,
      type: 'USER',
      rawId: m.user_id,
      label: m.full_name || m.username || 'POC Member',
      sublabel: m.username ? `@${m.username}` : undefined,
    }));
    setMembersSelection(initialMembers);

    setNotes(pocGroup?.head_poc?.notes || '');
    setError(null);
    setIsModalOpen(true);
  };

  const handleSavePOCGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    const headId = headPocSelection[0]?.rawId;
    if (!headId) {
      setError('A designated Head POC is required.');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const memberIds = membersSelection.map((it) => it.rawId);
      const payload: POCGroupAssignRequest = {
        head_poc_id: headId,
        poc_member_ids: memberIds,
        notes: notes.trim() || undefined,
      };
      await eventsApi.assignPOCGroup(eventId, payload);
      setIsModalOpen(false);
      onUpdated();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to assign POC group';
      setError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="rounded-2xl border border-zinc-200/80 bg-white p-5 sm:p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center border-b border-zinc-100 pb-4 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-amber-500/10 p-2.5 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Event POC Group & Coordination
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Authoritative operational contacts and point-of-contact governance
            </p>
          </div>
        </div>
        {canManage && (
          <button
            onClick={handleOpenModal}
            className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-3.5 py-2 text-xs font-semibold text-zinc-950 shadow-sm hover:from-amber-400 hover:to-orange-400 transition-all cursor-pointer"
          >
            <UserCheck className="h-3.5 w-3.5" />
            Manage POCs
          </button>
        )}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Head POC Section */}
        <div className="rounded-xl border border-zinc-200/70 bg-zinc-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-800/40">
          <span className="inline-flex items-center gap-1 text-xs font-semibold tracking-wide uppercase text-amber-600 dark:text-amber-400">
            <Shield className="h-3.5 w-3.5" />
            Designated Head POC
          </span>
          {pocGroup?.head_poc ? (
            <div className="mt-3 flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-500/15 font-semibold text-amber-700 dark:text-amber-300">
                {(pocGroup.head_poc.full_name || pocGroup.head_poc.username || 'P')[0].toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  {pocGroup.head_poc.full_name || pocGroup.head_poc.username}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  @{pocGroup.head_poc.username}
                </p>
                {pocGroup.head_poc.notes && (
                  <p className="mt-2 text-xs text-zinc-600 italic dark:text-zinc-400">
                    &quot;{pocGroup.head_poc.notes}&quot;
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="mt-3 text-xs text-slate-500 italic dark:text-slate-400">
              No Head POC designated yet.
            </div>
          )}
        </div>

        {/* POC Members Section */}
        <div className="rounded-xl border border-zinc-200/70 bg-zinc-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-800/40">
          <span className="inline-flex items-center gap-1 text-xs font-semibold tracking-wide uppercase text-zinc-600 dark:text-zinc-400">
            <Users className="h-3.5 w-3.5" />
            POC Members ({pocGroup?.poc_members?.length || 0})
          </span>
          {pocGroup?.poc_members && pocGroup.poc_members.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {pocGroup.poc_members.map((member) => (
                <div
                  key={member.user_id}
                  className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-700 shadow-xs dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                >
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span>{member.full_name || member.username}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 text-xs text-zinc-500 italic dark:text-zinc-400">
              No additional POC members assigned.
            </div>
          )}
        </div>
      </div>

      {/* Modal for Assigning POC Group */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 sm:p-4 md:p-6 backdrop-blur-xs">
          <div className="relative w-[95vw] sm:w-[90vw] md:w-[75vw] lg:w-[62vw] max-w-3xl max-h-[88vh] flex flex-col rounded-2xl border border-zinc-200/80 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
            <div className="shrink-0 px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between bg-white dark:bg-zinc-900">
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-amber-500" />
                <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100">
                  Assign POC Group
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSavePOCGroup} className="flex flex-col flex-1 min-h-0 overflow-hidden">
              <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4">
                {error && (
                  <div className="flex items-center gap-2 rounded-lg bg-rose-50 p-3 text-xs text-rose-700 dark:bg-rose-950/30 dark:text-rose-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                {/* Head POC Selector using UniversalAudienceSelector */}
                <div>
                  <UniversalAudienceSelector
                    mode="USER"
                    usage="assignment"
                    label="Head POC (Exactly 1 Active Lead)"
                    required
                    placeholder="Select Head POC..."
                    verticalId={verticalId}
                    value={headPocSelection}
                    onChange={(items) => {
                      setHeadPocSelection(items);
                      if (items[0]) {
                        setMembersSelection((prev) => prev.filter((p) => p.rawId !== items[0].rawId));
                      }
                    }}
                  />
                </div>

                {/* POC Members Multi-Select using UniversalAudienceSelector */}
                <div>
                  <UniversalAudienceSelector
                    mode="USER"
                    multi={true}
                    usage="assignment"
                    label="Additional POC Members"
                    placeholder="Select additional POC members..."
                    verticalId={verticalId}
                    value={membersSelection}
                    onChange={(items) => {
                      const filtered = headPocSelection[0]
                        ? items.filter((it) => it.rawId !== headPocSelection[0].rawId)
                        : items;
                      setMembersSelection(filtered);
                    }}
                  />
                </div>

                {/* Operational Remarks */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                    Operational Notes / Briefing
                  </label>
                  <textarea
                    rows={3}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Operational briefing notes, POC responsibilities, match-day coordination instructions..."
                    className="mt-1.5 w-full rounded-xl border border-zinc-300 bg-white p-2.5 text-xs text-zinc-900 focus:border-amber-500 focus:outline-none dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"
                  />
                </div>
              </div>

              {/* Fixed Footer Action Buttons */}
              <div className="shrink-0 flex justify-end gap-3 px-6 py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="rounded-xl border border-zinc-300 px-4 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving || headPocSelection.length === 0}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2 text-xs font-semibold text-zinc-950 hover:from-amber-400 hover:to-orange-400 disabled:opacity-50 transition-colors shadow-sm"
                >
                  {isSaving ? 'Updating...' : 'Assign POC Group'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
