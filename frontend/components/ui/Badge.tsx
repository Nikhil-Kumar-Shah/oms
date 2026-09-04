import React from 'react';
import { cn } from '@/lib/utils';
import { CanonicalRole } from '@/types/user';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'ember' | 'cream';
  role?: CanonicalRole;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = 'default',
  role,
  size = 'md',
  children,
  ...props
}) => {
  const base = 'inline-flex items-center font-medium rounded-full';

  const sizes = {
    sm: 'px-2 py-0.5 text-[10px] leading-tight',
    md: 'px-2.5 py-1 text-xs leading-none',
  };

  const variants = {
    default: 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200/80 dark:border-zinc-700/60',
    success: 'bg-emerald-500/10 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/25 font-medium',
    warning: 'bg-amber-500/10 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/25 font-medium',
    danger: 'bg-rose-500/10 dark:bg-rose-500/15 text-rose-700 dark:text-rose-400 border border-rose-500/25 font-medium',
    info: 'bg-sky-500/10 dark:bg-sky-500/15 text-sky-700 dark:text-sky-400 border border-sky-500/25 font-medium',
    purple: 'bg-purple-500/10 dark:bg-purple-500/15 text-purple-700 dark:text-purple-400 border border-purple-500/25 font-medium',
    ember: 'bg-orange-500/10 dark:bg-orange-500/15 text-orange-700 dark:text-orange-400 border border-orange-500/25 font-medium',
    cream: 'bg-[#f5f0e6] text-[#161514] border border-[#e8e0d0] font-semibold',
  };

  // Special role badge styles
  if (role) {
    const roleStyles: Record<CanonicalRole, string> = {
      ADMIN: 'bg-purple-500/10 dark:bg-purple-500/15 text-purple-700 dark:text-purple-300 border border-purple-500/25 font-semibold',
      SPORTS_CORE: 'bg-amber-500/10 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30 font-semibold',
      DEPUTY_CORE: 'bg-amber-500/10 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/20 font-semibold',
      SUPER_COORDINATOR: 'bg-sky-500/10 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-500/25 font-medium',
      COORDINATOR: 'bg-teal-500/10 dark:bg-teal-500/15 text-teal-700 dark:text-teal-300 border border-teal-500/25 font-medium',
      VOLUNTEER: 'bg-emerald-500/10 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/25 font-medium',
      EVENT_TEAM: 'bg-orange-500/10 dark:bg-orange-500/15 text-orange-700 dark:text-orange-400 border border-orange-500/30 font-medium',
    };

    return (
      <span className={cn(base, sizes[size], roleStyles[role], className)} {...props}>
        {children || role.replace('_', ' ')}
      </span>
    );
  }

  return (
    <span className={cn(base, sizes[size], variants[variant], className)} {...props}>
      {children}
    </span>
  );
};
