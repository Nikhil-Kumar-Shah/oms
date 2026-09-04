import React from 'react';

interface ActiveBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export const ActiveBadge: React.FC<ActiveBadgeProps> = ({ status, size = 'sm' }) => {
  const normalized = (status || '').toUpperCase();
  const isActive = ['NOT_STARTED', 'TODO', 'IN_PROGRESS', 'BLOCKED'].includes(normalized);

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[11px] font-semibold' : 'px-2.5 py-1 text-xs font-semibold';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${
        isActive
          ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/50'
          : 'bg-zinc-100 text-zinc-500 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:border-zinc-700'
      } ${sizeClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-500' : 'bg-zinc-400'}`} />
      Active: {isActive ? 'Yes' : 'No'}
    </span>
  );
};
