'use client';

/**
 * Universal Selector Component - Paradox Sports OMS (Phase 10E)
 * 
 * Canonical reusable selector for:
 * - USER: Single user select (returns user UUID)
 * - MULTI_USER: Multiple user select (returns user UUID[])
 * - VERTICAL: Vertical division select (returns vertical UUID)
 * - ROLE: Role select (returns canonical role string)
 * - ROLE_IN_VERTICAL: Role + Vertical combination select
 * - EVENT_TEAM: Designated Event Team account select (returns user UUID)
 * - AUDIENCE: Multi-scope audience selector (Organization, Vertical, Role, Users, Event Team)
 *
 * Backed by server-side query endpoint `GET /api/v1/organization/selector-options`
 * Features:
 * - 300ms debounced search on username, full name, email, role, and vertical
 * - Stale request rejection via incremental request IDs
 * - Visual badges, sublabels, and keyboard navigation
 * - Downward hierarchy and vertical isolation when usage="assignment"
 */

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Search, ChevronDown, Check, X, Loader2, Users, Building2, Shield, User, Globe } from 'lucide-react';
import { organizationApi } from '@/lib/api';
import { SelectorOptionItem } from '@/types/organization';
import { cn } from '@/lib/utils';

export type UniversalSelectorMode =
  | 'USER'
  | 'MULTI_USER'
  | 'VERTICAL'
  | 'ROLE'
  | 'ROLE_IN_VERTICAL'
  | 'EVENT_TEAM'
  | 'AUDIENCE';

export interface AudienceSelectionValue {
  scope: 'ALL' | 'VERTICAL' | 'ROLE' | 'ROLE_IN_VERTICAL' | 'USER' | 'EVENT_TEAM';
  vertical_id?: string;
  role?: string;
  user_ids?: string[];
  user_id?: string;
}

export interface UniversalSelectorProps {
  mode: UniversalSelectorMode;
  value?: string | string[] | AudienceSelectionValue;
  onChange?: (value: any, selectedItem?: SelectorOptionItem | SelectorOptionItem[]) => void;
  label?: string;
  description?: string;
  placeholder?: string;
  searchPlaceholder?: string;
  usage?: 'assignment' | 'audience' | 'general';
  verticalId?: string;
  roleFilter?: string;
  disabled?: boolean;
  required?: boolean;
  error?: string;
  helperText?: string;
  className?: string;
  id?: string;
}

