'use client';

/**
 * Universal Audience Selector Component (Phase 10E / Event Module Canonical)
 * Unified selector supporting hierarchical selection:
 * - Vertical Division (mode="VERTICAL")
 * - Specific Individual Users (mode="USER") with Vertical → Role → Users grouping & filter drilldown
 * - Audience Groups (Entire Org, Entire Vertical, Role Group, Role+Vertical, Event Team)
 * - Single or Multi selection mode
 *
 * Enforces:
 * - Server-side query via GET /api/v1/organization/selector-options
 * - Clean UI with actual labels, role badges, usernames (never raw UUIDs)
 * - Role-based grouping: Vertical → Role → Users
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import {
  Search,
  Check,
  X,
  ChevronDown,
  Users,
  User,
  Shield,
  Layers,
  Flag,
  Globe,
  Loader2,
  AlertCircle,
  FolderTree,
  Filter,
} from 'lucide-react';
import { organizationApi } from '@/lib/api';
import { SelectorOptionItem, SelectorGroupItem, UniversalAudienceSelection, Vertical } from '@/types/organization';

export interface AudienceItem {
  id: string; // e.g. "ALL", "VERTICAL:<id>", "ROLE:<code>", "ROLE_VERTICAL:<vid>:<role>", "USER:<id>", "EVENT_TEAM:<id>"
  type: 'ALL' | 'VERTICAL' | 'ROLE' | 'ROLE_VERTICAL' | 'USER' | 'EVENT_TEAM';
  rawId: string; // Raw UUID or Role Code
  label: string;
  sublabel?: string;
  badge?: string;
  memberCount?: number;
  metadata?: Record<string, any>;
}

export type SelectorDisplayMode = 'multi' | 'single' | 'VERTICAL' | 'USER' | 'EVENT_TEAM';

export interface UniversalAudienceSelectorProps {
  label?: string;
  description?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  usage?: 'assignment' | 'audience' | 'general';
  mode?: SelectorDisplayMode;
  selectionMode?: 'single' | 'multi';
  multi?: boolean;
  allowAllUsers?: boolean;
  allowVerticals?: boolean;
  allowRoles?: boolean;
  allowIndividualUsers?: boolean;
  allowEventTeams?: boolean;
  showResolvedPreview?: boolean;
  allowedScopes?: Array<'ALL' | 'VERTICAL' | 'ROLE' | 'ROLE_VERTICAL' | 'USER' | 'EVENT_TEAM'>;
  verticalId?: string;
  eventId?: string;
  value?: AudienceItem[] | string | string[];
  onChange?: (
    items: AudienceItem[],
    structuredValue: UniversalAudienceSelection,
    rawIdOrIds?: string | string[]
  ) => void;
  className?: string;
}

const CANONICAL_ROLES = [
  { code: 'ALL', label: 'All Roles' },
  { code: 'SPORTS_CORE', label: 'Sports Core' },
  { code: 'DEPUTY_CORE', label: 'Deputy Core' },
  { code: 'SUPER_COORDINATOR', label: 'Super Coord' },
  { code: 'COORDINATOR', label: 'Coordinator' },
  { code: 'VOLUNTEER', label: 'Volunteer' },
  { code: 'EVENT_TEAM', label: 'Event Team' },
];

export const UniversalAudienceSelector: React.FC<UniversalAudienceSelectorProps> = ({
  label,
  description,
  placeholder,
  required = false,
  disabled = false,
  usage = 'general',
  mode = 'multi',
  selectionMode,
  multi,
  allowAllUsers,
  allowVerticals,
  allowRoles,
  allowIndividualUsers,
  allowEventTeams = false,
  showResolvedPreview,
  allowedScopes,
  verticalId,
  eventId,
  value,
  onChange,
  className = '',
}) => {
  // Mode resolutions
  const isVerticalMode = mode === 'VERTICAL';
  const isUserMode = mode === 'USER';
  const isEventTeamMode = mode === 'EVENT_TEAM';

  // Single vs Multi determination
  const isSingle = useMemo(() => {
    if (selectionMode === 'single') return true;
    if (selectionMode === 'multi') return false;
    if (multi === true) return false;
    if (multi === false) return true;
    if (mode === 'single') return true;
    if (mode === 'multi') return false;
    if (isVerticalMode || isUserMode || isEventTeamMode) return true; // Default single for VERTICAL, USER, and EVENT_TEAM unless multi is explicitly passed
    return false;
  }, [selectionMode, multi, mode, isVerticalMode, isUserMode, isEventTeamMode]);

  // Derived capability flags
  const effAllowAll = isVerticalMode || isUserMode || isEventTeamMode ? false : allowAllUsers ?? true;
  const effAllowVerticals = isVerticalMode ? true : isUserMode || isEventTeamMode ? false : allowVerticals ?? true;
  const effAllowRoles = isVerticalMode || isUserMode || isEventTeamMode ? false : allowRoles ?? true;
  const effAllowUsers = isVerticalMode || isEventTeamMode ? false : isUserMode ? true : allowIndividualUsers ?? true;
  const effShowPreview = showResolvedPreview !== undefined ? showResolvedPreview : !isVerticalMode && !isUserMode && !isEventTeamMode;

  const defaultPlaceholder = isVerticalMode
    ? 'Select Vertical Division...'
    : isEventTeamMode
    ? 'Select Associated Event Team Account...'
    : isUserMode
    ? isSingle
      ? 'Select Platform User...'
      : 'Select Users...'
    : 'Select audience groups, verticals, roles, or users...';

  const effPlaceholder = placeholder || defaultPlaceholder;

  // Dropdown UI state
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'GROUPS' | 'USERS'>(isUserMode || isEventTeamMode ? 'USERS' : 'GROUPS');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');
  const [verticalFilter, setVerticalFilter] = useState<string>(verticalId || 'ALL');

  // Keep verticalFilter in sync with verticalId prop when parent updates selection
  useEffect(() => {
    if (verticalId) {
      setVerticalFilter(verticalId);
    } else {
      setVerticalFilter('ALL');
    }
  }, [verticalId]);

  // Available verticals for filter dropdown
  const [availableVerticals, setAvailableVerticals] = useState<Array<{ id: string; name: string }>>([]);

  // Normalized internal items state
  const [internalItems, setInternalItems] = useState<AudienceItem[]>([]);

  // Async data states
  const [groupOptions, setGroupOptions] = useState<AudienceItem[]>([]);
  const [userOptions, setUserOptions] = useState<AudienceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Position & DOM refs
  const triggerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const reqIdRef = useRef(0);
  const allGroupsCacheRef = useRef<AudienceItem[] | null>(null);
  const [dropdownPosition, setDropdownPosition] = useState<{
    top?: number;
    bottom?: number;
    left: number;
    width: number;
    maxHeight: number;
    openUpward: boolean;
  }>({
    top: 0,
    left: 0,
    width: 320,
    maxHeight: 380,
    openUpward: false,
  });

  // Keep internal items in sync with prop value
  useEffect(() => {
    if (!value) {
      setInternalItems([]);
      return;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        setInternalItems([]);
        return;
      }
      if (typeof value[0] === 'object' && 'rawId' in value[0]) {
        setInternalItems(value as AudienceItem[]);
        return;
      }
      // Array of string IDs
      const rawIds = value as string[];
      setInternalItems((prev) => {
        return rawIds.map((rid) => {
          const existing = prev.find((p) => p.rawId === rid);
          if (existing) return existing;
          const foundInOpts = [...groupOptions, ...userOptions].find((o) => o.rawId === rid);
          if (foundInOpts) return foundInOpts;
          return {
            id: `${isVerticalMode ? 'VERTICAL' : isEventTeamMode ? 'EVENT_TEAM' : 'USER'}:${rid}`,
            type: isVerticalMode ? 'VERTICAL' : isEventTeamMode ? 'EVENT_TEAM' : 'USER',
            rawId: rid,
            label: rid.length > 12 ? `${rid.slice(0, 8)}...` : rid,
          };
        });
      });
      return;
    }

    if (typeof value === 'string') {
      if (!value.trim()) {
        setInternalItems([]);
        return;
      }
      const rawId = value.trim();
      setInternalItems((prev) => {
        const existing = prev.find((p) => p.rawId === rawId);
        if (existing) return [existing];
        const foundInOpts = [...groupOptions, ...userOptions].find((o) => o.rawId === rawId);
        if (foundInOpts) return [foundInOpts];
        return [
          {
            id: `${isVerticalMode ? 'VERTICAL' : isEventTeamMode ? 'EVENT_TEAM' : 'USER'}:${rawId}`,
            type: isVerticalMode ? 'VERTICAL' : isEventTeamMode ? 'EVENT_TEAM' : 'USER',
            rawId,
            label: rawId.length > 12 ? `${rawId.slice(0, 8)}...` : rawId,
          },
        ];
      });
    }
  }, [value, isVerticalMode, isEventTeamMode, groupOptions, userOptions]);

  // Load verticals for the filter dropdown
  useEffect(() => {
    let ignore = false;
    organizationApi
      .listVerticals()
      .then((res) => {
        if (!ignore && res.items) {
          setAvailableVerticals(res.items.map((v) => ({ id: v.id, name: v.name })));
        }
      })
      .catch(() => {
        // ignore
      });
    return () => {
      ignore = true;
    };
  }, []);

  // Update vertical filter when verticalId prop changes
  useEffect(() => {
    if (verticalId) {
      setVerticalFilter(verticalId);
    }
  }, [verticalId]);

  // Compute effective scopes
  const effectiveScopes = useMemo(() => {
    if (allowedScopes) return allowedScopes;
    if (isVerticalMode) return ['VERTICAL' as const];
    if (isEventTeamMode) return ['EVENT_TEAM' as const];
    if (isUserMode) return ['USER' as const];
    const scopes: Array<'ALL' | 'VERTICAL' | 'ROLE' | 'ROLE_VERTICAL' | 'USER' | 'EVENT_TEAM'> = [];
    if (effAllowAll) scopes.push('ALL');
    if (effAllowVerticals) scopes.push('VERTICAL', 'ROLE_VERTICAL');
    if (effAllowRoles) scopes.push('ROLE');
    if (effAllowUsers) scopes.push('USER');
    if (allowEventTeams) scopes.push('EVENT_TEAM');
    return scopes;
  }, [allowedScopes, isVerticalMode, isEventTeamMode, isUserMode, effAllowAll, effAllowVerticals, effAllowRoles, effAllowUsers, allowEventTeams]);

  // Calculate dropdown positioning
  const updatePosition = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;

      // Horizontal clamping
      const targetWidth = Math.min(Math.max(rect.width, 360), viewportWidth - 24);
      let left = rect.left;
      if (left + targetWidth > viewportWidth - 12) {
        left = Math.max(12, viewportWidth - targetWidth - 12);
      }
      if (left < 12) {
        left = 12;
      }

      // Vertical positioning & flip
      const spaceBelow = viewportHeight - rect.bottom - 12;
      const spaceAbove = rect.top - 12;
      const openUpward = spaceBelow < 300 && spaceAbove > spaceBelow;

      const availableHeight = openUpward ? spaceAbove : spaceBelow;
      const maxHeight = Math.min(Math.max(availableHeight, 200), 450);

      setDropdownPosition({
        top: openUpward ? undefined : rect.bottom + 6,
        bottom: openUpward ? viewportHeight - rect.top + 6 : undefined,
        left,
        width: targetWidth,
        maxHeight,
        openUpward,
      });
    }
  }, []);

  // Invalidate group cache when scope or vertical filters change
  useEffect(() => {
    allGroupsCacheRef.current = null;
  }, [verticalFilter, roleFilter, effectiveScopes]);

  // Fetch options from backend with server-side filtering
  const fetchAudienceData = useCallback(
    async (query: string, tab: 'GROUPS' | 'USERS') => {
      const curReq = ++reqIdRef.current;
      setErrorMsg(null);

      try {
        if (isEventTeamMode) {
          // Fetch Event Team accounts with server search
          setLoading(true);
          const res = await organizationApi.getSelectorOptions({
            selection_type: 'EVENT_TEAM',
            search: query || undefined,
            usage,
            limit: 100,
          });
          if (curReq !== reqIdRef.current) return;

          const teams: AudienceItem[] = (res.items || []).map((it) => ({
            id: `EVENT_TEAM:${it.id}`,
            type: 'EVENT_TEAM',
            rawId: it.id,
            label: it.label,
            sublabel: it.sublabel,
            badge: it.badge || 'EVENT_TEAM',
            metadata: it.metadata,
          }));

          setUserOptions(teams);
          setLoading(false);
          return;
        } else if (tab === 'GROUPS' && !isUserMode) {
          let baseGroups = allGroupsCacheRef.current;

          if (!baseGroups) {
            setLoading(true);
            const promises: Promise<any>[] = [];

            if (effectiveScopes.includes('ALL')) {
              promises.push(
                organizationApi.getSelectorOptions({
                  selection_type: 'ALL_USERS',
                  usage,
                  limit: 1,
                }).catch(() => ({ items: [] }))
              );
            }

            if (effectiveScopes.includes('VERTICAL')) {
              promises.push(
                organizationApi.getSelectorOptions({
                  selection_type: 'VERTICAL',
                  usage,
                  limit: 100,
                }).catch(() => ({ items: [] }))
              );
            }

            if (effectiveScopes.includes('ROLE')) {
              promises.push(
                organizationApi.getSelectorOptions({
                  selection_type: 'ROLE',
                  usage,
                  limit: 100,
                }).catch(() => ({ items: [] }))
              );
            }

            if (effectiveScopes.includes('ROLE_VERTICAL')) {
              promises.push(
                organizationApi.getSelectorOptions({
                  selection_type: 'ROLE_VERTICAL',
                  vertical_id: verticalFilter !== 'ALL' ? verticalFilter : undefined,
                  role_filter: roleFilter !== 'ALL' ? roleFilter : undefined,
                  usage,
                  limit: 100,
                }).catch(() => ({ items: [] }))
              );
            }

            const results = await Promise.all(promises);
            if (curReq !== reqIdRef.current) return;

            const collected: AudienceItem[] = [];
            results.forEach((res) => {
              (res.items || []).forEach((it: SelectorOptionItem) => {
                if (it.id === 'ADMIN' || it.badge === 'ADMIN' || it.metadata?.role === 'ADMIN') {
                  return;
                }
                const normType = it.type === 'ALL_USERS' || it.id === 'ALL' ? 'ALL' : it.type;
                collected.push({
                  id: `${normType}:${it.id}`,
                  type: normType as any,
                  rawId: it.id,
                  label: it.label,
                  sublabel: it.sublabel,
                  badge: it.badge,
                  memberCount: it.member_count,
                  metadata: it.metadata,
                });
              });
            });

            allGroupsCacheRef.current = collected;
            baseGroups = collected;
          }

          const q = (query || '').trim().toLowerCase();
          if (!q) {
            setGroupOptions(baseGroups);
          } else {
            const filtered = baseGroups.filter((it) => {
              const labelMatch = it.label.toLowerCase().includes(q);
              const subMatch = it.sublabel ? it.sublabel.toLowerCase().includes(q) : false;
              const badgeMatch = it.badge ? it.badge.toLowerCase().includes(q) : false;
              return labelMatch || subMatch || badgeMatch;
            });
            setGroupOptions(filtered);
          }
          setLoading(false);
          return;
        } else {
          // Fetch specific users with server search
          setLoading(true);
          const res = await organizationApi.getSelectorOptions({
            selection_type: 'USER',
            search: query || undefined,
            vertical_id: verticalFilter !== 'ALL' ? verticalFilter : (verticalId || undefined),
            role_filter: roleFilter !== 'ALL' ? roleFilter : undefined,
            usage,
            limit: 100,
          });
          if (curReq !== reqIdRef.current) return;

          const users: AudienceItem[] = (res.items || [])
            .filter((it) => it.badge !== 'ADMIN' && it.metadata?.role !== 'ADMIN' && (it.type !== 'ROLE' || it.id !== 'ADMIN'))
            .map((it) => ({
              id: `USER:${it.id}`,
              type: 'USER',
              rawId: it.id,
              label: it.label,
              sublabel: it.sublabel,
              badge: it.badge,
              metadata: it.metadata,
            }));

          setUserOptions(users);
        }
      } catch (err: any) {
        if (curReq === reqIdRef.current) {
          setErrorMsg('Failed to load audience targets');
        }
      } finally {
        if (curReq === reqIdRef.current) {
          setLoading(false);
        }
      }
    },
    [effectiveScopes, usage, verticalFilter, roleFilter, verticalId, isUserMode, isEventTeamMode]
  );

  // Debounce search input
  useEffect(() => {
    if (!isOpen) return;

    if (activeTab === 'GROUPS' && allGroupsCacheRef.current) {
      fetchAudienceData(searchQuery, 'GROUPS');
      return;
    }

    const timer = setTimeout(() => {
      fetchAudienceData(searchQuery, activeTab);
    }, 200);
    return () => clearTimeout(timer);
  }, [searchQuery, activeTab, verticalFilter, roleFilter, isOpen, fetchAudienceData]);

  // Click outside to close
  useEffect(() => {
    if (!isOpen) return;
    updatePosition();

    const handleClickOutside = (e: MouseEvent) => {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    window.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);

    return () => {
      window.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isOpen, updatePosition]);

  // Convert selected audience items to structured output
  const emitChange = (newSelected: AudienceItem[]) => {
    setInternalItems(newSelected);

    const structured: UniversalAudienceSelection = {
      include_all: newSelected.some((it) => it.type === 'ALL' || (it.type as string) === 'ALL_USERS' || it.rawId === 'ALL'),
      vertical_ids: newSelected.filter((it) => it.type === 'VERTICAL').map((it) => it.rawId),
      role_ids: newSelected.filter((it) => it.type === 'ROLE').map((it) => it.rawId),
      role_vertical_pairs: newSelected
        .filter((it) => it.type === 'ROLE_VERTICAL')
        .map((it) => ({
          role: it.metadata?.role || '',
          vertical_id: it.metadata?.vertical_id || '',
          label: it.label,
          member_count: it.memberCount,
        })),
      user_ids: newSelected.filter((it) => it.type === 'USER').map((it) => it.rawId),
      event_team_ids: newSelected.filter((it) => it.type === 'EVENT_TEAM').map((it) => it.rawId),
    };

    const rawOutput = isSingle
      ? (newSelected[0]?.rawId || '')
      : newSelected.map((it) => it.rawId);

    if (onChange) {
      onChange(newSelected, structured, rawOutput);
    }
  };

  const handleToggleItem = (item: AudienceItem) => {
    if (isSingle) {
      emitChange([item]);
      setIsOpen(false);
      return;
    }

    const exists = internalItems.some((v) => v.id === item.id);
    let next: AudienceItem[];
    if (exists) {
      next = internalItems.filter((v) => v.id !== item.id);
    } else {
      next = [...internalItems, item];
    }
    emitChange(next);
  };

  const handleRemoveItem = (e: React.MouseEvent, itemId: string) => {
    e.stopPropagation();
    const next = internalItems.filter((v) => v.id !== itemId);
    emitChange(next);
  };

  const currentOptions = isEventTeamMode
    ? userOptions
    : isUserMode
    ? userOptions
    : activeTab === 'GROUPS'
    ? groupOptions
    : userOptions;

  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
          {label} {required && <span className="text-rose-500 font-bold">*</span>}
        </label>
      )}

      {description && (
        <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{description}</p>
      )}

      {/* Main Trigger Box */}
      <div
        ref={triggerRef}
        onClick={() => {
          if (!disabled) {
            setIsOpen(!isOpen);
            if (!isOpen) {
              setTimeout(() => searchInputRef.current?.focus(), 50);
            }
          }
        }}
        className={`min-h-[42px] w-full px-3 py-1.5 rounded-xl border transition-all cursor-pointer flex flex-wrap items-center gap-1.5 ${
          disabled
            ? 'bg-zinc-100 dark:bg-zinc-800/60 border-zinc-200 dark:border-zinc-800 text-zinc-400 cursor-not-allowed'
            : isOpen
            ? 'bg-white dark:bg-zinc-900 border-amber-500 ring-2 ring-amber-500/20 shadow-sm'
            : 'bg-white dark:bg-zinc-900 border-zinc-300 dark:border-zinc-800 hover:border-zinc-400'
        }`}
      >
        {internalItems.length === 0 ? (
          <span className="text-xs text-zinc-400 select-none">{effPlaceholder}</span>
        ) : (
          internalItems.map((item) => {
            const isGroup = item.type !== 'USER';
            return (
              <span
                key={item.id}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold animate-in fade-in zoom-in-95 duration-100 ${
                  item.type === 'VERTICAL'
                    ? 'bg-emerald-500/10 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/25'
                    : item.type === 'EVENT_TEAM'
                    ? 'bg-amber-500/10 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/25'
                    : isGroup
                    ? 'bg-amber-500/10 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/25'
                    : 'bg-sky-500/10 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-500/25'
                }`}
              >
                {item.type === 'VERTICAL' ? (
                  <FolderTree className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                ) : item.type === 'EVENT_TEAM' ? (
                  <Shield className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                ) : isGroup ? (
                  item.type === 'ALL' ? (
                    <Globe className="w-3.5 h-3.5 text-amber-500" />
                  ) : (
                    <Users className="w-3.5 h-3.5 text-amber-500" />
                  )
                ) : (
                  <User className="w-3.5 h-3.5 text-sky-500" />
                )}

                <span>{item.label}</span>

                {item.sublabel && !isVerticalMode && (
                  <span className="text-[10px] text-zinc-400 font-normal">
                    ({item.sublabel})
                  </span>
                )}

                {item.memberCount !== undefined && item.memberCount !== null && (
                  <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-indigo-200/50 dark:bg-indigo-900/60 font-mono text-indigo-800 dark:text-indigo-200">
                    {item.memberCount}
                  </span>
                )}

                <button
                  type="button"
                  onClick={(e) => handleRemoveItem(e, item.id)}
                  className="hover:text-rose-500 text-zinc-400 p-0.5 rounded-sm"
                  aria-label={`Remove ${item.label}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            );
          })
        )}

        <div className="ml-auto pl-2 flex items-center text-zinc-400">
          <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
        </div>
      </div>

      {/* Portal Dropdown Menu */}
      {isOpen &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            ref={dropdownRef}
            style={{
              position: 'fixed',
              top: dropdownPosition.top !== undefined ? `${dropdownPosition.top}px` : 'auto',
              bottom: dropdownPosition.bottom !== undefined ? `${dropdownPosition.bottom}px` : 'auto',
              left: `${dropdownPosition.left}px`,
              width: `${dropdownPosition.width}px`,
              maxHeight: `${dropdownPosition.maxHeight}px`,
              zIndex: 99999,
            }}
            className="flex flex-col bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-100 text-xs"
          >
            {/* Header: Search + Hierarchical Filters */}
            <div className="p-3 border-b border-zinc-100 dark:border-zinc-800 space-y-2.5 bg-zinc-50/70 dark:bg-zinc-800/40">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-zinc-400" />
                <input
                  ref={searchInputRef}
                  type="text"
                  placeholder={
                    isVerticalMode
                      ? 'Search vertical division by name...'
                      : isEventTeamMode
                      ? 'Search Event Team accounts...'
                      : 'Search by name, username, email...'
                  }
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-hidden focus:ring-2 focus:ring-amber-500/20"
                />
              </div>

              {/* General Scope Tabs (Hidden when forced to VERTICAL, USER, or EVENT_TEAM) */}
              {!isVerticalMode && !isUserMode && !isEventTeamMode && (
                <div className="flex items-center gap-1.5 p-1 bg-zinc-100 dark:bg-zinc-800/80 rounded-xl">
                  <button
                    type="button"
                    onClick={() => setActiveTab('GROUPS')}
                    className={`flex-1 py-1 px-2.5 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                      activeTab === 'GROUPS'
                        ? 'bg-white dark:bg-zinc-900 text-amber-600 dark:text-amber-400 shadow-xs'
                        : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                    }`}
                  >
                    <Users className="w-3.5 h-3.5" />
                    <span>Audience Groups</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('USERS')}
                    className={`flex-1 py-1 px-2.5 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                      activeTab === 'USERS'
                        ? 'bg-white dark:bg-zinc-900 text-sky-600 dark:text-sky-400 shadow-xs'
                        : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                    }`}
                  >
                    <User className="w-3.5 h-3.5" />
                    <span>Individual Users</span>
                  </button>
                </div>
              )}

              {/* HIERARCHICAL DRILLDOWN: Vertical → Role → Users */}
              {(isUserMode || activeTab === 'USERS') && !isEventTeamMode && (
                <div className="space-y-2 pt-1 border-t border-zinc-200/60 dark:border-zinc-800/80">
                  {/* Step 1: Vertical Division Filter (only show when not scoped to fixed verticalId) */}
                  {!verticalId ? (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400 shrink-0 flex items-center gap-1">
                        <FolderTree className="w-3 h-3" />
                        Vertical:
                      </span>
                      <select
                        value={verticalFilter}
                        onChange={(e) => setVerticalFilter(e.target.value)}
                        className="flex-1 py-1 px-2 text-[11px] font-medium rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:ring-1 focus:ring-indigo-500"
                      >
                        <option value="ALL">All Vertical Divisions</option>
                        {availableVerticals.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-amber-500/10 dark:bg-amber-500/15 text-[11px] text-amber-700 dark:text-amber-300 font-medium">
                      <FolderTree className="w-3.5 h-3.5 shrink-0 text-amber-600 dark:text-amber-400" />
                      <span>
                        Filtered to {availableVerticals.find((v) => v.id === verticalId)?.name || 'Selected Division'}
                      </span>
                    </div>
                  )}

                  {/* Step 2: Role Selector Pills */}
                  <div className="space-y-1">
                    <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">
                      Filter by Role:
                    </span>
                    <div className="flex items-center gap-1 flex-wrap">
                      {CANONICAL_ROLES.filter((r) => !isUserMode || r.code !== 'EVENT_TEAM').map((r) => {
                        const isRoleActive = roleFilter === r.code;
                        return (
                          <button
                            key={r.code}
                            type="button"
                            onClick={() => setRoleFilter(r.code)}
                            className={`px-2 py-0.5 rounded-md text-[10px] font-medium transition-all cursor-pointer ${
                              isRoleActive
                                ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-zinc-950 font-bold shadow-xs'
                                : 'bg-zinc-200/80 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-300 dark:hover:bg-zinc-700'
                            }`}
                          >
                            {r.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Scrollable Results List */}
            <div className="max-h-72 overflow-y-auto p-2 space-y-1">
              {loading ? (
                <div className="py-8 flex flex-col items-center justify-center gap-2 text-zinc-400 text-xs">
                  <Loader2 className="w-5 h-5 animate-spin text-amber-500" />
                  <span>Loading options...</span>
                </div>
              ) : errorMsg ? (
                <div className="py-6 px-4 text-center text-rose-500 text-xs flex items-center justify-center gap-1.5">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              ) : currentOptions.length === 0 ? (
                <div className="py-8 text-center text-zinc-400 text-xs">
                  No matching {isVerticalMode ? 'vertical divisions' : isEventTeamMode ? 'Event Team accounts' : 'users or roles'} found.
                </div>
              ) : (
                currentOptions.map((item) => {
                  const isSelected = internalItems.some((v) => v.id === item.id || v.rawId === item.rawId);
                  const isGroup = item.type !== 'USER';

                  return (
                    <div
                      key={item.id}
                      onClick={() => handleToggleItem(item)}
                      className={`p-2.5 rounded-xl cursor-pointer transition-colors flex items-center justify-between gap-3 ${
                        isSelected
                          ? 'bg-amber-500/10 dark:bg-amber-500/15'
                          : 'hover:bg-zinc-100/80 dark:hover:bg-zinc-800/50'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className={`p-1.5 rounded-lg shrink-0 ${
                            item.type === 'VERTICAL'
                              ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-400'
                              : isGroup
                              ? 'bg-amber-100 text-amber-600 dark:bg-amber-950/80 dark:text-amber-400'
                              : 'bg-sky-100 text-sky-600 dark:bg-sky-950/80 dark:text-sky-400'
                          }`}
                        >
                          {item.type === 'VERTICAL' ? (
                            <FolderTree className="w-4 h-4" />
                          ) : item.type === 'ALL' ? (
                            <Globe className="w-4 h-4" />
                          ) : isGroup ? (
                            <Shield className="w-4 h-4" />
                          ) : (
                            <User className="w-4 h-4" />
                          )}
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                              {item.label}
                            </span>
                            {item.badge && (
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 font-mono">
                                {item.badge}
                              </span>
                            )}
                          </div>
                          {item.sublabel && (
                            <p className="text-[10px] text-zinc-400 truncate">{item.sublabel}</p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {item.memberCount !== undefined && item.memberCount !== null && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/20">
                            {item.memberCount} members
                          </span>
                        )}
                        {isSingle ? (
                          <div
                            className={`w-4 h-4 rounded-full border flex items-center justify-center transition-colors ${
                              isSelected
                                ? 'border-amber-500 bg-amber-500 text-zinc-950'
                                : 'border-zinc-300 dark:border-zinc-700'
                            }`}
                          >
                            {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-zinc-950" />}
                          </div>
                        ) : (
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                              isSelected
                                ? 'bg-amber-500 border-amber-500 text-zinc-950'
                                : 'border-zinc-300 dark:border-zinc-700'
                            }`}
                          >
                            {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer Summary */}
            <div className="p-2.5 bg-zinc-50 dark:bg-zinc-800/40 border-t border-zinc-100 dark:border-zinc-800 flex items-center justify-between text-[11px] text-zinc-500">
              <span>{internalItems.length} selected</span>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="px-3 py-1.5 text-xs font-semibold bg-gradient-to-r from-amber-500 to-orange-500 text-zinc-950 rounded-xl hover:from-amber-400 hover:to-orange-400 shadow-xs cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
};
