'use client';

import React, { useEffect, useState } from 'react';
import { WifiOff, CheckCircle2, RefreshCw } from 'lucide-react';

export function NetworkStatusBanner() {
  const [isOnline, setIsOnline] = useState(true);
  const [showRestoredNotice, setShowRestoredNotice] = useState(false);
  const [isChecking, setIsChecking] = useState(false);

  useEffect(() => {
    // Initial check
    if (typeof navigator !== 'undefined') {
      setIsOnline(navigator.onLine);
    }

    const handleOnline = () => {
      setIsOnline(true);
      setShowRestoredNotice(true);
      const timer = setTimeout(() => {
        setShowRestoredNotice(false);
      }, 3500);
      return () => clearTimeout(timer);
    };

    const handleOffline = () => {
      setIsOnline(false);
      setShowRestoredNotice(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleManualCheck = async () => {
    setIsChecking(true);
    try {
      // Ping a lightweight endpoint or head request
      await fetch('/api/v1/workspaces', { method: 'HEAD', cache: 'no-store' });
      setIsOnline(true);
      setShowRestoredNotice(true);
      setTimeout(() => setShowRestoredNotice(false), 3000);
    } catch {
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        setIsOnline(false);
      }
    } finally {
      setIsChecking(false);
    }
  };

  // If online and not showing the restored notice, render nothing
  if (isOnline && !showRestoredNotice) {
    return null;
  }

  if (showRestoredNotice) {
    return (
      <aside
        aria-label="Network status notification"
        className="fixed top-4 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-3 duration-300 pointer-events-auto"
      >
        <div className="flex items-center gap-2.5 px-4 py-2 rounded-full bg-emerald-500/15 dark:bg-emerald-500/20 border border-emerald-500/30 text-emerald-950 dark:text-emerald-200 backdrop-blur-md shadow-lg shadow-emerald-500/10 text-xs font-medium">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span>Internet connection restored. Reconnecting to OMS...</span>
        </div>
      </aside>
    );
  }

  return (
    <aside
      aria-label="Network status notification"
      className="fixed top-4 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-3 duration-300 pointer-events-auto max-w-[90vw] md:max-w-lg"
    >
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 rounded-2xl bg-amber-500/15 dark:bg-amber-500/20 border border-amber-500/30 text-amber-950 dark:text-amber-200 backdrop-blur-md shadow-xl shadow-amber-500/10 text-xs font-medium">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="relative shrink-0">
            <WifiOff className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping" />
          </div>
          <span className="truncate">
            You are currently offline. Actions requiring live sync are paused.
          </span>
        </div>
        <button
          onClick={handleManualCheck}
          disabled={isChecking}
          className="shrink-0 flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-950 dark:text-amber-100 transition-colors disabled:opacity-50 text-[11px] font-semibold"
        >
          <RefreshCw className={`w-3 h-3 ${isChecking ? 'animate-spin' : ''}`} />
          <span>Check</span>
        </button>
      </div>
    </aside>
  );
}