export const UniversalSelector: React.FC<UniversalSelectorProps> = ({
  mode,
  value,
  onChange,
  label,
  placeholder,
  searchPlaceholder = 'Search by name, username, email...',
  usage = 'general',
  verticalId,
  roleFilter,
  disabled = false,
  required = false,
  error,
  helperText,
  className,
  id,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [options, setOptions] = useState<SelectorOptionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const [selectedItems, setSelectedItems] = useState<SelectorOptionItem[]>([]);
  const [audienceScope, setAudienceScope] = useState<AudienceSelectionValue['scope']>('VERTICAL');

  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);
  const reqIdRef = useRef<number>(0);

  const [rect, setRect] = useState<DOMRect | null>(null);
  const [openUpward, setOpenUpward] = useState<boolean>(false);

  // Default placeholder resolution
  const resolvedPlaceholder = useMemo(() => {
    if (placeholder) return placeholder;
    switch (mode) {
      case 'USER':
        return 'Select a member...';
      case 'MULTI_USER':
        return 'Select members...';
      case 'VERTICAL':
        return 'Select a vertical division...';
      case 'ROLE':
        return 'Select a role...';
      case 'EVENT_TEAM':
        return 'Select Event Team account...';
      case 'AUDIENCE':
        return 'Configure target audience...';
      default:
        return 'Select...';
    }
  }, [placeholder, mode]);

  // Debounce search input (300ms)
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchTerm);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Position calculation
  const updatePosition = useCallback(() => {
    if (containerRef.current) {
      const currentRect = containerRef.current.getBoundingClientRect();
      setRect(currentRect);
      const spaceBelow = window.innerHeight - currentRect.bottom;
      const spaceAbove = currentRect.top;
      setOpenUpward(spaceBelow < 280 && spaceAbove > 200);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      updatePosition();
      window.addEventListener('scroll', updatePosition, true);
      window.addEventListener('resize', updatePosition);
      return () => {
        window.removeEventListener('scroll', updatePosition, true);
        window.removeEventListener('resize', updatePosition);
      };
    }
  }, [isOpen, updatePosition]);

  // Fetch options from backend
  const fetchOptions = useCallback(
    async (query: string) => {
      const currentReqId = ++reqIdRef.current;
      setLoading(true);
      setFetchError(null);

      try {
        let queryType: string = mode;
        if (mode === 'AUDIENCE') {
          if (audienceScope === 'ALL') queryType = 'ALL_USERS';
          else if (audienceScope === 'VERTICAL') queryType = 'VERTICAL';
          else if (audienceScope === 'ROLE') queryType = 'ROLE';
          else if (audienceScope === 'EVENT_TEAM') queryType = 'EVENT_TEAM';
          else queryType = 'USER';
        } else if (mode === 'MULTI_USER') {
          queryType = 'USER';
        }

        const res = await organizationApi.getSelectorOptions({
          selection_type: queryType,
          search: query || undefined,
          vertical_id: verticalId,
          role_filter: roleFilter,
          usage,
          limit: 100,
        });

        if (currentReqId === reqIdRef.current) {
          setOptions(res.items || []);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (currentReqId === reqIdRef.current) {
          const msg = err instanceof Error ? err.message : 'Unable to load options. Please try again.';
          setFetchError(msg);
          setLoading(false);
        }
      }
    },
    [mode, audienceScope, verticalId, roleFilter, usage]
  );

  useEffect(() => {
    if (isOpen) {
      fetchOptions(debouncedSearch);
    }
  }, [isOpen, debouncedSearch, fetchOptions]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;

    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex((prev) => (prev < options.length - 1 ? prev + 1 : 0));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex((prev) => (prev > 0 ? prev - 1 : options.length - 1));
        break;
      case 'Enter':
        e.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < options.length) {
          handleSelect(options[focusedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        break;
    }
  };

  // Scroll focused option into view
  useEffect(() => {
    if (isOpen && focusedIndex >= 0 && listboxRef.current) {
      const items = listboxRef.current.querySelectorAll('li[role="option"]');
      if (items[focusedIndex]) {
        items[focusedIndex].scrollIntoView({ block: 'nearest' });
      }
    }
  }, [focusedIndex, isOpen]);

  // Option selection handler
  const handleSelect = (item: SelectorOptionItem) => {
    if (mode === 'MULTI_USER') {
      const currentValues = Array.isArray(value) ? [...value] : [];
      const index = currentValues.indexOf(item.id);
      let newValues: string[];
      let newSelected: SelectorOptionItem[];

      if (index >= 0) {
        newValues = currentValues.filter((id) => id !== item.id);
        newSelected = selectedItems.filter((i) => i.id !== item.id);
      } else {
        newValues = [...currentValues, item.id];
        newSelected = [...selectedItems, item];
      }
      setSelectedItems(newSelected);
      onChange?.(newValues, newSelected);
    } else if (mode === 'AUDIENCE') {
      const audVal: AudienceSelectionValue = {
        scope: audienceScope,
      };
      if (audienceScope === 'VERTICAL') audVal.vertical_id = item.id;
      else if (audienceScope === 'ROLE') audVal.role = item.id;
      else if (audienceScope === 'USER') {
        audVal.user_id = item.id;
        audVal.user_ids = [item.id];
      } else if (audienceScope === 'EVENT_TEAM') audVal.user_id = item.id;

      setSelectedItems([item]);
      onChange?.(audVal, item);
      setIsOpen(false);
    } else {
      setSelectedItems([item]);
      onChange?.(item.id, item);
      setIsOpen(false);
    }
  };

  const removeMultiItem = (idToRemove: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const currentValues = Array.isArray(value) ? value : [];
    const newValues = currentValues.filter((id) => id !== idToRemove);
    const newSelected = selectedItems.filter((i) => i.id !== idToRemove);
    setSelectedItems(newSelected);
    onChange?.(newValues, newSelected);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedItems([]);
    if (mode === 'MULTI_USER') {
      onChange?.([]);
    } else if (mode === 'AUDIENCE') {
      onChange?.({ scope: 'VERTICAL' });
    } else {
      onChange?.('');
    }
  };

  // Find label for single value display
  const singleLabel = useMemo(() => {
    if (typeof value === 'string' && value) {
      const found = selectedItems.find((i) => i.id === value) || options.find((i) => i.id === value);
      if (found) return found.label;
      return value;
    }
    if (mode === 'AUDIENCE' && typeof value === 'object' && value !== null) {
      const aud = value as AudienceSelectionValue;
      if (aud.scope === 'ALL') return 'Entire Organization (All Members)';
      const targetId = aud.vertical_id || aud.role || aud.user_id;
      const found = selectedItems.find((i) => i.id === targetId) || options.find((i) => i.id === targetId);
      if (found) return `${aud.scope}: ${found.label}`;
      return `Audience: ${aud.scope}`;
    }
    return null;
  }, [value, selectedItems, options, mode]);

  // Dropdown portal rendering
  const dropdownContent = isOpen && rect && (
    <div
      ref={dropdownRef}
      style={(() => {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const targetWidth = Math.min(Math.max(rect.width, 260), viewportWidth - 24);
        let left = rect.left;
        if (left + targetWidth > viewportWidth - 12) {
          left = Math.max(12, viewportWidth - targetWidth - 12);
        }
        if (left < 12) left = 12;

        const spaceBelow = viewportHeight - rect.bottom;
        const spaceAbove = rect.top;
        const maxHeight = Math.min(openUpward ? spaceAbove - 16 : spaceBelow - 16, 380);

        return {
          position: 'fixed' as const,
          left: `${left}px`,
          width: `${targetWidth}px`,
          top: openUpward ? 'auto' : `${rect.bottom + 4}px`,
          bottom: openUpward ? `${viewportHeight - rect.top + 4}px` : 'auto',
          maxHeight: `${Math.max(maxHeight, 180)}px`,
          zIndex: 99999,
        };
      })()}
      className="flex flex-col rounded-xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-900 animate-in fade-in zoom-in-95 duration-100"
    >
      {/* Audience Scope Switcher */}
      {mode === 'AUDIENCE' && (
        <div className="flex border-b border-zinc-100 bg-zinc-50/75 p-1.5 dark:border-zinc-800 dark:bg-zinc-900/75">
          {(['VERTICAL', 'ALL', 'ROLE', 'USER', 'EVENT_TEAM'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setAudienceScope(s);
                setSearchTerm('');
              }}
              className={cn(
                'flex-1 rounded-lg py-1 text-xs font-semibold transition-colors',
                audienceScope === s
                  ? 'bg-white text-amber-600 shadow-sm dark:bg-zinc-800 dark:text-amber-400'
                  : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white'
              )}
            >
              {s === 'ALL' ? 'Everyone' : s.replace('_', ' ')}
            </button>
          ))}
        </div>
      )}

      {/* Search Input Bar */}
      <div className="relative border-b border-zinc-100 p-2 dark:border-zinc-800">
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
        <input
          ref={searchInputRef}
          type="text"
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setFocusedIndex(0);
          }}
          placeholder={searchPlaceholder}
          className="w-full rounded-lg bg-zinc-50 py-2 pl-9 pr-8 text-xs text-zinc-900 placeholder:text-zinc-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500/20 dark:bg-zinc-800 dark:text-white dark:focus:bg-zinc-950"
          autoFocus
        />
        {searchTerm && (
          <button
            type="button"
            onClick={() => setSearchTerm('')}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Options Listbox */}
      <ul
        ref={listboxRef}
        role="listbox"
        className="flex-1 overflow-y-auto p-1.5 focus:outline-none max-h-56"
      >
        {loading && options.length === 0 ? (
          <li className="flex items-center justify-center gap-2 py-6 text-xs text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
            Loading targets...
          </li>
        ) : fetchError ? (
          <li className="p-4 text-center text-xs text-rose-600 dark:text-rose-400">
            {fetchError}
          </li>
        ) : options.length === 0 ? (
          <li className="p-4 text-center text-xs text-slate-500 dark:text-slate-400">
            No matching targets found
          </li>
        ) : (
          options.map((option, index) => {
            const isSelected =
              mode === 'MULTI_USER'
                ? Array.isArray(value) && value.includes(option.id)
                : typeof value === 'string'
                ? value === option.id
                : mode === 'AUDIENCE' && typeof value === 'object' && value !== null
                ? (value as AudienceSelectionValue).vertical_id === option.id ||
                  (value as AudienceSelectionValue).role === option.id ||
                  (value as AudienceSelectionValue).user_id === option.id ||
                  ((value as AudienceSelectionValue).scope === 'ALL' && option.id === 'ALL')
                : false;

            const isFocused = focusedIndex === index;

            return (
              <li
                key={option.id}
                role="option"
                aria-selected={isSelected}
                onClick={() => handleSelect(option)}
                className={cn(
                  'flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-xs transition-colors',
                  isFocused ? 'bg-zinc-100 dark:bg-zinc-800' : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/60',
                  isSelected && 'bg-amber-500/10 font-medium text-amber-900 dark:bg-amber-500/15 dark:text-amber-200'
                )}
              >
                <div className="flex flex-col gap-0.5 truncate pr-2">
                  <div className="flex items-center gap-2 truncate">
                    <span className="truncate font-semibold text-zinc-900 dark:text-zinc-100">
                      {option.label}
                    </span>
                    {option.badge && (
                      <span className="rounded-full bg-zinc-100 px-1.5 py-0.5 text-[10px] font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                        {option.badge}
                      </span>
                    )}
                  </div>
                  {option.sublabel && (
                    <span className="truncate text-[11px] text-zinc-500 dark:text-zinc-400">
                      {option.sublabel}
                    </span>
                  )}
                </div>

                {isSelected && (
                  <Check className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                )}
              </li>
            );
          })
        )}
      </ul>
    </div>
  );

  return (
    <div className={cn('relative flex flex-col gap-1.5', className)} ref={containerRef}>
      {label && (
        <label
          htmlFor={id}
          className="text-xs font-semibold text-zinc-700 dark:text-zinc-300"
        >
          {label} {required ? <span className="text-rose-500">*</span> : <span className="text-zinc-400 font-normal">(Optional)</span>}
        </label>
      )}

      {/* Main Trigger Button */}
      <div
        id={id}
        tabIndex={disabled ? -1 : 0}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        role="combobox"
        aria-expanded={isOpen}
        className={cn(
          'flex min-h-[42px] cursor-pointer items-center justify-between gap-2 rounded-xl border bg-white px-3.5 py-2 text-xs text-zinc-900 shadow-sm transition-all focus:outline-none dark:bg-zinc-900 dark:text-zinc-100',
          disabled && 'cursor-not-allowed opacity-50 bg-zinc-50 dark:bg-zinc-800/40',
          error
            ? 'border-rose-300 focus:ring-2 focus:ring-rose-500/20 dark:border-rose-800'
            : isOpen
            ? 'border-amber-500 ring-2 ring-amber-500/20 dark:border-amber-500'
            : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700'
        )}
      >
        <div className="flex flex-1 flex-wrap items-center gap-1.5 truncate">
          {mode === 'MULTI_USER' && Array.isArray(value) && value.length > 0 ? (
            value.map((uid) => {
              const item = selectedItems.find((i) => i.id === uid);
              return (
                <span
                  key={uid}
                  className="inline-flex items-center gap-1 rounded-md bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-500/15 dark:text-amber-300 border border-amber-500/20"
                >
                  {item ? item.label : uid.slice(0, 8)}
                  <button
                    type="button"
                    onClick={(e) => removeMultiItem(uid, e)}
                    className="text-amber-400 hover:text-amber-700 dark:hover:text-amber-200"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              );
            })
          ) : singleLabel ? (
            <span className="truncate font-medium text-zinc-900 dark:text-zinc-100">
              {singleLabel}
            </span>
          ) : (
            <span className="text-zinc-400 dark:text-zinc-500">
              {resolvedPlaceholder}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {((typeof value === 'string' && value) || (Array.isArray(value) && value.length > 0)) && !disabled && (
            <button
              type="button"
              onClick={handleClear}
              className="p-0.5 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
              title="Clear selection"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <ChevronDown
            className={cn(
              'h-4 w-4 text-zinc-400 transition-transform duration-200',
              isOpen && 'rotate-180 text-amber-500'
            )}
          />
        </div>
      </div>

      {error && (
        <p className="text-[11px] font-medium text-rose-500 dark:text-rose-400">{error}</p>
      )}
      {helperText && !error && (
        <p className="text-[11px] text-zinc-400 dark:text-zinc-500">{helperText}</p>
      )}

      {typeof document !== 'undefined' && createPortal(dropdownContent, document.body)}
    </div>
  );
};
