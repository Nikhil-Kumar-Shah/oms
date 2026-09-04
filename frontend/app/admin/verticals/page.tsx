'use client';

/**
 * Vertical Divisions Administration (/admin/verticals)
 * Dynamic vertical creation, status control, lead coordinator assignment, and operational hierarchy.
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
import { EmptyState } from '@/components/common/EmptyState';
import { UserSelector } from '@/components/selectors';
import { adminApi, organizationApi, ApiException } from '@/lib/api';
import { Vertical } from '@/types/organization';
import {
  Layers,
  Plus,
  Search,
  UserCheck,
  ToggleLeft,
  ToggleRight,
  RefreshCw,
} from 'lucide-react';

export default function AdminVerticalsPage() {
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Create Modal State
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    name: '',
    slug: '',
    description: '',
    lead_coordinator_id: '',
  });

  const fetchVerticals = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const items = await adminApi.listVerticals();
      setVerticals(items || []);
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`Failed to load verticals: ${err.message}`);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    adminApi
      .listVerticals()
      .then((items) => {
        if (active) setVerticals(items || []);
      })
      .catch((err) => {
        if (active) {
          setErrorMsg(err instanceof Error ? err.message : 'Failed to load verticals');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleCreateVertical = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    if (!createForm.name.trim()) {
      setCreateError('Vertical division name is required.');
      return;
    }

    setCreateLoading(true);
    try {
      const slug =
        createForm.slug.trim() ||
        createForm.name.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 50);

      await adminApi.createVertical({
        name: createForm.name.trim(),
        slug,
        description: createForm.description.trim() || undefined,
        lead_coordinator_id: createForm.lead_coordinator_id || undefined,
      });

      setSuccessMsg(`Vertical division '${createForm.name}' created successfully.`);
      setIsCreateOpen(false);
      setCreateForm({ name: '', slug: '', description: '', lead_coordinator_id: '' });
      await fetchVerticals();
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

  const handleToggleStatus = async (vert: Vertical) => {
    const nextStatus = vert.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE';
    try {
      await adminApi.updateVertical(vert.id, { status: nextStatus });
      setSuccessMsg(`Vertical '${vert.name}' status set to ${nextStatus}.`);
      await fetchVerticals();
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`Unable to update vertical status: ${err.message}. Please try again.`);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    }
  };

  const filteredVerticals = verticals.filter(
    (v) =>
      v.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (v.description && v.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <AppShell requiredRoles={['ADMIN']} requiredPermission="verticals.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-blue-950/20 via-indigo-950/15 to-transparent border border-blue-200 dark:border-blue-800/40">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300">
                <Layers className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                Vertical Management
              </h1>
              <Badge variant="default" size="sm">
                Organizational Structure
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
              Create and govern operational verticals, manage coordinators, and configure department partitions.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchVerticals}
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
                setIsCreateOpen(true);
              }}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              Add Vertical
            </Button>
          </div>
        </div>

        {/* Alerts */}
        {errorMsg && (
          <Alert variant="danger" title="Vertical Error" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" title="Success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {/* Search Bar */}
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search vertical divisions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Verticals Grid */}
        {loading && verticals.length === 0 ? (
          <div className="p-16 flex flex-col items-center justify-center gap-2 text-zinc-400">
            <Spinner size="md" />
            <p className="text-xs">Loading vertical divisions...</p>
          </div>
        ) : filteredVerticals.length === 0 ? (
          <EmptyState
            icon={Layers}
            title="No Verticals Found"
            description="No vertical divisions match your search query."
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredVerticals.map((vert) => (
              <Card key={vert.id} className="flex flex-col justify-between">
                <CardHeader className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-indigo-600 dark:text-indigo-400">
                      <Layers className="w-4 h-4" />
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        vert.status === 'ACTIVE'
                          ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300'
                          : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400'
                      }`}
                    >
                      {vert.status}
                    </span>
                  </div>
                  <CardTitle className="text-sm font-bold">{vert.name}</CardTitle>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 line-clamp-2">
                    {vert.description || 'No description configured.'}
                  </p>
                </CardHeader>

                <CardContent className="pt-0 space-y-3">
                  {vert.lead_coordinator_name && (
                    <div className="flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-800/40 p-2 rounded-lg">
                      <UserCheck className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                      <span className="truncate">Lead: <strong>{vert.lead_coordinator_name}</strong></span>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2 border-t border-zinc-100 dark:border-zinc-800">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleToggleStatus(vert)}
                      className="text-xs"
                      leftIcon={
                        vert.status === 'ACTIVE' ? (
                          <ToggleRight className="w-4 h-4 text-emerald-600" />
                        ) : (
                          <ToggleLeft className="w-4 h-4 text-zinc-400" />
                        )
                      }
                    >
                      {vert.status === 'ACTIVE' ? 'Active' : 'Inactive'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Create Vertical Modal */}
        <Modal
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          title="Create Vertical Division"
          description="Add a new functional division to the organizational structure."
        >
          <form onSubmit={handleCreateVertical} className="space-y-4">
            {createError && (
              <Alert variant="danger" title="Creation Failed">
                {createError}
              </Alert>
            )}

            <Input
              label="Vertical Name"
              required
              placeholder="e.g. Ground Operations"
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
            />

            <Input
              label="Slug (Optional)"
              placeholder="e.g. ground_operations"
              value={createForm.slug}
              onChange={(e) => setCreateForm({ ...createForm, slug: e.target.value })}
              helperText="URL-friendly identifier. Auto-generated if left blank."
            />

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                Description
              </label>
              <textarea
                rows={3}
                placeholder="Scope and purpose of this vertical division..."
                value={createForm.description}
                onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <UserSelector
              usage="assignment"
              label="Lead Coordinator"
              placeholder="Search and assign lead coordinator..."
              value={createForm.lead_coordinator_id}
              onChange={(val) => setCreateForm({ ...createForm, lead_coordinator_id: val || '' })}
            />

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsCreateOpen(false)}
                disabled={createLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={createLoading}
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                Create Vertical
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </AppShell>
  );
}
