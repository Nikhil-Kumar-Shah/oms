import React from 'react';
import { Button } from '@/components/ui/Button';
import { AlertCircle, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'primary';
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: React.ReactNode;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'primary',
  isLoading = false,
  onConfirm,
  onCancel,
  children,
}) => {
  if (!isOpen) return null;

  let Icon = CheckCircle2;
  let iconBg = 'bg-indigo-100 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400';
  let buttonVariant: 'primary' | 'danger' | 'outline' = 'primary';

  if (variant === 'danger') {
    Icon = AlertCircle;
    iconBg = 'bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400';
    buttonVariant = 'danger';
  } else if (variant === 'warning') {
    Icon = AlertTriangle;
    iconBg = 'bg-amber-100 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400';
    buttonVariant = 'primary';
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="w-full max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl p-6 space-y-4"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start gap-3.5">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${iconBg}`}>
            <Icon className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">{title}</h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">{description}</p>
          </div>
        </div>

        {children && <div className="pt-2">{children}</div>}

        <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-zinc-100 dark:border-zinc-800">
          <Button variant="outline" size="sm" onClick={onCancel} disabled={isLoading}>
            {cancelLabel}
          </Button>
          <Button
            variant={buttonVariant}
            size="sm"
            onClick={onConfirm}
            isLoading={isLoading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};
