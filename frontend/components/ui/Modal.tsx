import React, { useEffect } from 'react';
import { cn } from '@/lib/utils';
import { X } from 'lucide-react';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'wide';
}

const SIZE_CLASSES: Record<string, string> = {
  sm: 'w-[94vw] sm:w-[85vw] md:w-[480px] max-w-md',
  md: 'w-[95vw] sm:w-[88vw] md:w-[75vw] lg:w-[62vw] max-w-3xl',
  lg: 'w-[95vw] sm:w-[92vw] md:w-[82vw] lg:w-[72vw] xl:w-[68vw] max-w-5xl',
  wide: 'w-[95vw] sm:w-[92vw] md:w-[82vw] lg:w-[72vw] xl:w-[68vw] max-w-5xl',
  xl: 'w-[96vw] sm:w-[94vw] md:w-[88vw] lg:w-[80vw] xl:w-[76vw] max-w-6xl',
  '2xl': 'w-[96vw] sm:w-[94vw] md:w-[90vw] lg:w-[85vw] max-w-7xl',
};

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  className,
  bodyClassName,
  size = 'lg',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog Container */}
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          'relative w-full max-h-[88vh] flex flex-col bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 rounded-2xl shadow-2xl overflow-hidden z-10 animate-in zoom-in-95 duration-150',
          SIZE_CLASSES[size] || SIZE_CLASSES.lg,
          className
        )}
      >
        {/* Fixed Header */}
        {(title || description) && (
          <div className="shrink-0 px-5 sm:px-6 py-4 border-b border-zinc-200/80 dark:border-zinc-800 flex items-start justify-between bg-white dark:bg-zinc-900">
            <div className="min-w-0 pr-3">
              {title && (
                typeof title === 'string' ? (
                  <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100 truncate">{title}</h3>
                ) : (
                  title
                )
              )}
              {description && (
                typeof description === 'string' ? (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{description}</p>
                ) : (
                  description
                )
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="shrink-0 p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
              aria-label="Close dialog"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Scrollable Content Body */}
        <div className={cn('p-5 sm:p-6 overflow-y-auto overflow-x-hidden flex-1', bodyClassName)}>
          {children}
        </div>

        {/* Optional Fixed Footer (Action Buttons) */}
        {footer && (
          <div className="shrink-0 px-5 sm:px-6 py-3.5 sm:py-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/70 flex items-center justify-end gap-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
