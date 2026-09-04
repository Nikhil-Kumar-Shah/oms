import React from 'react';
import { cn } from '@/lib/utils';
import { Spinner } from './Spinner';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled,
      children,
      leftIcon,
      rightIcon,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:ring-offset-1 dark:focus:ring-offset-zinc-950 disabled:opacity-45 disabled:pointer-events-none select-none active:scale-[0.98] cursor-pointer';

    const variants = {
      primary:
        'bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-zinc-950 font-semibold shadow-sm shadow-orange-950/15 dark:from-amber-500 dark:to-orange-500 dark:text-zinc-950 dark:hover:from-amber-400 dark:hover:to-orange-400',
      secondary:
        'bg-zinc-100 hover:bg-zinc-200 text-zinc-900 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:text-zinc-100 border border-zinc-200/80 dark:border-zinc-700/60',
      outline:
        'border border-zinc-300 dark:border-zinc-700/80 bg-transparent hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60 text-zinc-800 dark:text-zinc-100',
      ghost:
        'bg-transparent hover:bg-zinc-100/70 dark:hover:bg-zinc-800/60 text-zinc-700 dark:text-zinc-300',
      danger:
        'bg-rose-600 hover:bg-rose-500 active:bg-rose-700 text-white font-medium shadow-sm shadow-rose-950/20',
    };

    const sizes = {
      sm: 'h-8 px-3 text-xs gap-1.5 rounded-lg',
      md: 'h-10 px-4 text-xs sm:text-sm gap-2 rounded-xl',
      lg: 'h-11 px-5 text-sm sm:text-base gap-2.5 rounded-xl',
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isLoading}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      >
        {isLoading && <Spinner size={size === 'lg' ? 'md' : 'sm'} className="mr-1" />}
        {!isLoading && leftIcon && <span className="inline-flex shrink-0">{leftIcon}</span>}
        <span>{children}</span>
        {!isLoading && rightIcon && <span className="inline-flex shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';
