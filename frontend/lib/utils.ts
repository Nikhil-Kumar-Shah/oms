import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Utility for combining Tailwind and conditional classes safely.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Authoritative datetime formatter for audit logs and system records.
 * Presents timestamps clearly in the user's localized timezone while backing data remains UTC.
 */
export function formatAuditDateTime(dateStr?: string | null, includeSeconds: boolean = false): string {
  if (!dateStr) return 'Timestamp unavailable';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return 'Timestamp unavailable';
    return d.toLocaleString('en-US', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: includeSeconds ? '2-digit' : undefined,
    });
  } catch {
    return 'Timestamp unavailable';
  }
}
