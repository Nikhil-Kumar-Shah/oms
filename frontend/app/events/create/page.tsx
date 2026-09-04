'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout/AppShell';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import Link from 'next/link';
import { canCreateEvent } from '@/lib/permissions';

export default function CreateEventPage() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const isAuthorized = canCreateEvent(user);

  useEffect(() => {
    if (!isLoading && !isAuthorized) {
      // Non-executives are not allowed
    }
  }, [isLoading, isAuthorized, router]);

  if (isLoading) {

    return (
      <AppShell>
        <div className="flex items-center justify-center p-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        </div>
      </AppShell>
    );
  }

  if (!isAuthorized) {
    return (
      <AppShell>
        <div className="mx-auto max-w-xl py-12 space-y-4 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
            Unauthorized Access
          </h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Only Sports Core and Deputy Core executive members are authorized to create events.
          </p>
          <div className="pt-4">
            <Link href="/events">
              <Button variant="outline" leftIcon={<ArrowLeft className="h-4 w-4" />}>
                Back to Events
              </Button>
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  // Redirect or show guidance to events page where the executive creation dialog is hosted
  return (
    <AppShell>
      <div className="mx-auto max-w-2xl py-8 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Create Event
          </h1>
          <Link href="/events">
            <Button variant="outline" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" />}>
              Back to Events
            </Button>
          </Link>
        </div>
        <Alert variant="info" title="Executive Workflow">
          Please use the Create Event dialog on the main Events workspace to configure events, event team accounts, and POC rosters.
        </Alert>
        <Link href="/events">
          <Button variant="primary">
            Open Events Workspace
          </Button>
        </Link>
      </div>
    </AppShell>
  );
}
