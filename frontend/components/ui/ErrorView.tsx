'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
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
  AlertOctagon,
  RotateCw,
  ArrowLeft,
  Home,
  LogIn,
} from 'lucide-react';
import { ApiException } from '@/lib/api';

export type ErrorCategory =
  | 'offline'
  | 'backend_unavailable'
  | 'database_unavailable'
  | '500'
  | '401'
  | '403'
  | '404'
  | 'timeout'
  | 'app_error'
  | 'network_failure'
  | 'generic';

export type ErrorType = ErrorCategory;

export interface ErrorViewProps {
  type?: ErrorCategory;
  error?: unknown;
  title?: string;
  message?: string;
  statusCode?: number | string;
  onRetry?: () => void | Promise<void>;
  retryLabel?: string;
  showHomeButton?: boolean;
  showBackButton?: boolean;
  homeHref?: string;
  returnHref?: string;
  homeLabel?: string;
  returnLabel?: string;
  layout?: 'fullPage' | 'inline';
  className?: string;
}

interface ErrorMeta {
  badge: string;
  defaultTitle: string;
  defaultMessage: string;
  icon: React.ComponentType<{ className?: string }>;
  theme: 'rose' | 'amber' | 'indigo' | 'zinc';
}

const ERROR_CONFIG: Record<ErrorCategory, ErrorMeta> = {
  offline: {
    badge: 'Offline Mode',
    defaultTitle: 'No Internet Connection',
    defaultMessage: 'You are currently offline. Please check your network connection and try again.',
    icon: WifiOff,
    theme: 'amber',
  },
  backend_unavailable: {
    badge: '503 Service Unavailable',
    defaultTitle: 'Backend Service Unreachable',
    defaultMessage: 'The Paradox Sports OMS server is currently unreachable. Our operations team is actively investigating.',
    icon: ServerOff,
    theme: 'rose',
  },
  database_unavailable: {
    badge: '503 Database Unavailable',
    defaultTitle: 'Database Connection Unavailable',
    defaultMessage: 'The operational database service is momentarily unavailable. Please retry in a few moments.',
    icon: Database,
    theme: 'rose',
  },
  '500': {
    badge: '500 Server Error',
    defaultTitle: 'Internal Server Error',
    defaultMessage: 'An unexpected server error occurred while processing your request. Please try again later.',
    icon: AlertTriangle,
    theme: 'rose',
  },
  '401': {
    badge: '401 Unauthorized',
    defaultTitle: 'Session Expired',
    defaultMessage: 'Your active session has expired or requires authentication. Please sign in to continue.',
    icon: Lock,
    theme: 'amber',
  },
  '403': {
    badge: '403 Forbidden',
    defaultTitle: 'Access Restricted',
    defaultMessage: 'You do not have the required operational privileges or vertical scope to access this section.',
    icon: ShieldAlert,
    theme: 'rose',
  },
  '404': {
    badge: '404 Not Found',
    defaultTitle: 'Page Not Found',
    defaultMessage: 'The requested page or operational record does not exist or may have been moved.',
    icon: SearchX,
    theme: 'zinc',
  },
  timeout: {
    badge: '408 Request Timeout',
    defaultTitle: 'Request Timed Out',
    defaultMessage: 'The request took too long to complete. Please check your network connection and retry.',
    icon: Clock,
    theme: 'amber',
  },
  app_error: {
    badge: 'Application Error',
    defaultTitle: 'Something Went Wrong',
    defaultMessage: 'An unexpected client-side error occurred. We have isolated the issue to protect your data.',
    icon: AlertOctagon,
    theme: 'rose',
  },
  network_failure: {
    badge: 'Connection Dropped',
    defaultTitle: 'Network Connection Lost',
    defaultMessage: 'Unable to communicate with the server. Please check your internet or local proxy settings.',
    icon: WifiOff,
    theme: 'amber',
  },
  generic: {
    badge: 'Error',
    defaultTitle: 'Operation Failed',
    defaultMessage: 'An issue occurred while completing your request. Please retry.',
    icon: AlertTriangle,
    theme: 'rose',
  },
};

/**
 * Derives the canonical error category from an unknown error object.
 */
export function classifyError(error: unknown, explicitType?: ErrorCategory): ErrorCategory {
  if (explicitType) return explicitType;

  // 1. Check browser network offline status
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return 'offline';
  }

  // 2. ApiException classification
  if (error instanceof ApiException) {
    if (error.status === 401) return '401';
    if (error.status === 403) return '403';
    if (error.status === 404) return '404';
    if (error.status === 408 || error.code === 'TIMEOUT') return 'timeout';
    if (error.code === 'OFFLINE') return 'offline';
    if (error.code === 'DATABASE_ERROR' || error.code === 'DB_UNAVAILABLE') return 'database_unavailable';
    if (
      error.status === 502 ||
      error.status === 503 ||
      error.status === 504 ||
      error.code === 'BACKEND_UNAVAILABLE' ||
      error.code === 'SERVICE_UNAVAILABLE'
    ) {
      return 'backend_unavailable';
    }
    if (error.status >= 500) return '500';
    return 'generic';
  }

  // 3. Native Error classification
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    if (error.name === 'AbortError' || msg.includes('timeout')) {
      return 'timeout';
    }
    if (msg.includes('offline') || msg.includes('no internet')) {
      return 'offline';
    }
    if (msg.includes('failed to fetch') || msg.includes('network') || msg.includes('connection refused')) {
      return typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'backend_unavailable';
    }
    return 'app_error';
  }

  return 'generic';
}

