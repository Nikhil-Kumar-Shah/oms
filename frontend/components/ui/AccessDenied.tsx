'use client';

import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/Button';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export interface AccessDeniedProps {
  title?: string;
  message?: string;
  requiredRoleOrPermission?: string;
}

export const AccessDenied: React.FC<AccessDeniedProps> = ({
  title = 'Access Denied (403)',
  message = 'You do not have the required operational privileges or vertical scope to access this screen.',
  requiredRoleOrPermission,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs max-w-xl mx-auto my-8 space-y-5">
      <div className="w-14 h-14 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 flex items-center justify-center text-rose-600 dark:text-rose-400">
        <ShieldAlert className="w-7 h-7" />
      </div>

      <div className="space-y-1.5">
        <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">{title}</h3>
        <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed max-w-md">
          {message}
        </p>
        {requiredRoleOrPermission && (
          <div className="mt-2 text-[11px] font-mono text-zinc-500 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-md inline-block">
            Required: {requiredRoleOrPermission}
          </div>
        )}
      </div>

      <div className="pt-2">
        <Link href="/">
          <Button variant="primary" size="sm" leftIcon={<ArrowLeft className="w-4 h-4" />}>
            Return to Workspace Home
          </Button>
        </Link>
      </div>
    </div>
  );
};
