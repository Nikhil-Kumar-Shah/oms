'use client';

/**
 * User Administration Workspace (/admin/users)
 * Full operational account provisioning, canonical role assignment,
 * vertical division membership, account status control, profile inspection,
 * and secure credential management.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { PasswordRequirements } from '@/components/ui/PasswordRequirements';
import { EmptyState } from '@/components/common/EmptyState';
import { VerticalSelector } from '@/components/selectors';
import { adminApi, organizationApi, eventsApi, eventTeamsApi, ApiException } from '@/lib/api';
import { UserResponse, CanonicalRole, AccountStatus, UserCreateInput, RoleDetail } from '@/types/user';
import { Vertical } from '@/types/organization';
import {
  UserCog,
  UserPlus,
  Search,
  Layers,
  RefreshCw,
  UserCheck,
  UserX,
  Edit3,
  KeyRound,
  Lock,
  Eye,
  Clock,
  Calendar,
} from 'lucide-react';

const CANONICAL_ROLES: { name: CanonicalRole; description: string }[] = [
  { name: 'ADMIN', description: 'System Administrator — technical and security authority' },
  { name: 'SPORTS_CORE', description: 'Executive Sports Core — supreme operational leadership' },
  { name: 'DEPUTY_CORE', description: 'Deputy Core — operational supervision and governance' },
  { name: 'SUPER_COORDINATOR', description: 'Super Coordinator — multi-vertical lead' },
  { name: 'COORDINATOR', description: 'Field Coordinator — operational task management' },
  { name: 'VOLUNTEER', description: 'Operational Volunteer — execution of assigned work' },
  { name: 'EVENT_TEAM', description: 'External Event Team — isolated tournament tenant' },
];

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');

  // Preloaded data
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [availableRoles, setAvailableRoles] = useState<RoleDetail[]>([]);

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [createMode, setCreateMode] = useState<'INTERNAL' | 'EVENT_TEAM'>('INTERNAL');
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Create Form State
  const [formData, setFormData] = useState({
    username: '',
    full_name: '',
    email: '',
    password: '',
    role: 'COORDINATOR' as CanonicalRole,
    vertical_id: '',
    // Event Team specific
    event_id: '',
    team_name: '',
    head_name: '',
    head_phone: '',
    head_email: '',
    notes: '',
  });

  // Action / Status Modal
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
  const [statusAction, setStatusAction] = useState<AccountStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState<boolean>(false);

  // Edit User Modal
  const [isEditOpen, setIsEditOpen] = useState<boolean>(false);
  const [editLoading, setEditLoading] = useState<boolean>(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ full_name: '', email: '' });

  // Role Assignment Modal
  const [isRoleOpen, setIsRoleOpen] = useState<boolean>(false);
  const [roleLoading, setRoleLoading] = useState<boolean>(false);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [selectedRoleName, setSelectedRoleName] = useState<CanonicalRole>('COORDINATOR');

  // Vertical Assignment Modal
  const [isVerticalOpen, setIsVerticalOpen] = useState<boolean>(false);
  const [verticalLoading, setVerticalLoading] = useState<boolean>(false);
  const [verticalError, setVerticalError] = useState<string | null>(null);
  const [assignVerticalId, setAssignVerticalId] = useState<string>('');
  const [assignIsPrimary, setAssignIsPrimary] = useState<boolean>(true);

  // Password Reset Modal
  const [isPasswordOpen, setIsPasswordOpen] = useState<boolean>(false);
  const [passwordLoading, setPasswordLoading] = useState<boolean>(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');

  // View Profile Modal
  const [isProfileOpen, setIsProfileOpen] = useState<boolean>(false);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch preloaded data
  useEffect(() => {
    organizationApi
      .listVerticals()
      .then((res) => setVerticals(res.items || []))
      .catch((err) => console.warn('Failed to load verticals:', err));

    adminApi
      .listRoles()
      .then((roles) => setAvailableRoles(roles || []))
      .catch((err) => console.warn('Failed to load roles:', err));
  }, []);

  // Authoritative User Listing
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await adminApi.listUsers({
        search: debouncedSearch.trim() || undefined,
        status_filter: statusFilter !== 'ALL' ? (statusFilter as AccountStatus) : undefined,
        role_filter: roleFilter !== 'ALL' ? roleFilter : undefined,
        limit: 100,
        offset: 0,
      });
      setUsers(res.items || []);
      setTotalCount(res.total || 0);
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`Failed to fetch user accounts: ${err.message} (${err.code})`);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, statusFilter, roleFilter]);

  useEffect(() => {
    let active = true;
    adminApi
      .listUsers({
        search: debouncedSearch.trim() || undefined,
        status_filter: statusFilter !== 'ALL' ? (statusFilter as AccountStatus) : undefined,
        role_filter: roleFilter !== 'ALL' ? roleFilter : undefined,
        limit: 100,
        offset: 0,
      })
      .then((res) => {
        if (active) {
          setUsers(res.items || []);
          setTotalCount(res.total || 0);
        }
      })
      .catch((err) => {
        if (active) {
          setErrorMsg(err instanceof Error ? err.message : 'Failed to fetch user accounts');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [debouncedSearch, statusFilter, roleFilter]);

  // Handle User Creation
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    if (createMode === 'EVENT_TEAM') {
      if (!formData.username.trim() || !formData.full_name.trim() || !formData.email.trim() || !formData.password) {
        setCreateError('Username, Full Name, Email Address, and Password are required for Event Team provisioning.');
        return;
      }
    } else {
      if (!formData.username.trim() || !formData.full_name.trim() || !formData.password) {
        setCreateError('Username, Full Name, and Password are required.');
        return;
      }
    }

    if (formData.password.length < 8) {
      setCreateError('Password must be at least 8 characters long.');
      return;
    }

    setCreateLoading(true);
    try {
      const targetRole = createMode === 'EVENT_TEAM' ? 'EVENT_TEAM' : formData.role;
      const matchedRole = availableRoles.find((r) => r.name === targetRole);
      let createdUsername = '';

      if (createMode === 'EVENT_TEAM') {
        const teamProfile = await eventTeamsApi.create({
          username: formData.username.trim().toLowerCase(),
          full_name: formData.full_name.trim(),
          email: formData.email.trim().toLowerCase(),
          password: formData.password,
          head_name: formData.head_name.trim() || undefined,
          head_phone: formData.head_phone.trim() || undefined,
        });
        createdUsername = teamProfile.username || formData.username;
        setSuccessMsg(`Successfully created Event Team account '@${createdUsername}' in Pending Activation state. Sports Core or Deputy Core must assign an Event and Head POC to activate.`);
      } else {
        if (!matchedRole) {
          setCreateError(`Target role '${targetRole}' is not registered in the system. Please refresh the page.`);
          setCreateLoading(false);
          return;
        }
        const payload: UserCreateInput = {
          username: formData.username.trim().toLowerCase(),
          full_name: formData.full_name.trim(),
          email: formData.email.trim() ? formData.email.trim().toLowerCase() : undefined,
          password: formData.password,
          role_ids: [matchedRole.id],
          vertical_ids: formData.vertical_id ? [formData.vertical_id] : undefined,
        };
        const newUser = await adminApi.createUser(payload);
        createdUsername = newUser.username;
        setSuccessMsg(`Successfully created account for '${createdUsername}' (${targetRole}).`);
      }
      setIsCreateModalOpen(false);
      setFormData({
        username: '',
        full_name: '',
        email: '',
        password: '',
        role: 'COORDINATOR',
        vertical_id: '',
        event_id: '',
        team_name: '',
        head_name: '',
        head_phone: '',
        head_email: '',
        notes: '',
      });

      await fetchUsers();
    } catch (err) {
      if (err instanceof ApiException) {
        setCreateError(err.message);
      } else if (err instanceof Error) {
        setCreateError(err.message);
      }
    } finally {
      setCreateLoading(false);
    }
  };

  // Handle Edit User
  const handleEditUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    setEditError(null);
    setEditLoading(true);

    try {
      await adminApi.updateUser(selectedUser.id, {
        full_name: editForm.full_name.trim() || undefined,
        email: editForm.email.trim() || undefined,
      });
      setSuccessMsg(`User '${selectedUser.username}' details updated successfully.`);
      setIsEditOpen(false);
      setSelectedUser(null);
      await fetchUsers();
    } catch (err) {
      if (err instanceof ApiException) {
        setEditError(err.message);
      } else if (err instanceof Error) {
        setEditError(err.message);
      }
    } finally {
      setEditLoading(false);
    }
  };

  // Handle Role Assignment
  const handleAssignRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    setRoleError(null);
    setRoleLoading(true);

    try {
      const targetRoleObj = availableRoles.find((r) => r.name === selectedRoleName);
      if (!targetRoleObj) {
        setRoleError(`Target role '${selectedRoleName}' was not found in canonical role registry. Please refresh the page.`);
        setRoleLoading(false);
        return;
      }

      await adminApi.assignRoles(selectedUser.id, [targetRoleObj.id]);
      setSuccessMsg(`Assigned role '${selectedRoleName}' to user '${selectedUser.username}'.`);
      setIsRoleOpen(false);
      setSelectedUser(null);
      await fetchUsers();
    } catch (err) {
      if (err instanceof ApiException) {
        setRoleError(err.message);
      } else if (err instanceof Error) {
        setRoleError(err.message);
      }
    } finally {
      setRoleLoading(false);
    }
  };

  // Handle Vertical Assignment
  const handleAssignVertical = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser || !assignVerticalId) return;
    setVerticalError(null);
    setVerticalLoading(true);

    try {
      await adminApi.assignVerticals(selectedUser.id, [
        { vertical_id: assignVerticalId, is_primary: assignIsPrimary },
      ]);
      setSuccessMsg(`Vertical assigned to user '${selectedUser.username}' successfully.`);
      setIsVerticalOpen(false);
      setSelectedUser(null);
      await fetchUsers();
    } catch (err) {
      if (err instanceof ApiException) {
        setVerticalError(err.message);
      } else if (err instanceof Error) {
        setVerticalError(err.message);
      }
    } finally {
      setVerticalLoading(false);
    }
  };

  // Handle Password Reset
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    setPasswordError(null);

    if (!newPassword || newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters long.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('New password and confirmation do not match.');
      return;
    }

    setPasswordLoading(true);
    try {
      await adminApi.resetPassword(selectedUser.id, newPassword);
      setSuccessMsg(`Password for user '${selectedUser.username}' has been securely reset.`);
      setIsPasswordOpen(false);
      setSelectedUser(null);
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      if (err instanceof ApiException) {
        setPasswordError(err.message);
      } else if (err instanceof Error) {
        setPasswordError(err.message);
      }
    } finally {
      setPasswordLoading(false);
    }
  };

  // Handle User Status Change (Enable / Disable)
  const handleUpdateStatus = async () => {
    if (!selectedUser || !statusAction) return;

    setStatusLoading(true);
    try {
      await adminApi.setUserStatus(selectedUser.id, statusAction);
      setSuccessMsg(`User '${selectedUser.username}' status updated to ${statusAction}.`);
      setSelectedUser(null);
      setStatusAction(null);
      await fetchUsers();
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`Status update failed: ${err.message}`);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setStatusLoading(false);
    }
  };

  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return 'Never';
    try {
      return new Date(dateStr).toLocaleString('en-US', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <AppShell requiredRoles={['ADMIN']} requiredPermission="users.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-purple-950/20 via-indigo-950/15 to-transparent border border-purple-200 dark:border-purple-800/40">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300">
                <UserCog className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                User Administration
              </h1>
              <Badge variant="default" size="sm">
                System Authority
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
              Provision operator identities, configure canonical role boundaries, assign verticals, and govern credential lifecycles.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchUsers}
              isLoading={loading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setCreateError(null);
                setIsCreateModalOpen(true);
              }}
              leftIcon={<UserPlus className="w-3.5 h-3.5" />}
            >
              Provision User
            </Button>
          </div>
        </div>

        {/* Alerts */}
        {errorMsg && (
          <Alert variant="danger" title="User Administration Error" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" title="Success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {/* Filter Controls Bar */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
              {/* Search Bar */}
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search by username, full name, or email..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Status Filter */}
              <div className="flex items-center gap-2">
                <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 shrink-0">
                  Status:
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="ACTIVE">Active</option>
                  <option value="DISABLED">Disabled</option>
                  <option value="SUSPENDED">Suspended</option>
                </select>
              </div>

              {/* Role Filter */}
              <div className="flex items-center gap-2">
                <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 shrink-0">
                  Role:
                </label>
                <select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  className="px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="ALL">All Roles</option>
                  {CANONICAL_ROLES.map((r) => (
                    <option key={r.name} value={r.name}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Authoritative User Accounts Table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-sm font-bold">Registered User Accounts</CardTitle>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Authoritative accounts in PostgreSQL ({totalCount} total)
              </p>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading && users.length === 0 ? (
              <div className="p-12 flex flex-col items-center justify-center gap-2 text-zinc-400">
                <Spinner size="md" />
                <p className="text-xs">Loading user registry...</p>
              </div>
            ) : users.length === 0 ? (
              <EmptyState
                icon={UserCog}
                title="No Users Found"
                description={
                  debouncedSearch || statusFilter !== 'ALL' || roleFilter !== 'ALL'
                    ? 'No user accounts match the current filter criteria.'
                    : 'No accounts are registered in the system.'
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-zinc-50 dark:bg-zinc-900/50 border-y border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 font-semibold uppercase tracking-wider text-[10px]">
                    <tr>
                      <th className="py-3 px-4">User Details</th>
                      <th className="py-3 px-4">Canonical Role</th>
                      <th className="py-3 px-4">Vertical Division</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Last Login</th>
                      <th className="py-3 px-4 text-right">Administrative Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60">
                    {users.map((u) => {
                      const primaryRole = u.roles[0]?.name;
                      const primaryVert = u.verticals.find((v) => v.is_primary) || u.verticals[0];

                      return (
                        <tr
                          key={u.id}
                          className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40 transition-colors"
                        >
                          <td className="py-3 px-4">
                            <div className="space-y-0.5">
                              <p className="font-semibold text-zinc-900 dark:text-zinc-100">
                                {u.full_name}
                              </p>
                              <div className="flex items-center gap-2 text-[11px] text-zinc-500 dark:text-zinc-400">
                                <span className="font-mono text-indigo-600 dark:text-indigo-400">
                                  @{u.username}
                                </span>
                                {u.email && <span>• {u.email}</span>}
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            {primaryRole ? (
                              <Badge role={primaryRole} size="sm" />
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-500 border border-zinc-200 dark:border-zinc-700">
                                Unassigned
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            {primaryVert ? (
                              <div className="flex items-center gap-1 text-zinc-700 dark:text-zinc-300">
                                <Layers className="w-3.5 h-3.5 text-indigo-500" />
                                <span className="font-medium">{primaryVert.name}</span>
                              </div>
                            ) : (
                              <span className="text-zinc-400 italic">Unassigned</span>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                u.account_status === 'ACTIVE'
                                  ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300'
                                  : primaryRole === 'EVENT_TEAM'
                                  ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300'
                                  : u.account_status === 'SUSPENDED'
                                  ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300'
                                  : 'bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300'
                              }`}
                            >
                              {primaryRole === 'EVENT_TEAM' && (u.account_status as string) !== 'ACTIVE'
                                ? 'PENDING ACTIVATION'
                                : u.account_status}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-zinc-500 dark:text-zinc-400 font-mono text-[11px]">
                            {formatDateTime(u.last_login_at)}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1">
                              {/* View Profile */}
                              <button
                                type="button"
                                title="View User Profile"
                                onClick={() => {
                                  setSelectedUser(u);
                                  setIsProfileOpen(true);
                                }}
                                className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 dark:hover:text-zinc-100 transition-colors"
                              >
                                <Eye className="w-3.5 h-3.5" />
                              </button>

                              {/* Edit Details */}
                              <button
                                type="button"
                                title="Edit User Details"
                                onClick={() => {
                                  setSelectedUser(u);
                                  setEditForm({ full_name: u.full_name, email: u.email || '' });
                                  setEditError(null);
                                  setIsEditOpen(true);
                                }}
                                className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 dark:hover:text-zinc-100 transition-colors"
                              >
                                <Edit3 className="w-3.5 h-3.5" />
                              </button>

                              {/* Change Role */}
                              <button
                                type="button"
                                title="Assign / Change Role"
                                onClick={() => {
                                  setSelectedUser(u);
                                  setSelectedRoleName((u.roles[0]?.name as CanonicalRole) || 'COORDINATOR');
                                  setRoleError(null);
                                  setIsRoleOpen(true);
                                }}
                                className="p-1.5 rounded-lg text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/40 transition-colors"
                              >
                                <KeyRound className="w-3.5 h-3.5" />
                              </button>

                              {/* Assign Vertical */}
                              <button
                                type="button"
                                title="Assign Vertical Division"
                                onClick={() => {
                                  setSelectedUser(u);
                                  setAssignVerticalId(u.verticals[0]?.id || '');
                                  setAssignIsPrimary(true);
                                  setVerticalError(null);
                                  setIsVerticalOpen(true);
                                }}
                                className="p-1.5 rounded-lg text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 transition-colors"
                              >
                                <Layers className="w-3.5 h-3.5" />
                              </button>

                              {/* Reset Password */}
                              <button
                                type="button"
                                title="Reset User Password"
                                onClick={() => {
                                  setSelectedUser(u);
                                  setNewPassword('');
                                  setConfirmPassword('');
                                  setPasswordError(null);
                                  setIsPasswordOpen(true);
                                }}
                                className="p-1.5 rounded-lg text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-colors"
                              >
                                <Lock className="w-3.5 h-3.5" />
                              </button>

                              {/* Enable / Disable */}
                              {u.account_status === 'ACTIVE' ? (
                                <button
                                  type="button"
                                  title="Disable Account"
                                  onClick={() => {
                                    setSelectedUser(u);
                                    setStatusAction('DISABLED');
                                  }}
                                  className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                                >
                                  <UserX className="w-3.5 h-3.5" />
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  title="Enable Account"
                                  onClick={() => {
                                    setSelectedUser(u);
                                    setStatusAction('ACTIVE');
                                  }}
                                  className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 transition-colors"
                                >
                                  <UserCheck className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ------------------------------------------------------------------ */}
        {/* Modals                                                             */}
        {/* ------------------------------------------------------------------ */}

        {/* 1. Provision User Modal */}
        <Modal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          title="Provision Operational User Account"
          description="Create a secure identity and configure its role architecture."
        >
          <form onSubmit={handleCreateUser} className="space-y-4 pb-28">
            {createError && (
              <Alert variant="danger" title="Provisioning Failed">
                {createError}
              </Alert>
            )}

            {/* Mode Switcher */}
            <div className="flex items-center p-1 rounded-xl bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700">
              <button
                type="button"
                onClick={() => setCreateMode('INTERNAL')}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  createMode === 'INTERNAL'
                    ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                    : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
                }`}
              >
                Internal Operations / Volunteer
              </button>
              <button
                type="button"
                onClick={() => setCreateMode('EVENT_TEAM')}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  createMode === 'EVENT_TEAM'
                    ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs'
                    : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
                }`}
              >
                External Event Team (Isolated)
              </button>
            </div>

            {/* Form Fields based on Mode */}
            {createMode === 'INTERNAL' ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input
                    label="Username"
                    required
                    placeholder="e.g. coordinator_field"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    helperText="Unique login identifier (alphanumeric, lowercase)"
                  />
                  <Input
                    label="Full Name"
                    required
                    placeholder="e.g. Jane Doe"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input
                    label="Email Address"
                    type="email"
                    placeholder="e.g. jane@paradoxsports.org"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                  <Input
                    label="Password"
                    type="password"
                    required
                    placeholder="Min 8 characters"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    helperText="Complexity: uppercase, lowercase, number, symbol"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                      Canonical Role <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={formData.role}
                      onChange={(e) => setFormData({ ...formData, role: e.target.value as CanonicalRole })}
                      className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    >
                      {CANONICAL_ROLES.filter((r) => r.name !== 'EVENT_TEAM').map((r) => (
                        <option key={r.name} value={r.name}>
                          {r.name} — {r.description}
                        </option>
                      ))}
                    </select>
                  </div>

                  <VerticalSelector
                    label="Primary Vertical Division"
                    placeholder="Select Vertical Division..."
                    value={formData.vertical_id}
                    onChange={(val) => setFormData({ ...formData, vertical_id: val || '' })}
                  />
                </div>
              </>
            ) : (
              /* External Event Team (Isolated) Mode */
              <>
                <div className="p-3 bg-purple-50/50 dark:bg-purple-950/20 rounded-xl border border-purple-100 dark:border-purple-900/30 text-xs text-purple-800 dark:text-purple-300">
                  <p className="font-semibold">Event Team Identity Provisioning (Pending Activation)</p>
                  <p className="text-[11px] text-purple-600 dark:text-purple-400 mt-0.5">
                    Provisions an Event Team account in an Inactive / Pending Activation state. Credentials are created, but access is blocked (HTTP 403) until Sports Core or Deputy Core assigns an active Event and designated Head POC.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input
                    label="Username"
                    required
                    placeholder="e.g. team_phoenix"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    helperText="Unique login identifier (alphanumeric, lowercase)"
                  />
                  <Input
                    label="Full Name"
                    required
                    placeholder="e.g. Phoenix Hockey Squad"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input
                    label="Email Address"
                    type="email"
                    required
                    placeholder="e.g. contact@phoenixhockey.org"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                  <Input
                    label="Password"
                    type="password"
                    required
                    placeholder="Min 8 characters"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    helperText="Complexity: uppercase, lowercase, number, symbol"
                  />
                </div>

                {/* Optional Metadata */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                  <Input
                    label="Event Team Head Name"
                    placeholder="e.g. Coach / Head of Contingent"
                    value={formData.head_name}
                    onChange={(e) => setFormData({ ...formData, head_name: e.target.value })}
                    helperText="Optional operational contact"
                  />
                  <Input
                    label="Event Team Head Phone Number"
                    placeholder="e.g. +1 555-0199"
                    value={formData.head_phone}
                    onChange={(e) => setFormData({ ...formData, head_phone: e.target.value })}
                    helperText="Optional direct mobile / WhatsApp"
                  />
                </div>
              </>
            )}

            {/* Footer Buttons */}
            <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsCreateModalOpen(false)}
                disabled={createLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={createLoading}
                leftIcon={<UserPlus className="w-3.5 h-3.5" />}
              >
                Provision Account
              </Button>
            </div>
          </form>
        </Modal>

        {/* 2. Edit User Modal */}
        <Modal
          isOpen={isEditOpen && !!selectedUser}
          onClose={() => {
            setIsEditOpen(false);
            setSelectedUser(null);
          }}
          title={`Edit User: @${selectedUser?.username}`}
          description="Update account details and contact information."
        >
          <form onSubmit={handleEditUser} className="space-y-4">
            {editError && (
              <Alert variant="danger" title="Update Failed">
                {editError}
              </Alert>
            )}

            <Input
              label="Full Name"
              required
              value={editForm.full_name}
              onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
            />

            <Input
              label="Email Address"
              type="email"
              value={editForm.email}
              onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
            />

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setIsEditOpen(false);
                  setSelectedUser(null);
                }}
                disabled={editLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={editLoading}
              >
                Save Changes
              </Button>
            </div>
          </form>
        </Modal>

        {/* 3. Assign / Change Role Modal */}
        <Modal
          isOpen={isRoleOpen && !!selectedUser}
          onClose={() => {
            setIsRoleOpen(false);
            setSelectedUser(null);
          }}
          title={`Change Role: @${selectedUser?.username}`}
          description="Changing a user's canonical role alters their entire permission boundary."
        >
          <form onSubmit={handleAssignRole} className="space-y-4">
            {roleError && (
              <Alert variant="danger" title="Role Assignment Failed">
                {roleError}
              </Alert>
            )}

            <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300">
              <strong>Privilege Notice:</strong> Role assignment is server-authoritative and immediately changes the user&apos;s effective capabilities across all operational modules.
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                Select Canonical Role
              </label>
              <select
                value={selectedRoleName}
                onChange={(e) => setSelectedRoleName(e.target.value as CanonicalRole)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
              >
                {CANONICAL_ROLES.map((r) => (
                  <option key={r.name} value={r.name}>
                    {r.name} — {r.description}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setIsRoleOpen(false);
                  setSelectedUser(null);
                }}
                disabled={roleLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={roleLoading}
                leftIcon={<KeyRound className="w-3.5 h-3.5" />}
              >
                Confirm Role Change
              </Button>
            </div>
          </form>
        </Modal>

        {/* 4. Assign Vertical Modal */}
        <Modal
          isOpen={isVerticalOpen && !!selectedUser}
          onClose={() => {
            setIsVerticalOpen(false);
            setSelectedUser(null);
          }}
          title={`Assign Vertical: @${selectedUser?.username}`}
          description="Configure vertical division membership for operational scoping."
        >
          <form onSubmit={handleAssignVertical} className="space-y-4">
            {verticalError && (
              <Alert variant="danger" title="Vertical Assignment Failed">
                {verticalError}
              </Alert>
            )}

            <VerticalSelector
              label="Vertical Division"
              required
              placeholder="Select vertical division..."
              value={assignVerticalId}
              onChange={(val) => setAssignVerticalId(val || '')}
            />

            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="is_primary_checkbox"
                checked={assignIsPrimary}
                onChange={(e) => setAssignIsPrimary(e.target.checked)}
                className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-zinc-300 dark:border-zinc-700"
              />
              <label htmlFor="is_primary_checkbox" className="text-xs text-zinc-700 dark:text-zinc-300 font-medium">
                Set as Primary Vertical Division
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setIsVerticalOpen(false);
                  setSelectedUser(null);
                }}
                disabled={verticalLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={verticalLoading}
                leftIcon={<Layers className="w-3.5 h-3.5" />}
              >
                Save Vertical Assignment
              </Button>
            </div>
          </form>
        </Modal>

        {/* 5. Password Reset Modal */}
        <Modal
          isOpen={isPasswordOpen && !!selectedUser}
          onClose={() => {
            setIsPasswordOpen(false);
            setSelectedUser(null);
          }}
          title={`Reset Password: @${selectedUser?.username}`}
          description="Set a new password for the target account. Active user sessions will be revoked."
        >
          <form onSubmit={handleResetPassword} className="space-y-4">
            {passwordError && (
              <Alert variant="danger" title="Reset Failed">
                {passwordError}
              </Alert>
            )}

            <div className="p-3 rounded-xl bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 text-xs text-purple-800 dark:text-purple-300">
              <strong>Security Protocol:</strong> Existing password hashes are never revealed. The new password will be hashed with Argon2id and an immutable audit record will be logged.
            </div>

            <Input
              label="New Password"
              type="password"
              required
              placeholder="Min 8 characters"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />

            {/* PASSWORD COMBINATION GUIDE & CHECKLIST */}
            <PasswordRequirements
              password={newPassword}
              confirmPassword={confirmPassword}
            />

            <Input
              label="Confirm New Password"
              type="password"
              required
              placeholder="Re-enter new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setIsPasswordOpen(false);
                  setSelectedUser(null);
                }}
                disabled={passwordLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={passwordLoading}
                leftIcon={<Lock className="w-3.5 h-3.5" />}
              >
                Reset Password
              </Button>
            </div>
          </form>
        </Modal>

        {/* 6. View User Profile Modal */}
        <Modal
          isOpen={isProfileOpen && !!selectedUser}
          onClose={() => {
            setIsProfileOpen(false);
            setSelectedUser(null);
          }}
          title={`User Profile: ${selectedUser?.full_name}`}
          description={`@${selectedUser?.username}`}
        >
          {selectedUser && (
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3 p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Username</span>
                  <span className="font-mono font-semibold text-zinc-900 dark:text-zinc-100">
                    @{selectedUser.username}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Account Status</span>
                  <span className="font-bold text-zinc-900 dark:text-zinc-100">
                    {selectedUser.account_status}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Email</span>
                  <span className="text-zinc-900 dark:text-zinc-100">
                    {selectedUser.email || 'Not provided'}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 block font-medium">Canonical Role</span>
                  <div className="mt-0.5">
                    {selectedUser.roles[0]?.name ? (
                      <Badge role={selectedUser.roles[0].name} size="sm" />
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-500 border border-zinc-200 dark:border-zinc-700">
                        Unassigned
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Verticals */}
              <div className="space-y-1.5">
                <span className="text-zinc-500 dark:text-zinc-400 font-semibold uppercase tracking-wider text-[10px]">
                  Assigned Verticals
                </span>
                {selectedUser.verticals && selectedUser.verticals.length > 0 ? (
                  <div className="space-y-1">
                    {selectedUser.verticals.map((v) => (
                      <div
                        key={v.id}
                        className="flex items-center justify-between p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800"
                      >
                        <span className="font-medium text-zinc-900 dark:text-zinc-100">{v.name}</span>
                        {v.is_primary && (
                          <span className="text-[10px] bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 px-1.5 py-0.5 rounded font-bold">
                            Primary
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-zinc-400 italic">No vertical divisions assigned.</p>
                )}
              </div>

              {/* Activity Timestamps */}
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-zinc-100 dark:border-zinc-800 text-[11px]">
                <div className="flex items-center gap-1.5 text-zinc-500 dark:text-zinc-400">
                  <Clock className="w-3.5 h-3.5 text-purple-500" />
                  <span>Last Login: <strong>{formatDateTime(selectedUser.last_login_at)}</strong></span>
                </div>
                <div className="flex items-center gap-1.5 text-zinc-500 dark:text-zinc-400">
                  <Calendar className="w-3.5 h-3.5 text-indigo-500" />
                  <span>Created: <strong>{formatDateTime(selectedUser.created_at)}</strong></span>
                </div>
              </div>

              <div className="flex justify-end pt-3 border-t border-zinc-100 dark:border-zinc-800">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setIsProfileOpen(false);
                    setSelectedUser(null);
                  }}
                >
                  Close
                </Button>
              </div>
            </div>
          )}
        </Modal>

        {/* 7. Status Confirmation Modal */}
        <Modal
          isOpen={!!selectedUser && !!statusAction}
          onClose={() => {
            setSelectedUser(null);
            setStatusAction(null);
          }}
          title="Confirm Account Status Transition"
          description={`Are you sure you want to transition '${selectedUser?.username}' to ${statusAction}?`}
        >
          <div className="space-y-4">
            <p className="text-xs text-zinc-600 dark:text-zinc-400">
              {statusAction === 'DISABLED'
                ? 'Disabling this account will revoke active session tokens and prevent future logins until re-enabled.'
                : 'Enabling this account will restore immediate login and authorized operational access.'}
            </p>

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSelectedUser(null);
                  setStatusAction(null);
                }}
                disabled={statusLoading}
              >
                Cancel
              </Button>
              <Button
                variant={statusAction === 'DISABLED' ? 'danger' : 'primary'}
                size="sm"
                isLoading={statusLoading}
                onClick={handleUpdateStatus}
              >
                Confirm {statusAction}
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </AppShell>
  );
}
