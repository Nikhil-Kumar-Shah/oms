'use client';

/**
 * Reusable SmartSelect / SearchableSelect Component
 * Features:
 * - Server-side debounced search (300ms) with stale request prevention
 * - Preloaded options support for smaller searchable datasets
 * - Keyboard navigation (ArrowUp, ArrowDown, Enter, Escape)
 * - Clear selection button
 * - Subtitle / metadata badge rendering in options
 * - Fully accessible ARIA attributes
 * - Dark mode & Mobile responsive touch targets
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Search, ChevronDown, Check, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SmartSelectOption {
  value: string;
  label: string;
  sublabel?: string;
  badge?: string;
  disabled?: boolean;
}

export interface SmartSelectProps {
  label?: string;
  value?: string;
  onChange: (value: string, selectedOption?: SmartSelectOption) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  fetchOptions?: (query: string) => Promise<SmartSelectOption[]>;
  options?: SmartSelectOption[];
  disabled?: boolean;
  error?: string;
  helperText?: string;
  required?: boolean;
  className?: string;
  renderOption?: (option: SmartSelectOption) => React.ReactNode;
  id?: string;
}

export const SmartSelect: React.FC<SmartSelectProps> = ({
  label,
  value,
  onChange,
  placeholder = 'Select an option...',
  searchPlaceholder = 'Type to search...',
  fetchOptions,
  options: staticOptions,
  disabled = false,
  error,
  helperText,
  required = false,
  className,
  renderOption,
  id,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [asyncOptions, setAsyncOptions] = useState<SmartSelectOption[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const [openUpward, setOpenUpward] = useState<boolean>(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);
  const searchReqIdRef = useRef<number>(0);

  const [rect, setRect] = useState<DOMRect | null>(null);

  const updatePosition = () => {
    if (containerRef.current) {
      const currentRect = containerRef.current.getBoundingClientRect();
      setRect(currentRect);
      const spaceBelow = window.innerHeight - currentRect.bottom;
      const spaceAbove = currentRect.top;
      if (spaceBelow < 280 && spaceAbove > 200) {
        setOpenUpward(true);
      } else {
        setOpenUpward(false);
      }
    }
  };

  // Position calculation: flip upward if near viewport or container bottom
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
  }, [isOpen]);

  // Debounce search query (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Load async options when fetchOptions is provided
  useEffect(() => {
    let isSubscribed = true;

    if (isOpen && fetchOptions) {
      const reqId = ++searchReqIdRef.current;
      
      // Async trigger for loading indicator
      Promise.resolve().then(() => {
        if (isSubscribed && reqId === searchReqIdRef.current) {
          setLoading(true);
        }
      });

      fetchOptions(debouncedSearch)
        .then((results) => {
          if (isSubscribed && reqId === searchReqIdRef.current) {
            setAsyncOptions(results || []);
          }
        })
        .catch((err) => {
          console.error('SmartSelect fetchOptions error:', err);
          if (isSubscribed && reqId === searchReqIdRef.current) {
            setAsyncOptions([]);
          }
        })
        .finally(() => {
          if (isSubscribed && reqId === searchReqIdRef.current) {
            setLoading(false);
          }
        });
    }

    return () => {
      isSubscribed = false;
    };
  }, [isOpen, debouncedSearch, fetchOptions]);

  // Compute displayed options
  const options = useMemo(() => {
    if (fetchOptions) {
      return asyncOptions;
    }
    if (!staticOptions) {
      return [];
    }
    if (!searchTerm.trim()) {
      return staticOptions;
    }
    const q = searchTerm.toLowerCase();
    return staticOptions.filter(
      (opt) =>
        opt.label.toLowerCase().includes(q) ||
        (opt.sublabel && opt.sublabel.toLowerCase().includes(q))
    );
  }, [fetchOptions, asyncOptions, staticOptions, searchTerm]);

  // Close dropdown on outside click (check both container and portal dropdown)
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(target)
      ) {
        setIsOpen(false);
        setSearchTerm('');
        setFocusedIndex(-1);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isOpen]);

  // Focus search input when popover opens
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen]);

  // Selected Option resolver
  const selectedOption =
    options.find((o) => o.value === value) ||
    (staticOptions ? staticOptions.find((o) => o.value === value) : undefined);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;

    if (!isOpen) {
      if (e.key === 'Enter' || e.key === 'ArrowDown' || e.key === ' ') {
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
          const opt = options[focusedIndex];
          if (!opt.disabled) {
            onChange(opt.value, opt);
            setIsOpen(false);
            setSearchTerm('');
            setFocusedIndex(-1);
          }
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        setSearchTerm('');
        setFocusedIndex(-1);
        break;
    }
  };

  const handleSelect = (opt: SmartSelectOption) => {
    if (opt.disabled) return;
    onChange(opt.value, opt);
    setIsOpen(false);
    setSearchTerm('');
    setFocusedIndex(-1);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange('', undefined);
  };

  return (
    <div className={cn('relative w-full space-y-1.5', className)} ref={containerRef}>
      {label && (
        <label
          htmlFor={id}
          className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300"
        >
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}

      {/* Main Trigger Button */}
      <button
        id={id}
        type="button"
        disabled={disabled}
        onClick={() => {
          updatePosition();
          setIsOpen((prev) => {
            if (prev) {
              setSearchTerm('');
              setFocusedIndex(-1);
            }
            return !prev;
          });
        }}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className={cn(
          'w-full flex items-center justify-between px-3.5 py-2 text-left text-sm rounded-xl border bg-white dark:bg-zinc-900 shadow-xs transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500',
          error
            ? 'border-rose-400 dark:border-rose-600 ring-1 ring-rose-400'
            : 'border-zinc-300 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-700',
          disabled && 'opacity-60 cursor-not-allowed bg-zinc-100 dark:bg-zinc-800'
        )}
      >
        <div className="flex-1 truncate mr-2">
          {selectedOption ? (
            <div className="flex items-center gap-2">
              <span className="font-medium text-zinc-900 dark:text-zinc-100 truncate">
                {selectedOption.label}
              </span>
              {selectedOption.badge && (
                <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded-md bg-amber-500/10 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/25">
                  {selectedOption.badge}
                </span>
              )}
            </div>
          ) : (
            <span className="text-zinc-400 dark:text-zinc-500">{placeholder}</span>
          )}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {value && !disabled && (
            <span
              role="button"
              tabIndex={0}
              onClick={handleClear}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  e.stopPropagation();
                  onChange('', undefined);
                }
              }}
              className="p-0.5 rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 cursor-pointer inline-flex items-center justify-center"
              aria-label="Clear selection"
            >
              <X className="w-3.5 h-3.5" />
            </span>
          )}
          <ChevronDown
            className={cn(
              'w-4 h-4 text-zinc-400 transition-transform duration-200',
              isOpen && 'rotate-180'
            )}
          />
        </div>
      </button>

      {/* Dropdown Popover */}
      {isOpen && typeof document !== 'undefined' && rect && createPortal(
        <div
          ref={dropdownRef}
          className={cn(
            'fixed z-[99999] rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden animate-in fade-in-0 zoom-in-95 duration-100 flex flex-col',
            openUpward ? 'mb-1' : 'mt-1'
          )}
          style={(() => {
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            const targetWidth = Math.min(Math.max(rect.width, 240), viewportWidth - 24);
            let left = rect.left;
            if (left + targetWidth > viewportWidth - 12) {
              left = Math.max(12, viewportWidth - targetWidth - 12);
            }
            if (left < 12) left = 12;

            const spaceBelow = viewportHeight - rect.bottom;
            const spaceAbove = rect.top;
            const maxHeight = Math.min(openUpward ? spaceAbove - 16 : spaceBelow - 16, 360);

            return {
              width: `${targetWidth}px`,
              maxHeight: `${Math.max(maxHeight, 180)}px`,
              top: openUpward ? undefined : `${rect.bottom + 4}px`,
              bottom: openUpward ? `${viewportHeight - rect.top + 4}px` : undefined,
              left: `${left}px`,
            };
          })()}
        >
          {/* Search Input Filter */}
          <div className="p-2 border-b border-zinc-100 dark:border-zinc-800 flex items-center gap-2 bg-zinc-50/50 dark:bg-zinc-900/50">
            <Search className="w-3.5 h-3.5 text-zinc-400 shrink-0 ml-1" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={searchPlaceholder}
              className="w-full bg-transparent text-xs text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none"
            />
            {loading && <Loader2 className="w-3.5 h-3.5 text-amber-500 animate-spin shrink-0" />}
          </div>

          {/* Options List */}
          <ul
            ref={listboxRef}
            role="listbox"
            tabIndex={-1}
            className="max-h-60 overflow-y-auto p-1.5 space-y-0.5 text-xs divide-y divide-zinc-50 dark:divide-zinc-800/40"
          >
            {loading && options.length === 0 && (
              <li className="p-4 text-center text-zinc-400 dark:text-zinc-500 flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                <span>Searching records...</span>
              </li>
            )}

            {!loading && options.length === 0 && (
              <li className="p-4 text-center text-zinc-400 dark:text-zinc-500">
                No matching results found
              </li>
            )}

            {options.map((option, idx) => {
              const isSelected = option.value === value;
              const isFocused = idx === focusedIndex;

              return (
                <li
                  key={option.value}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => handleSelect(option)}
                  onMouseEnter={() => setFocusedIndex(idx)}
                  className={cn(
                    'p-2 rounded-lg cursor-pointer flex items-center justify-between transition-colors',
                    isSelected
                      ? 'bg-amber-500/10 dark:bg-amber-500/15 text-amber-800 dark:text-amber-200 font-medium'
                      : isFocused
                      ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100'
                      : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800/60',
                    option.disabled && 'opacity-40 cursor-not-allowed'
                  )}
                >
                  <div className="flex-1 min-w-0 mr-2">
                    {renderOption ? (
                      renderOption(option)
                    ) : (
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-xs truncate">{option.label}</span>
                          {option.badge && (
                            <span className="px-1.5 py-0.2 text-[9px] font-bold rounded bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300">
                              {option.badge}
                            </span>
                          )}
                        </div>
                        {option.sublabel && (
                          <p className="text-[11px] text-zinc-500 dark:text-zinc-400 truncate">
                            {option.sublabel}
                          </p>
                        )}
                      </div>
                    )}
                  </div>

                  {isSelected && <Check className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />}
                </li>
              );
            })}
          </ul>
        </div>,
        document.body
      )}

      {error && <p className="text-xs text-red-500 font-medium">{error}</p>}
      {helperText && !error && <p className="text-xs text-zinc-500 dark:text-zinc-400">{helperText}</p>}
    </div>
  );
};
