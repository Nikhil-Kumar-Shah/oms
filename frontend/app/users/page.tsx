'use client';

/**
 * Operational User Directory (/users)
 * Scoped read-only directory for operators to discover team members, roles,
 * vertical divisions, and operational contact metadata across authorized scopes.
 */

import React, { useState, useEffect } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { StatusBadge } from '@/components/common/StatusBadge';
import { EmptyState } from '@/components/common/EmptyState';
import { useAuth } from '@/hooks/useAuth';
import { organizationApi, ApiException } from '@/lib/api';
import { UserResponse } from '@/types/user';
import { Vertical } from '@/types/organization';
import { formatAuditDateTime } from '@/lib/utils';
import {
  Users,
  Search,
  RefreshCw,
  Mail,
  Calendar,
  Layers,
  Shield,
  Eye,
  CheckCircle2,
  Clock,
} from 'lucide-react';

const CANONICAL_ROLE_LABELS: Record<string, string> = {
  ADMIN: 'System Administration',
  SPORTS_CORE: 'Sports Core',
  DEPUTY_CORE: 'Deputy Core',
  SUPER_COORDINATOR: 'Super Coordinator',
  COORDINATOR: 'Coordinator',
  VOLUNTEER: 'Volunteer',
  EVENT_TEAM: 'Event Team',
};

const ROLE_BADGE_STYLES: Record<string, { bg: string; text: string }> = {
  ADMIN: { bg: 'bg-rose-100 dark:bg-rose-950/60', text: 'text-rose-700 dark:text-rose-300' },
  SPORTS_CORE: { bg: 'bg-indigo-100 dark:bg-indigo-950/60', text: 'text-indigo-700 dark:text-indigo-300' },
  DEPUTY_CORE: { bg: 'bg-purple-100 dark:bg-purple-950/60', text: 'text-purple-700 dark:text-purple-300' },
  SUPER_COORDINATOR: { bg: 'bg-sky-100 dark:bg-sky-950/60', text: 'text-sky-700 dark:text-sky-300' },
  COORDINATOR: { bg: 'bg-emerald-100 dark:bg-emerald-950/60', text: 'text-emerald-700 dark:text-emerald-300' },
  VOLUNTEER: { bg: 'bg-amber-100 dark:bg-amber-950/60', text: 'text-amber-700 dark:text-amber-300' },
  EVENT_TEAM: { bg: 'bg-teal-100 dark:bg-teal-950/60', text: 'text-teal-700 dark:text-teal-300' },
};

