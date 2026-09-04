import React from 'react';
import { ErrorView } from '@/components/ui/ErrorView';

export default function NotFound() {
  return (
    <ErrorView
      type="404"
      layout="fullPage"
      returnHref="/"
      returnLabel="Return to Workspace"
    />
  );
}
