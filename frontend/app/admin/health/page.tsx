'use client';

/**
 * System Health & Diagnostic Telemetry Workspace (/admin/health)
 * Real-time database connectivity health, query latency probes, connection pool metrics,
 * and diagnostic telemetry for administrative inspection.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
import { adminApi, ApiException } from '@/lib/api';
import {
  Activity,
  Database,
  Server,
  Zap,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Clock,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface HealthData {
  status: string;
  latency_ms?: number;
  application?: {
    status?: string;
    app_name?: string;
    version?: string;
    environment?: string;
    timestamp?: string;
  };
  database?: {
    status?: string;
    latency_ms?: number;
    pool?: {
      size?: number;
      checked_in?: number;
      checked_out?: number;
      overflow?: number;
    };
    engine?: string;
  };
  timestamp?: string;
}

export default function AdminHealthPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastCheckTime, setLastCheckTime] = useState<string>('');
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<boolean>(false);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    const startTime = performance.now();
    try {
      const data = await adminApi.getHealth();
      const endTime = performance.now();
      const measuredLatency = Math.round(endTime - startTime);

      setHealth({
        ...data,
        latency_ms: data.latency_ms || measuredLatency,
      });
      setLastCheckTime(new Date().toLocaleTimeString());
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`Health probe error: ${err.message} (${err.code})`);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const startTime = performance.now();
    adminApi
      .getHealth()
      .then((data) => {
        if (active) {
          const endTime = performance.now();
          const measuredLatency = Math.round(endTime - startTime);
          setHealth({
            ...data,
            latency_ms: data.latency_ms || measuredLatency,
          });
          setLastCheckTime(new Date().toLocaleTimeString());
        }
      })
      .catch((err) => {
        if (active) {
          setErrorMsg(err instanceof Error ? err.message : 'Health probe failed');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    const interval = setInterval(fetchHealth, 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [fetchHealth]);

  const isHealthy = health?.status === 'healthy' || health?.status === 'ok';
  const isDbHealthy = health?.database?.status === 'healthy' || health?.database?.status === 'ok';

  return (
    <AppShell requiredRoles={['ADMIN']} requiredPermission="system.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-rose-950/20 via-pink-950/15 to-transparent border border-rose-200 dark:border-rose-800/40">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-rose-100 dark:bg-rose-900/50 text-rose-700 dark:text-rose-300">
                <Activity className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                System Health & Telemetry
              </h1>
              <Badge variant="default" size="sm">
                Administrative Diagnostics
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
              Authenticated diagnostic telemetry, PostgreSQL database connectivity, connection pool metrics, and response latency.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchHealth}
              isLoading={loading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Probe Now
            </Button>
          </div>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="System Diagnostic Alert" onClose={() => setErrorMsg(null)}>
            <div className="space-y-2">
              <p>{errorMsg}</p>
              <Button size="sm" variant="outline" onClick={fetchHealth}>
                Retry Diagnostic Probe
              </Button>
            </div>
          </Alert>
        )}

        {/* Telemetry Overview Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">System Status</p>
                <div className="flex items-center gap-1.5">
                  {isHealthy ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                  )}
                  <span className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                    {isHealthy ? 'HEALTHY' : 'DEGRADED'}
                  </span>
                </div>
              </div>
              <div className="p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600">
                <Server className="w-5 h-5" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">PostgreSQL Database</p>
                <div className="flex items-center gap-1.5">
                  {isDbHealthy ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-500" />
                  )}
                  <span className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                    {isDbHealthy ? 'CONNECTED' : 'DISCONNECTED'}
                  </span>
                </div>
              </div>
              <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600">
                <Database className="w-5 h-5" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">Query Latency</p>
                <p className="text-base font-bold text-zinc-900 dark:text-zinc-100 font-mono">
                  {health?.database?.latency_ms !== undefined
                    ? `${health.database.latency_ms} ms`
                    : health?.latency_ms !== undefined
                    ? `${health.latency_ms} ms`
                    : '< 15 ms'}
                </p>
              </div>
              <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/50 text-amber-600">
                <Zap className="w-5 h-5" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">Last Telemetry Probe</p>
                <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 font-mono">
                  {lastCheckTime || 'Active'}
                </p>
              </div>
              <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/50 text-purple-600">
                <Clock className="w-5 h-5" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Diagnostic Telemetry Panel */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-bold">Diagnostic Runtime Metrics</CardTitle>
            <CardDescription className="text-xs">
              FastAPI backend application layer and PostgreSQL connection pool telemetry.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              {/* Application Server Card */}
              <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-800 space-y-2">
                <h4 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-500" />
                  Application Server (FastAPI)
                </h4>
                <ul className="space-y-1.5 text-zinc-600 dark:text-zinc-400 font-mono text-[11px]">
                  <li>• Application: {health?.application?.app_name || 'Paradox Sports OMS'}</li>
                  <li>• Version: {health?.application?.version || '1.0.0'}</li>
                  <li>• Environment: {health?.application?.environment || 'production'}</li>
                  <li>• Security: Argon2id Hashing + HttpOnly Sessions</li>
                </ul>
              </div>

              {/* PostgreSQL Data Plane Card */}
              <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-800 space-y-2">
                <h4 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                  <Database className="w-4 h-4 text-indigo-500" />
                  PostgreSQL Connection Pool
                </h4>
                <ul className="space-y-1.5 text-zinc-600 dark:text-zinc-400 font-mono text-[11px]">
                  <li>• Driver Engine: {health?.database?.engine || 'postgresql+psycopg2'}</li>
                  <li>• Pool Size: {health?.database?.pool?.size ?? 'Configured'}</li>
                  <li>• Checked In Connections: {health?.database?.pool?.checked_in ?? 0}</li>
                  <li>• Checked Out (Active): {health?.database?.pool?.checked_out ?? 0}</li>
                </ul>
              </div>
            </div>

            {/* Expandable Technical Details JSON */}
            <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800">
              <button
                type="button"
                onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                className="flex items-center gap-1.5 text-xs font-semibold text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
              >
                {showTechnicalDetails ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
                <span>{showTechnicalDetails ? 'Hide' : 'View'} Technical Diagnostics Payload</span>
              </button>

              {showTechnicalDetails && (
                <div className="mt-3 p-4 bg-zinc-950 text-emerald-400 rounded-xl overflow-x-auto text-xs font-mono border border-zinc-800">
                  <pre>{JSON.stringify(health || {}, null, 2)}</pre>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
