'use client';

import React, { useState } from 'react';
import { ErrorView, ErrorType } from '@/components/ui/ErrorView';
import { Button } from '@/components/ui/Button';
import { 
  WifiOff, 
  ServerOff, 
  Database, 
  AlertTriangle, 
  Lock, 
  ShieldAlert, 
  SearchX, 
  Clock, 
  Radio, 
  Bomb,
  Layers,
  Monitor
} from 'lucide-react';
import Link from 'next/link';

export default function TestErrorsPage() {
  const [activeType, setActiveType] = useState<ErrorType | 'render_crash'>('offline');
  const [layoutMode, setLayoutMode] = useState<'fullPage' | 'inline'>('fullPage');
  const [retryFeedback, setRetryFeedback] = useState<string | null>(null);

  // Trigger a true React rendering crash when requested
  if (activeType === 'render_crash') {
    throw new Error('Simulated React frontend rendering crash for Error Boundary verification.');
  }

  const handleSimulatedRetry = () => {
    setRetryFeedback('Retry action triggered successfully at ' + new Date().toLocaleTimeString());
    setTimeout(() => setRetryFeedback(null), 3500);
  };

  const errorScenarios: {
    type: ErrorType;
    label: string;
    description: string;
    icon: React.ReactNode;
    badge: string;
  }[] = [
    {
      type: 'offline',
      label: 'Offline / No Internet',
      description: 'Client device loses network connectivity (!navigator.onLine)',
      icon: <WifiOff className="w-4 h-4" />,
      badge: 'Client Network',
    },
    {
      type: 'backend_unavailable',
      label: 'Backend Unavailable',
      description: 'API gateway or OMS FastAPI daemon down (502 / 503)',
      icon: <ServerOff className="w-4 h-4" />,
      badge: '503 Service',
    },
    {
      type: 'database_unavailable',
      label: 'Database Unavailable',
      description: 'PostgreSQL or SQLite storage engine connection loss',
      icon: <Database className="w-4 h-4" />,
      badge: 'DB Cluster',
    },
    {
      type: '500',
      label: 'Internal Server Error',
      description: 'Unexpected backend unhandled exception with sanitized output',
      icon: <AlertTriangle className="w-4 h-4" />,
      badge: '500 Error',
    },
    {
      type: '401',
      label: 'Unauthorized',
      description: 'Invalid, missing, or expired authentication session',
      icon: <Lock className="w-4 h-4" />,
      badge: '401 Auth',
    },
    {
      type: '403',
      label: 'Forbidden / Restricted',
      description: 'Insufficient vertical or role permissions for resource',
      icon: <ShieldAlert className="w-4 h-4" />,
      badge: '403 RBAC',
    },
    {
      type: '404',
      label: 'Not Found',
      description: 'Non-existent task, report, issue, or route requested',
      icon: <SearchX className="w-4 h-4" />,
      badge: '404 Route',
    },
    {
      type: 'timeout',
      label: 'Request Timeout',
      description: 'Gateway or API request timed out before response',
      icon: <Clock className="w-4 h-4" />,
      badge: '408 / 504',
    },
    {
      type: 'network_failure',
      label: 'Network / Transport Failure',
      description: 'Failed to establish socket connection or DNS lookup dropped',
      icon: <Radio className="w-4 h-4" />,
      badge: 'Transport',
    },
  ];

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 p-6 md:p-10 font-sans transition-colors">
      <header className="max-w-6xl mx-auto mb-8 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-zinc-200 dark:border-zinc-800">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-400">
              Paradox Sports OMS • System Diagnostics
            </span>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
              Unified Error Page Test Harness
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/">
              <Button variant="outline" size="sm">
                Exit to Dashboard
              </Button>
            </Link>
          </div>
        </div>

        <p className="text-sm text-zinc-600 dark:text-zinc-400 max-w-3xl">
          Use this interactive suite to verify visual fidelity, copy sanitization, action handling, and debounce logic for all 10 unified error states across full-page and inline layouts.
        </p>

        {retryFeedback && (
          <div className="px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-medium animate-in fade-in">
            ✓ {retryFeedback}
          </div>
        )}
      </header>

      <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Controls Column */}
        <div className="lg:col-span-4 space-y-6">
          {/* Mode Switcher */}
          <div className="p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-sm space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              Display Mode
            </h2>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setLayoutMode('fullPage')}
                className={`flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                  layoutMode === 'fullPage'
                    ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-500 text-rose-700 dark:text-rose-300 font-semibold'
                    : 'border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 text-zinc-600 dark:text-zinc-400'
                }`}
              >
                <Monitor className="w-3.5 h-3.5" />
                <span>Full Page</span>
              </button>
              <button
                onClick={() => setLayoutMode('inline')}
                className={`flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                  layoutMode === 'inline'
                    ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-500 text-rose-700 dark:text-rose-300 font-semibold'
                    : 'border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 text-zinc-600 dark:text-zinc-400'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Inline Card</span>
              </button>
            </div>
          </div>

          {/* Standard State Buttons */}
          <div className="p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-sm space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              Error Scenarios
            </h2>
            <div className="space-y-1.5">
              {errorScenarios.map((scenario) => {
                const isActive = activeType === scenario.type;
                return (
                  <button
                    key={scenario.type}
                    onClick={() => setActiveType(scenario.type)}
                    className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-left transition-all ${
                      isActive
                        ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950 border-transparent shadow-sm'
                        : 'border-zinc-100 dark:border-zinc-800/80 hover:bg-zinc-50 dark:hover:bg-zinc-800/40 text-zinc-700 dark:text-zinc-300'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={isActive ? 'text-rose-400 dark:text-rose-600' : 'text-zinc-400'}>
                        {scenario.icon}
                      </span>
                      <div className="min-w-0">
                        <div className="text-xs font-semibold truncate">{scenario.label}</div>
                        <div className={`text-[10px] truncate ${isActive ? 'text-zinc-300 dark:text-zinc-600' : 'text-zinc-400'}`}>
                          {scenario.badge}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Crash Trigger Button */}
          <div className="p-4 rounded-2xl bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200/80 dark:border-rose-900/40 shadow-sm space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-rose-700 dark:text-rose-400">
              Boundary Crash Test
            </h2>
            <p className="text-[11px] text-rose-800/80 dark:text-rose-300/80">
              Throws an unhandled React error in this component segment to verify Next.js <code className="px-1 py-0.5 rounded bg-rose-100 dark:bg-rose-900 font-mono text-[10px]">error.tsx</code> catches it.
            </p>
            <button
              onClick={() => setActiveType('render_crash')}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold transition-colors shadow-sm"
            >
              <Bomb className="w-3.5 h-3.5" />
              <span>Trigger Segment Crash</span>
            </button>
          </div>
        </div>

        {/* Preview Area */}
        <div className="lg:col-span-8">
          <div className="p-1 rounded-3xl bg-zinc-200/60 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-800">
            <div className="p-3 bg-zinc-100 dark:bg-zinc-900/80 rounded-t-2xl border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between text-xs text-zinc-500">
              <span className="font-mono text-[11px]">
                Preview: <strong className="text-zinc-800 dark:text-zinc-200 font-semibold">{activeType}</strong> ({layoutMode})
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-200 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                Safe Mode • No Traces Leaked
              </span>
            </div>

            <div className="min-h-[520px] bg-white dark:bg-zinc-950 rounded-b-2xl flex items-center justify-center p-4">
              {layoutMode === 'fullPage' ? (
                <div className="w-full">
                  <ErrorView
                    type={activeType as ErrorType}
                    layout="fullPage"
                    onRetry={handleSimulatedRetry}
                  />
                </div>
              ) : (
                <div className="w-full max-w-xl p-6 rounded-2xl bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800">
                  <div className="text-xs font-medium text-zinc-400 mb-4 pb-2 border-b border-zinc-200 dark:border-zinc-800">
                    Parent Component Card Example:
                  </div>
                  <ErrorView
                    type={activeType as ErrorType}
                    layout="inline"
                    onRetry={handleSimulatedRetry}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