export default function UserDirectoryPage() {
  const { user: currentUser } = useAuth();

  const [users, setUsers] = useState<UserResponse[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Multi-dimensional filter states
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');
  const [verticalFilter, setVerticalFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ACTIVE');

  // Selected User Detail Modal
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Load Verticals for dropdown
  useEffect(() => {
    organizationApi
      .listVerticals({ status: 'ACTIVE' })
      .then((res) => setVerticals(res.items || []))
      .catch(() => {});
  }, []);

  // Fetch Users based on multi-dimensional filters
  useEffect(() => {
    let ignore = false;
    async function loadUsers() {
      try {
        const params: {
          search?: string;
          role_filter?: string;
          vertical_id?: string;
          status_filter?: string;
          limit: number;
        } = {
          limit: 100,
        };

        if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
        if (roleFilter !== 'ALL') params.role_filter = roleFilter;
        if (verticalFilter !== 'ALL') params.vertical_id = verticalFilter;
        if (statusFilter !== 'ALL') params.status_filter = statusFilter;

        const res = await organizationApi.searchUsers(params);
        if (!ignore) {
          setUsers(res.items || []);
          setTotalCount(res.total || 0);
          setLoading(false);
        }
      } catch (err) {
        if (!ignore) {
          if (err instanceof ApiException) setErrorMsg(err.message);
          else if (err instanceof Error) setErrorMsg(err.message);
          setLoading(false);
        }
      }
    }

    loadUsers();
    return () => {
      ignore = true;
    };
  }, [debouncedSearch, roleFilter, verticalFilter, statusFilter, refreshTrigger]);

  const handleRefresh = () => {
    setLoading(true);
    setErrorMsg(null);
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <AppShell requiredPermission="users.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <Users className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              User Directory
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              Operational roster of active operators, leadership roles, and vertical divisions.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={loading}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Error Alert */}
        {errorMsg && (
          <Alert variant="danger">
            {errorMsg}
          </Alert>
        )}

        {/* Multi-Dimensional Filter Toolbar */}
        <Card>
          <CardContent className="p-4 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Search */}
              <div className="relative">
                <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 block mb-1.5">
                  Search Operators
                </label>
                <div className="relative">
                  <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <Input
                    type="text"
                    placeholder="Search name, @username..."
                    className="pl-9 h-10 text-xs"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              </div>

              {/* Role Filter */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 block mb-1.5">
                  Role / Governance Level
                </label>
                <select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  className="w-full h-10 px-3 py-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 font-medium"
                >
                  <option value="ALL">All Roles</option>
                  <option value="ADMIN">System Administration</option>
                  <option value="SPORTS_CORE">Sports Core</option>
                  <option value="DEPUTY_CORE">Deputy Core</option>
                  <option value="SUPER_COORDINATOR">Super Coordinator</option>
                  <option value="COORDINATOR">Coordinator</option>
                  <option value="VOLUNTEER">Volunteer</option>
                  <option value="EVENT_TEAM">Event Team</option>
                </select>
              </div>

              {/* Vertical Filter */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 block mb-1.5">
                  Vertical Division
                </label>
                <select
                  value={verticalFilter}
                  onChange={(e) => setVerticalFilter(e.target.value)}
                  className="w-full h-10 px-3 py-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 font-medium"
                >
                  <option value="ALL">All Vertical Divisions</option>
                  {verticals.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Account Status Filter */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 block mb-1.5">
                  Account Status
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full h-10 px-3 py-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 font-medium"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="ACTIVE">Active Accounts</option>
                  <option value="DISABLED">Disabled Accounts</option>
                  <option value="SUSPENDED">Suspended Accounts</option>
                  <option value="ARCHIVED">Archived Accounts</option>
                </select>
              </div>
            </div>

            {/* Active Filters Summary */}
            <div className="flex items-center justify-between pt-2 border-t border-zinc-100 dark:border-zinc-800/60 text-xs text-zinc-500">
              <div className="flex items-center gap-2">
                <span>Displaying <strong>{users.length}</strong> of <strong>{totalCount}</strong> operators</span>
                {(debouncedSearch || roleFilter !== 'ALL' || verticalFilter !== 'ALL' || statusFilter !== 'ACTIVE') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[11px] text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 px-2"
                    onClick={() => {
                      setSearchTerm('');
                      setRoleFilter('ALL');
                      setVerticalFilter('ALL');
                      setStatusFilter('ACTIVE');
                    }}
                  >
                    Reset Filters
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* User Table List */}
        {loading ? (
          <div className="flex justify-center p-12">
            <Spinner size="lg" />
          </div>
        ) : users.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No Operators Found"
            description="No users matched your search and filter criteria. Try adjusting your filter parameters."
          />
        ) : (
          <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30 text-zinc-500 font-bold uppercase tracking-wider text-[10px]">
                    <th className="py-3 px-4">Operator</th>
                    <th className="py-3 px-4">Role</th>
                    <th className="py-3 px-4">Vertical Divisions</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Last Login</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {users.map((u) => {
                    const primaryRole = u.roles[0]?.name || 'VOLUNTEER';
                    const badgeStyle = ROLE_BADGE_STYLES[primaryRole] || {
                      bg: 'bg-zinc-100 dark:bg-zinc-800',
                      text: 'text-zinc-700 dark:text-zinc-300',
                    };
                    const isSelf = currentUser?.id === u.id;

                    return (
                      <tr
                        key={u.id}
                        className="hover:bg-zinc-50 dark:hover:bg-zinc-800/40 transition-colors"
                      >
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-linear-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-xs uppercase shadow-xs shrink-0">
                              {u.full_name?.charAt(0) || u.username.charAt(0)}
                            </div>
                            <div className="min-w-0">
                              <div className="font-bold text-zinc-900 dark:text-zinc-100 truncate flex items-center gap-1.5">
                                {u.full_name || u.username}
                                {isSelf && (
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300">
                                    You
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-zinc-500 dark:text-zinc-400 truncate">
                                @{u.username}
                              </div>
                            </div>
                          </div>
                        </td>

                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-bold ${badgeStyle.bg} ${badgeStyle.text}`}
                          >
                            {CANONICAL_ROLE_LABELS[primaryRole] || primaryRole}
                          </span>
                        </td>

                        <td className="py-3.5 px-4">
                          <div className="flex flex-wrap gap-1 max-w-xs">
                            {u.verticals.length > 0 ? (
                              u.verticals.map((v) => (
                                <span
                                  key={v.id}
                                  className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${
                                    v.is_primary
                                      ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-bold border border-indigo-200 dark:border-indigo-800/60'
                                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400'
                                  }`}
                                >
                                  {v.name}
                                </span>
                              ))
                            ) : (
                              <span className="text-zinc-400 text-[11px] italic">No vertical</span>
                            )}
                          </div>
                        </td>

                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <StatusBadge status={u.account_status} />
                        </td>

                        <td className="py-3.5 px-4 whitespace-nowrap text-[11px] text-zinc-500">
                          {u.last_login_at ? formatAuditDateTime(u.last_login_at) : 'Never'}
                        </td>

                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs font-semibold px-2.5"
                            onClick={() => setSelectedUser(u)}
                            leftIcon={<Eye className="w-3.5 h-3.5" />}
                          >
                            View
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Read-Only User Detail Modal */}
        {selectedUser && (
          <Modal
            isOpen={true}
            onClose={() => setSelectedUser(null)}
            title="Operator Profile Details"
            size="lg"
          >
            <div className="space-y-6">
              {/* Header Info */}
              <div className="flex items-center gap-4 p-4 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-800">
                <div className="w-14 h-14 rounded-2xl bg-linear-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-xl uppercase shadow-md shrink-0">
                  {selectedUser.full_name?.charAt(0) || selectedUser.username.charAt(0)}
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100 truncate">
                    {selectedUser.full_name || selectedUser.username}
                  </h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    @{selectedUser.username}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <StatusBadge status={selectedUser.account_status} />
                    {selectedUser.roles[0] && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300">
                        {CANONICAL_ROLE_LABELS[selectedUser.roles[0].name] || selectedUser.roles[0].name}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Grid Metadata */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="p-3.5 rounded-xl bg-zinc-50/60 dark:bg-zinc-800/30 border border-zinc-200/80 dark:border-zinc-800 space-y-1">
                  <span className="font-bold text-zinc-500 uppercase text-[10px] flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5 text-zinc-400" />
                    Email Address
                  </span>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">
                    {selectedUser.email || 'No email provided'}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-zinc-50/60 dark:bg-zinc-800/30 border border-zinc-200/80 dark:border-zinc-800 space-y-1">
                  <span className="font-bold text-zinc-500 uppercase text-[10px] flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-zinc-400" />
                    Last Active
                  </span>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">
                    {selectedUser.last_login_at ? formatAuditDateTime(selectedUser.last_login_at) : 'No recorded login'}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-zinc-50/60 dark:bg-zinc-800/30 border border-zinc-200/80 dark:border-zinc-800 space-y-1">
                  <span className="font-bold text-zinc-500 uppercase text-[10px] flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-zinc-400" />
                    Account Provisioned
                  </span>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">
                    {selectedUser.created_at ? formatAuditDateTime(selectedUser.created_at) : 'N/A'}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-zinc-50/60 dark:bg-zinc-800/30 border border-zinc-200/80 dark:border-zinc-800 space-y-1">
                  <span className="font-bold text-zinc-500 uppercase text-[10px] flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-zinc-400" />
                    Assigned Roles
                  </span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {selectedUser.roles.map((r) => (
                      <span
                        key={r.id}
                        className="px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                      >
                        {CANONICAL_ROLE_LABELS[r.name] || r.name}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Vertical Divisions Assigned */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-indigo-500" />
                  Assigned Vertical Divisions
                </label>
                <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800 space-y-2">
                  {selectedUser.verticals.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {selectedUser.verticals.map((v) => (
                        <div
                          key={v.id}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 text-xs"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                          <span className="font-semibold text-zinc-900 dark:text-zinc-100">{v.name}</span>
                          {v.is_primary && (
                            <span className="ml-1 text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300">
                              Primary
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-500 italic">No assigned vertical divisions.</p>
                  )}
                </div>
              </div>

              {/* Modal Footer */}
              <div className="flex justify-end pt-3 border-t border-zinc-100 dark:border-zinc-800">
                <Button variant="outline" size="sm" onClick={() => setSelectedUser(null)}>
                  Close
                </Button>
              </div>
            </div>
          </Modal>
        )}
      </div>
    </AppShell>
  );
}
