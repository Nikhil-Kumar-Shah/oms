'use client';

import React from 'react';
import Link from 'next/link';
import { AppShell } from '@/components/layout/AppShell';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { ArrowLeft, Info } from 'lucide-react';

export default function DirectivesPage() {
  return (
    <AppShell>
      <div className="mx-auto max-w-2xl py-12 space-y-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
          <Info className="h-6 w-6" />
        </div>
        <div className="space-y-2">
          <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
            Directives Module Retired
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Mandatory operational actions and department broadcasts are now managed directly through Tasks, Announcements, and Official Communications.
          </p>
        </div>
        <div className="pt-2">
          <Link href="/">
            <Button variant="outline" leftIcon={<ArrowLeft className="h-4 w-4" />}>
              Return to Workspace
            </Button>
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
