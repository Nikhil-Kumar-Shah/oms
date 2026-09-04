'use client';

import React from 'react';

interface ReadinessBarProps {
  percentage: number;
  totalCheckpoints?: number;
  completedCheckpoints?: number;
  showDetails?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function ReadinessBar({
  percentage,
  totalCheckpoints,
  completedCheckpoints,
  showDetails = true,
  size = 'md',
}: ReadinessBarProps) {
  const clamped = Math.min(100, Math.max(0, Math.round(percentage)));

  const getColorClass = (val: number) => {
    if (val >= 80) return 'bg-emerald-500 text-emerald-600 dark:text-emerald-400';
    if (val >= 50) return 'bg-amber-500 text-amber-600 dark:text-amber-400';
    if (val > 0) return 'bg-orange-500 text-orange-600 dark:text-orange-400';
    return 'bg-slate-400 text-slate-500 dark:text-slate-400';
  };

  const getHeightClass = () => {
    switch (size) {
      case 'sm':
        return 'h-1.5';
      case 'lg':
        return 'h-3';
      case 'md':
      default:
        return 'h-2';
    }
  };

  return (
    <div className="w-full space-y-1.5">
      {showDetails && (
        <div className="flex items-center justify-between text-xs font-medium">
          <span className="text-slate-600 dark:text-slate-400">
            Readiness Checkpoints
            {totalCheckpoints !== undefined && completedCheckpoints !== undefined && (
              <span className="ml-1 text-slate-500 dark:text-slate-400">
                ({completedCheckpoints}/{totalCheckpoints} signed off)
              </span>
            )}
          </span>
          <span className={`font-bold ${getColorClass(clamped).split(' ')[1]}`}>
            {clamped}%
          </span>
        </div>
      )}
      <div className={`w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700 ${getHeightClass()}`}>
        <div
          className={`h-full transition-all duration-500 ease-out ${getColorClass(clamped).split(' ')[0]}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
