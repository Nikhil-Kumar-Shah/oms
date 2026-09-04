'use client';

import React, { useEffect } from 'react';
import { Poppins } from 'next/font/google';
import { ErrorView } from '@/components/ui/ErrorView';
import './globals.css';

const poppins = Poppins({
  weight: ['400', '500', '600', '700'],
  subsets: ['latin'],
  variable: '--font-poppins',
  display: 'swap',
});

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Paradox OMS Root Layout Critical Error:', error);
  }, [error]);

  return (
    <html lang="en" className={poppins.variable}>
      <body className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 transition-colors font-sans antialiased">
        <ErrorView
          error={error}
          onRetry={reset}
          layout="fullPage"
        />
      </body>
    </html>
  );
}
