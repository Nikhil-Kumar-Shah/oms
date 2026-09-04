'use client';

/**
 * Minimal & Professional Administrator Control Plane.
 * Strictly permission-gated: Only shows administrative modules the user is authorized to access.
 * Zero governance or directive clutter.
 */

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { adminApi } from '@/lib/api';
import {
  UserCog,
  Layers,
  KeyRound,
  ShieldCheck,
  Activity,
  Sliders,
  ArrowRight,
  Server,
  Users,
} from 'lucide-react';

export const AdminWorkspace: React.FC = () => {
  const { hasPermission } = useAuth();
  const [stats, setStats] = useState<{
    totalUsers: number;
    activeUsers: number;
    activeVerticals: number;
    systemHealthy: boolean;
  }>({
    totalUsers: 0,
    activeUsers: 0,
    activeVerticals: 0,
    systemHealthy: true,
  });

  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let active = true;

    Promise.all([
      adminApi.listUsers({ limit: 1 }).catch(() => ({ total: 0 })),
      adminApi.listUsers({ status_filter: 'ACTIVE', limit: 1 }).catch(() => ({ total: 0 })),
      adminApi.listVerticals().catch(() => []),
      adminApi.getHealth().catch(() => ({ status: 'unknown' })),
    ])
      .then(([allUsers, activeUsers, verts, health]) => {
        if (active) {
          const activeVerts = Array.isArray(verts)
            ? verts.filter((v: { status?: string }) => v.status === 'ACTIVE').length
            : 0;

          setStats({
            totalUsers: allUsers.total || 0,
            activeUsers: activeUsers.total || 0,
            activeVerticals: activeVerts,
            systemHealthy: health.status === 'healthy' || health.status === 'ok',
          });
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  // Check permissions for each administrative module before including it
  const canReadUsers = hasPermission('users.read');
  const canReadVerticals = hasPermission('verticals.read');
  const canReadRoles = hasPermission('roles.read');
  const canReadConfig = hasPermission('config.read');
  const canReadAudit = hasPermission('audit.read');
  const canReadSystem = hasPermission('system.read');

  const adminModules = [];

  if (canReadUsers) {
    adminModules.push({
      title: 'User Accounts',
      href: '/admin/users',
      icon: <UserCog className="w-4 h-4 text-indigo-500" />,
      detail: `${stats.totalUsers} total • ${stats.activeUsers} active`,
    });
  }

  if (canReadVerticals) {
    adminModules.push({
      title: 'Vertical Divisions',
      href: '/admin/verticals',
      icon: <Layers className="w-4 h-4 text-blue-500" />,
      detail: `${stats.activeVerticals} active verticals`,
    });
  }

  if (canReadRoles) {
    adminModules.push({
      title: 'Roles & Permissions',
      href: '/admin/roles',
      icon: <KeyRound className="w-4 h-4 text-amber-500" />,
      detail: 'Canonical RBAC matrix',
    });
  }

  if (canReadConfig) {
    adminModules.push({
      title: 'System Settings',
      href: '/admin/config',
      icon: <Sliders className="w-4 h-4 text-purple-500" />,
      detail: 'Runtime SLA & policies',
    });
  }

  if (canReadAudit) {
    adminModules.push({
      title: 'Audit Center',
      href: '/admin/audit',
      icon: <ShieldCheck className="w-4 h-4 text-emerald-500" />,
      detail: 'Security ledger & logs',
    });
  }

  return (
    <div className="space-y-4">
      {/* Telemetry Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
            <Server className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 dark:text-zinc-100">
              System Infrastructure
            </h3>
            <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
              Health: {stats.systemHealthy ? 'Operational' : 'Attention Required'} • {stats.totalUsers} registered staff accounts
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {canReadSystem && (
            <Link href="/admin/health">
              <Button variant="outline" size="sm" leftIcon={<Activity className="w-3.5 h-3.5 text-emerald-500" />}>
                Diagnostics
              </Button>
            </Link>
          )}
          {canReadUsers && (
            <Link href="/admin/users">
              <Button variant="primary" size="sm" leftIcon={<Users className="w-3.5 h-3.5" />}>
                Manage Users
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Compact Administrative Modules Grid (Only showing permitted modules) */}
      {adminModules.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {adminModules.map((module) => (
            <Link
              key={module.href}
              href={module.href}
              className="group block p-3.5 rounded-xl border border-zinc-200/90 dark:border-zinc-800 bg-white dark:bg-zinc-900 transition-all hover:border-zinc-300 dark:hover:border-zinc-700 hover:shadow-xs"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 shrink-0">
                    {module.icon}
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                      {module.title}
                    </p>
                    <p className="text-[10px] text-zinc-500 dark:text-zinc-400">
                      {loading ? '—' : module.detail}
                    </p>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-zinc-400 group-hover:text-zinc-600 dark:group-hover:text-zinc-200 transition-transform group-hover:translate-x-0.5" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};
