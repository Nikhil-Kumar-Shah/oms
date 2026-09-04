import React from 'react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const normalized = status.toUpperCase();

  let colorClasses = 'bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700';

  switch (normalized) {
    case 'NOT_STARTED':
    case 'TODO':
    case 'PLANNED':
    case 'DRAFT':
    case 'OPEN':
    case 'RAISED':
      colorClasses = 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/50';
      break;
    case 'ACKNOWLEDGED':
    case 'FORWARDED':
      colorClasses = 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-800/50';
      break;
    case 'IN_PROGRESS':
    case 'CONFIRMED':
    case 'SUBMITTED':
    case 'AWAITING_INFO':
      colorClasses = 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/50';
      break;
    case 'COMPLETED':
    case 'COMPLETE':
    case 'RESOLVED':
    case 'REVIEWED':
    case 'APPROVED':
      colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/50';
      break;
    case 'BLOCKED':
    case 'ESCALATED':
    case 'FLAGGED':
    case 'CRITICAL':
    case 'OVERDUE':
    case 'RETURNED':
    case 'REJECTED':
      colorClasses = 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/50';
      break;
    case 'CANCELLED':
    case 'CLOSED':
    case 'ARCHIVED':
      colorClasses = 'bg-zinc-100 text-zinc-500 border-zinc-200 dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-800';
      break;
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs font-medium' : 'px-2.5 py-1 text-xs font-semibold';

  const formatStatusText = (str: string) => {
    switch (str) {
      case 'PLANNING':
        return 'Planning';
      case 'NOT_STARTED':
        return 'Not Started';
      case 'IN_PROGRESS':
        return 'In Progress';
      case 'COMPLETED':
        return 'Completed';
      case 'CANCELLED':
        return 'Cancelled';
      default:
        return str
          .toLowerCase()
          .split('_')
          .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
          .join(' ');
    }
  };

  return (
    <span className={`inline-flex items-center rounded-full border ${colorClasses} ${sizeClasses}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5 opacity-70" />
      {formatStatusText(normalized)}
    </span>
  );
};
