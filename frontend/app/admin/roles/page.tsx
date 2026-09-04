'use client';

/**
 * Roles & Permissions Management (/admin/roles)
 * RBAC configuration, canonical role boundaries, and system permission registry inspection.
 */

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { EmptyState } from '@/components/common/EmptyState';
import { adminApi, ApiException } from '@/lib/api';
import { RoleDetail, PermissionSummary } from '@/types/user';
import {
  KeyRound,
  CheckCircle2,
  Lock,
  RefreshCw,
  Search,
  Users,
} from 'lucide-react';

export default function AdminRolesPage() {
  const [roles, setRoles] = useState<RoleDetail[]>([]);
  const [permissions, setPermissions] = useState<PermissionSummary[]>([]);
  const [selectedRole, setSelectedRole] = useState<RoleDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [permSearch, setPermSearch] = useState<string>('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [rolesData, permsData] = await Promise.all([
        adminApi.listRoles(),
        adminApi.listPermissions(),
      ]);
      setRoles(rolesData || []);
      setPermissions(permsData || []);
      if (rolesData && rolesData.length > 0 && !selectedRole) {
        setSelectedRole(rolesData[0]);
      }
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`Failed to load RBAC data: ${err.message}`);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [selectedRole]);

  useEffect(() => {
    let active = true;
    Promise.all([adminApi.listRoles(), adminApi.listPermissions()])
      .then(([rolesData, permsData]) => {
        if (active) {
          setRoles(rolesData || []);
          setPermissions(permsData || []);
          if (rolesData && rolesData.length > 0) {
            setSelectedRole((prev) => prev || rolesData[0]);
          }
        }
      })
      .catch((err) => {
        if (active) {
          setErrorMsg(err instanceof Error ? err.message : 'Failed to load RBAC data');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  // Group permissions by category
  const groupedPermissions: Record<string, PermissionSummary[]> = {};
  permissions.forEach((p) => {
    const cat = p.category || 'General';
    if (!groupedPermissions[cat]) {
      groupedPermissions[cat] = [];
    }
    groupedPermissions[cat].push(p);
  });

  const selectedRolePerms =
    selectedRole?.permissions ||
    (selectedRole?.role_permissions || []).map((rp) => rp.permission).filter(Boolean);
  const selectedRolePermCodes = new Set((selectedRolePerms || []).map((p) => p.code));

  return (
    <AppShell requiredRoles={['ADMIN']} requiredPermission="roles.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-amber-950/20 via-orange-950/15 to-transparent border border-amber-200 dark:border-amber-800/40">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300">
                <KeyRound className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                Roles & Permissions Registry
              </h1>
              <Badge variant="default" size="sm">
                Canonical RBAC
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
              Canonical system permission registry and authority scope definitions. Permission definitions are system-defined and immutable.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            isLoading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh Registry
          </Button>
        </div>

        {errorMsg && (
          <Alert variant="danger" title="RBAC Error" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        {loading && roles.length === 0 ? (
          <div className="p-16 flex flex-col items-center justify-center gap-2 text-zinc-400">
            <Spinner size="md" />
            <p className="text-xs">Loading RBAC architecture...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Roles List */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                Canonical Roles ({roles.length})
              </h3>

              <div className="space-y-2">
                {roles.map((r) => {
                  const isSelected = selectedRole?.id === r.id;
                  const permCount = r.permissions?.length || r.role_permissions?.length || 0;

                  return (
                    <div
                      key={r.id}
                      onClick={() => setSelectedRole(r)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? 'border-amber-400 dark:border-amber-600 bg-amber-50/50 dark:bg-amber-950/30 shadow-xs'
                          : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-zinc-300 dark:hover:border-zinc-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge role={r.name} size="sm" />
                          {r.is_system && (
                            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                              System Core
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] font-mono text-zinc-500 dark:text-zinc-400">
                          {permCount} perms
                        </span>
                      </div>
                      <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-2 line-clamp-2">
                        {r.description}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Selected Role Capabilities Detail */}
            <div className="lg:col-span-2 space-y-4">
              {selectedRole ? (
                <Card>
                  <CardHeader className="border-b border-zinc-100 dark:border-zinc-800 pb-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <CardTitle className="text-base font-bold">{selectedRole.name}</CardTitle>
                          <Badge role={selectedRole.name} size="sm" />
                        </div>
                        <CardDescription className="text-xs">
                          {selectedRole.description}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        <Link href={`/admin/users?role_filter=${selectedRole.name}`}>
                          <Button size="sm" variant="outline" leftIcon={<Users className="w-3.5 h-3.5" />}>
                            View Assigned Users
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="p-4 space-y-6">
                    {/* Permission Search Bar */}
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                      <input
                        type="text"
                        placeholder="Search permissions by code or category..."
                        value={permSearch}
                        onChange={(e) => setPermSearch(e.target.value)}
                        className="w-full pl-8 pr-4 py-1.5 text-xs rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
                      />
                    </div>

                    {/* Grouped Permission Badges */}
                    <div className="space-y-4">
                      {Object.entries(groupedPermissions).map(([category, perms]) => {
                        const filtered = perms.filter(
                          (p) =>
                            p.code.toLowerCase().includes(permSearch.toLowerCase()) ||
                            category.toLowerCase().includes(permSearch.toLowerCase())
                        );

                        if (filtered.length === 0) return null;

                        return (
                          <div key={category} className="space-y-2">
                            <h4 className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                              {category}
                            </h4>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {filtered.map((p) => {
                                const hasPerm = selectedRolePermCodes.has(p.code);

                                return (
                                  <div
                                    key={p.id}
                                    className={`p-2 rounded-lg border text-xs flex items-center justify-between ${
                                      hasPerm
                                        ? 'border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/50 dark:bg-emerald-950/20 text-emerald-950 dark:text-emerald-200'
                                        : 'border-zinc-100 dark:border-zinc-800 bg-zinc-50/30 dark:bg-zinc-900/30 text-zinc-400 dark:text-zinc-600 opacity-60'
                                    }`}
                                  >
                                    <div className="space-y-0.5 truncate mr-2">
                                      <p className="font-mono text-[11px] font-semibold truncate">
                                        {p.code}
                                      </p>
                                      <p className="text-[10px] text-zinc-500 dark:text-zinc-400 truncate">
                                        {p.description}
                                      </p>
                                    </div>
                                    {hasPerm ? (
                                      <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                                    ) : (
                                      <Lock className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <EmptyState
                  icon={KeyRound}
                  title="Select a Role"
                  description="Choose a canonical role from the left column to inspect its effective permissions."
                />
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