export const ErrorView: React.FC<ErrorViewProps> = ({
  type,
  error,
  title,
  message,
  statusCode,
  onRetry,
  retryLabel = 'Try Again',
  showHomeButton = true,
  showBackButton = true,
  homeHref = '/',
  returnHref,
  homeLabel,
  returnLabel,
  layout = 'inline',
  className = '',
}) => {
  const router = useRouter();
  const [retrying, setRetrying] = useState(false);
  const [retryCooldown, setRetryCooldown] = useState(false);

  const targetHomeHref = returnHref || homeHref;
  const targetHomeLabel = returnLabel || homeLabel || 'Workspace Home';

  const category = classifyError(error, type);
  const meta = ERROR_CONFIG[category] || ERROR_CONFIG.generic;
  const Icon = meta.icon;

  const displayTitle = title || meta.defaultTitle;
  const displayMessage = message || meta.defaultMessage;
  const displayBadge = statusCode ? `${statusCode} Error` : meta.badge;

  const handleRetry = async () => {
    if (!onRetry || retrying || retryCooldown) return;

    setRetrying(true);
    try {
      await Promise.resolve(onRetry());
    } finally {
      setRetrying(false);
      // Debounce rapid retries (1.5s cooldown)
      setRetryCooldown(true);
      setTimeout(() => setRetryCooldown(false), 1500);
    }
  };

  const handleGoBack = () => {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back();
    } else {
      router.push(homeHref);
    }
  };

  // Theme color styles
  const themeStyles = {
    rose: {
      iconBg: 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800/70 text-rose-600 dark:text-rose-400 shadow-rose-500/10',
      badge: 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800',
    },
    amber: {
      iconBg: 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/70 text-amber-600 dark:text-amber-400 shadow-amber-500/10',
      badge: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    },
    indigo: {
      iconBg: 'bg-indigo-50 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800/70 text-indigo-600 dark:text-indigo-400 shadow-indigo-500/10',
      badge: 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800',
    },
    zinc: {
      iconBg: 'bg-zinc-100 dark:bg-zinc-800/80 border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 shadow-zinc-500/10',
      badge: 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700',
    },
  }[meta.theme];

  const content = (
    <div className="max-w-md w-full text-center space-y-6 animate-in fade-in zoom-in-95 duration-200">
      {/* Icon with glowing pill */}
      <div className="relative inline-flex items-center justify-center">
        <div
          className={`w-16 h-16 sm:w-20 sm:h-20 rounded-3xl border flex items-center justify-center shadow-lg transition-transform hover:scale-105 ${themeStyles.iconBg}`}
        >
          <Icon className="w-8 h-8 sm:w-10 sm:h-10" />
        </div>
      </div>

      {/* Status Badge & Text */}
      <div className="space-y-2">
        <div className="flex justify-center">
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide uppercase border ${themeStyles.badge}`}
          >
            {displayBadge}
          </span>
        </div>
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          {displayTitle}
        </h2>
        <p className="text-xs sm:text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed max-w-sm mx-auto">
          {displayMessage}
        </p>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
        {category === '401' ? (
          <Link href="/login">
            <Button
              variant="primary"
              size="md"
              leftIcon={<LogIn className="w-4 h-4" />}
            >
              Sign In
            </Button>
          </Link>
        ) : onRetry ? (
          <Button
            variant="primary"
            size="md"
            onClick={handleRetry}
            isLoading={retrying}
            disabled={retryCooldown}
            leftIcon={<RotateCw className={`w-4 h-4 ${retrying ? 'animate-spin' : ''}`} />}
          >
            {retrying ? 'Retrying...' : retryLabel}
          </Button>
        ) : null}

        {showBackButton && (
          <Button
            variant="outline"
            size="md"
            onClick={handleGoBack}
            leftIcon={<ArrowLeft className="w-4 h-4" />}
          >
            Go Back
          </Button>
        )}

        {showHomeButton && category !== '401' && (
          <Link href={targetHomeHref}>
            <Button
              variant="secondary"
              size="md"
              leftIcon={<Home className="w-4 h-4" />}
            >
              {targetHomeLabel}
            </Button>
          </Link>
        )}
      </div>
    </div>
  );

  if (layout === 'fullPage') {
    return (
      <div
        className={`min-h-screen flex items-center justify-center p-6 bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 transition-colors ${className}`}
        role="alert"
        aria-live="assertive"
      >
        {content}
      </div>
    );
  }

  // Inline container within existing layout
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-3xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs max-w-2xl mx-auto my-8 ${className}`}
      role="alert"
      aria-live="assertive"
    >
      {content}
    </div>
  );
};
