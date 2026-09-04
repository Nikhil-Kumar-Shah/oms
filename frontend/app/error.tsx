'use client';

import React, { useEffect } from 'react';
import { ErrorView } from '@/components/ui/ErrorView';

export default function GlobalRouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to frontend telemetry / console safely
    console.error('Paradox OMS Segment Error:', error);
  }, [error]);

  return (
    <ErrorView
      error={error}
      onRetry={reset}
      layout="fullPage"
    />
  );
}
