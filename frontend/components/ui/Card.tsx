import React from 'react';
import { cn } from '@/lib/utils';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'outline' | 'flat' | 'cream';
}

export const Card: React.FC<CardProps> = ({ className, variant = 'default', children, ...props }) => {
  const variants = {
    default:
      'bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs rounded-xl overflow-hidden',
    outline: 'bg-transparent border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden',
    flat: 'bg-zinc-50 dark:bg-zinc-800/50 rounded-xl overflow-hidden',
    cream: 'bg-[#f5f0e6] text-[#161514] border border-[#e8e0d0] rounded-xl overflow-hidden shadow-sm',
  };

  return (
    <div className={cn(variants[variant], className)} {...props}>
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={cn('px-4 sm:px-6 py-3.5 sm:py-4 border-b border-zinc-100 dark:border-zinc-800', className)} {...props}>
    {children}
  </div>
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({ className, children, ...props }) => (
  <h3 className={cn('text-sm sm:text-base font-semibold text-zinc-900 dark:text-zinc-100', className)} {...props}>
    {children}
  </h3>
);

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className,
  children,
  ...props
}) => (
  <p className={cn('text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 sm:mt-1', className)} {...props}>
    {children}
  </p>
);

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={cn('p-4 sm:p-6', className)} {...props}>
    {children}
  </div>
);

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div
    className={cn(
      'px-4 sm:px-6 py-3 sm:py-3.5 bg-zinc-50/50 dark:bg-zinc-800/30 border-t border-zinc-100 dark:border-zinc-800 flex flex-wrap items-center justify-between gap-2',
      className
    )}
    {...props}
  >
    {children}
  </div>
);
