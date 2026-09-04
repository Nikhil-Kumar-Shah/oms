import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Clock, Check } from 'lucide-react';

interface HealthIndicatorProps {
  health: string;
  size?: 'sm' | 'md';
}

export const HealthIndicator: React.FC<HealthIndicatorProps> = ({ health, size = 'md' }) => {
  const normalized = health.toUpperCase();

  let colorClasses = 'text-zinc-600 bg-zinc-100 border-zinc-200 dark:text-zinc-400 dark:bg-zinc-800 dark:border-zinc-700';
  let Icon = CheckCircle2;
  let label = 'On Track';

  switch (normalized) {
    case 'ON_TRACK':
      colorClasses = 'text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-300 dark:bg-emerald-950/40 dark:border-emerald-800/50';
      Icon = CheckCircle2;
      label = 'On Track';
      break;
    case 'COMPLETE':
      colorClasses = 'text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-300 dark:bg-emerald-950/40 dark:border-emerald-800/50';
      Icon = Check;
      label = 'Complete';
      break;
    case 'AT_RISK':
      colorClasses = 'text-amber-700 bg-amber-50 border-amber-200 dark:text-amber-300 dark:bg-amber-950/40 dark:border-amber-800/50';
      Icon = AlertTriangle;
      label = 'At Risk';
      break;
    case 'OVERDUE':
      colorClasses = 'text-rose-700 bg-rose-50 border-rose-200 dark:text-rose-300 dark:bg-rose-950/40 dark:border-rose-800/50';
      Icon = Clock;
      label = 'Overdue';
      break;
    case 'BLOCKED':
    case 'CRITICAL':
      colorClasses = 'text-rose-700 bg-rose-50 border-rose-200 dark:text-rose-300 dark:bg-rose-950/40 dark:border-rose-800/50';
      Icon = XCircle;
      label = normalized === 'BLOCKED' ? 'Blocked' : 'Critical';
      break;
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs font-medium' : 'px-2.5 py-1 text-xs font-semibold';
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${colorClasses} ${sizeClasses}`}>
      <Icon className={iconSize} />
      {label}
    </span>
  );
};
