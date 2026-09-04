import React from 'react';
import { cn } from '@/lib/utils';
import { AlertCircle, CheckCircle2, Info, AlertTriangle, X } from 'lucide-react';

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'info' | 'success' | 'warning' | 'danger';
  title?: string;
  onClose?: () => void;
}

export const Alert: React.FC<AlertProps> = ({
  className,
  variant = 'info',
  title,
  children,
  onClose,
  ...props
}) => {
  const icons = {
    info: <Info className="w-5 h-5 text-sky-600 dark:text-sky-400 shrink-0" />,
    success: <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />,
    warning: <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />,
    danger: <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />,
  };

  const variants = {
    info: 'bg-sky-500/10 dark:bg-sky-500/10 border-sky-500/25 text-sky-900 dark:text-sky-300',
    success:
      'bg-emerald-500/10 dark:bg-emerald-500/10 border-emerald-500/25 text-emerald-900 dark:text-emerald-300',
    warning:
      'bg-amber-500/10 dark:bg-amber-500/10 border-amber-500/25 text-amber-900 dark:text-amber-300',
    danger:
      'bg-rose-500/10 dark:bg-rose-500/10 border-rose-500/25 text-rose-900 dark:text-rose-300',
  };

  return (
    <div
      role="alert"
      className={cn('flex items-start justify-between gap-3 p-4 rounded-xl border text-sm', variants[variant], className)}
      {...props}
    >
      <div className="flex items-start gap-3 flex-1">
        {icons[variant]}
        <div className="space-y-0.5 flex-1">
          {title && <h5 className="font-semibold leading-tight">{title}</h5>}
          <div className="text-xs leading-relaxed opacity-90">{children}</div>
        </div>
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
          aria-label="Dismiss alert"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};
