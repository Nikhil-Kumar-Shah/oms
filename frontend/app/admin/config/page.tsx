'use client';

/**
 * System Configuration Management (/admin/config)
 * Structured, domain-categorized system configuration workspace for administrators.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { ErrorView } from '@/components/ui/ErrorView';
import { configApi, ApiException } from '@/lib/api';
import { SystemConfigResponse, ConfigValueType } from '@/types/governance';
import {
  Sliders,
  Search,
  Shield,
  KeyRound,
  CheckCircle2,
  XCircle,
  Edit3,
  RefreshCw,
  Server,
  Layers,
  FileText,
  Clock,
  Plus,
} from 'lucide-react';

interface ConfigCategory {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  keys: string[];
}

const CONFIG_CATEGORIES: ConfigCategory[] = [
  {
    id: 'general',
    title: 'General System & Maintenance',
    description: 'System title, maintenance mode, and audit retention policies.',
    icon: Server,
    keys: ['system_name', 'maintenance_mode', 'audit_retention_days'],
  },
  {
    id: 'auth_security',
    title: 'Authentication & Session Security',
    description: 'Session lifetimes, concurrent login caps, and registration security.',
    icon: Shield,
    keys: ['session_timeout_mins', 'max_concurrent_logins', 'allow_self_registration', 'require_two_factor_auth'],
  },
  {
    id: 'operations',
    title: 'Task & Workflow Governance',
    description: 'Operational SLAs and coordinator workload capacity limits.',
    icon: Layers,
    keys: ['default_task_sla_days', 'max_active_tasks_per_user'],
  },
  {
    id: 'forms',
    title: 'Forms & Public Engagement',
    description: 'Organization-wide and public form submission permissions.',
    icon: FileText,
    keys: ['allow_public_forms'],
  },
];

const HUMAN_LABELS: Record<string, { label: string; unit?: string }> = {
  system_name: { label: 'Application Name' },
  maintenance_mode: { label: 'Maintenance Mode' },
  audit_retention_days: { label: 'Audit Retention Period', unit: 'days' },
  session_timeout_mins: { label: 'Session Inactivity Timeout', unit: 'minutes' },
  max_concurrent_logins: { label: 'Max Concurrent Sessions', unit: 'sessions / user' },
  allow_self_registration: { label: 'Self-Service Registration' },
  require_two_factor_auth: { label: 'Enforce Two-Factor Authentication' },
  default_task_sla_days: { label: 'Default Task Turnaround SLA', unit: 'days' },
  max_active_tasks_per_user: { label: 'Max Active Coordinator Tasks', unit: 'tasks / user' },
  allow_public_forms: { label: 'Public Form Submissions' },
};

export default function AdminConfigPage() {
  const [configs, setConfigs] = useState<SystemConfigResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Edit Modal State
  const [editingConfig, setEditingConfig] = useState<SystemConfigResponse | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [editDescription, setEditDescription] = useState<string>('');
  const [editIsActive, setEditIsActive] = useState<boolean>(true);
  const [editLoading, setEditLoading] = useState<boolean>(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Create Parameter Modal State
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    key: '',
    value: '',
    value_type: 'STRING' as ConfigValueType,
    description: '',
  });

  const fetchConfigs = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await configApi.listConfigs();
      setConfigs(res.items || []);
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(err.message);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    configApi
      .listConfigs()
      .then((res) => {
        if (active) setConfigs(res.items || []);
      })
      .catch((err) => {
        if (active) setErrorMsg(err instanceof Error ? err.message : 'Failed to load configurations');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const openEditModal = (cfg: SystemConfigResponse) => {
    setEditingConfig(cfg);
    setEditValue(cfg.value);
    setEditDescription(cfg.description || '');
    setEditIsActive(cfg.is_active);
    setEditError(null);
  };

  const handleUpdateConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingConfig) return;

    setEditLoading(true);
    setEditError(null);

    try {
      await configApi.updateConfig(editingConfig.key, {
        value: editValue,
        description: editDescription || undefined,
        is_active: editIsActive,
      });

      setSuccessMsg(`Setting '${editingConfig.key}' updated successfully.`);
      setEditingConfig(null);
      await fetchConfigs();
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

  const handleCreateConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    if (!createForm.key.trim()) {
      setCreateError('Configuration key is required.');
      return;
    }

    setCreateLoading(true);
    try {
      const normalizedKey = createForm.key.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
      await configApi.createConfig({
        key: normalizedKey,
        value: createForm.value.trim(),
        value_type: createForm.value_type,
        description: createForm.description.trim() || undefined,
      });

      setSuccessMsg(`Configuration '${normalizedKey}' registered successfully.`);
      setIsCreateOpen(false);
      setCreateForm({ key: '', value: '', value_type: 'STRING', description: '' });
      await fetchConfigs();
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

  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
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

  const filteredConfigs = configs.filter((c) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const meta = HUMAN_LABELS[c.key];
    return (
      c.key.toLowerCase().includes(q) ||
      c.value.toLowerCase().includes(q) ||
      (c.description && c.description.toLowerCase().includes(q)) ||
      (meta && meta.label.toLowerCase().includes(q))
    );
  });

  // Group filtered configs
  const categorizedMap = new Map<string, SystemConfigResponse[]>();
  const otherConfigs: SystemConfigResponse[] = [];

  filteredConfigs.forEach((cfg) => {
    const category = CONFIG_CATEGORIES.find((cat) => cat.keys.includes(cfg.key));
    if (category) {
      const list = categorizedMap.get(category.id) || [];
      list.push(cfg);
      categorizedMap.set(category.id, list);
    } else {
      otherConfigs.push(cfg);
    }
  });

  return (
    <AppShell requiredRoles={['ADMIN']} requiredPermission="config.read" isEventTeamAllowed={false}>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-amber-950/20 via-orange-950/15 to-transparent border border-amber-200 dark:border-amber-800/40">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300">
                <Sliders className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                System Configuration
              </h1>
              <Badge variant="default" size="sm">
                System Parameters
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
              Typed governance parameters, security constraints, and operational runtime thresholds.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchConfigs}
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
              Add Parameter
            </Button>
          </div>
        </div>

        {/* Alerts */}
        {errorMsg && (
          <Alert variant="danger" title="Configuration Error" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" title="Success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {/* Search Bar */}
        <Card>
          <CardContent className="p-4">
            <div className="relative max-w-md">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                placeholder="Search parameter names, descriptions, or keys..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs bg-zinc-50/50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </CardContent>
        </Card>

        {loading && configs.length === 0 ? (
          <div className="p-16 flex flex-col items-center justify-center gap-2 text-zinc-400">
            <Spinner size="lg" />
            <p className="text-xs">Loading system configuration...</p>
          </div>
        ) : errorMsg && configs.length === 0 ? (
          <div className="p-8">
            <ErrorView
              type="backend_unavailable"
              title="Unable to Load System Configuration"
              message={errorMsg}
              onRetry={fetchConfigs}
              layout="inline"
            />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Categorized Config Cards */}
            {CONFIG_CATEGORIES.map((cat) => {
              const catConfigs = categorizedMap.get(cat.id) || [];
              if (catConfigs.length === 0 && searchQuery) return null;

              const Icon = cat.icon;

              return (
                <Card key={cat.id}>
                  <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400">
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <CardTitle className="text-sm font-bold">{cat.title}</CardTitle>
                        <CardDescription className="text-xs">{cat.description}</CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="p-0 divide-y divide-zinc-100 dark:divide-zinc-800/60">
                    {catConfigs.length === 0 ? (
                      <div className="p-4 text-xs text-zinc-400 italic">No parameters in this category.</div>
                    ) : (
                      catConfigs.map((cfg) => {
                        const meta = HUMAN_LABELS[cfg.key] || { label: cfg.key };
                        const isBoolean = cfg.value_type === 'BOOLEAN';
                        const isTrue = cfg.value.toLowerCase() === 'true';

                        return (
                          <div
                            key={cfg.id}
                            className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30 transition-colors text-xs"
                          >
                            <div className="space-y-1 max-w-xl">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-bold text-zinc-900 dark:text-zinc-100 text-sm">
                                  {meta.label}
                                </span>
                                <span className="font-mono text-[10px] text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
                                  {cfg.key}
                                </span>
                                <span className="text-[10px] uppercase font-bold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/50 px-1.5 py-0.5 rounded">
                                  {cfg.value_type}
                                </span>
                              </div>
                              <p className="text-zinc-500 dark:text-zinc-400">
                                {cfg.description || 'System configuration parameter.'}
                              </p>
                              <div className="flex items-center gap-2 text-[10px] text-zinc-400">
                                <Clock className="w-3 h-3" />
                                <span>Updated {formatDateTime(cfg.updated_at)}</span>
                              </div>
                            </div>

                            <div className="flex items-center gap-3 shrink-0">
                              {/* Current Value Display */}
                              <div className="text-right">
                                {isBoolean ? (
                                  <span
                                    className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-bold text-xs ${
                                      isTrue
                                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                                        : 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300'
                                    }`}
                                  >
                                    {isTrue ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                                    {isTrue ? 'ENABLED' : 'DISABLED'}
                                  </span>
                                ) : (
                                  <div className="font-mono font-bold text-zinc-900 dark:text-zinc-100 text-sm bg-zinc-100 dark:bg-zinc-800 px-3 py-1.5 rounded-xl border border-zinc-200 dark:border-zinc-700">
                                    {cfg.value} {meta.unit && <span className="text-zinc-400 text-xs font-normal ml-1">{meta.unit}</span>}
                                  </div>
                                )}
                              </div>

                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openEditModal(cfg)}
                                leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                              >
                                Edit
                              </Button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </CardContent>
                </Card>
              );
            })}

            {/* Custom / Other Registered Configs */}
            {otherConfigs.length > 0 && (
              <Card>
                <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400">
                      <KeyRound className="w-4 h-4" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-bold">Custom & Dynamic Parameters</CardTitle>
                      <CardDescription className="text-xs">Additional registered configuration keys.</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-0 divide-y divide-zinc-100 dark:divide-zinc-800/60">
                  {otherConfigs.map((cfg) => (
                    <div
                      key={cfg.id}
                      className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30 transition-colors text-xs"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100">{cfg.key}</span>
                          <span className="text-[10px] uppercase font-bold text-indigo-600 bg-indigo-50 dark:bg-indigo-950/50 px-1.5 py-0.5 rounded">
                            {cfg.value_type}
                          </span>
                        </div>
                        <p className="text-zinc-500">{cfg.description || 'No description provided.'}</p>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100 bg-zinc-100 dark:bg-zinc-800 px-3 py-1.5 rounded-xl">
                          {cfg.value}
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => openEditModal(cfg)}
                          leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                        >
                          Edit
                        </Button>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------------ */}
        {/* Modals                                                             */}
        {/* ------------------------------------------------------------------ */}

        {/* Edit Config Modal */}
        <Modal
          isOpen={!!editingConfig}
          onClose={() => setEditingConfig(null)}
          title={`Edit Parameter: ${editingConfig ? HUMAN_LABELS[editingConfig.key]?.label || editingConfig.key : ''}`}
          description={`Key: ${editingConfig?.key} (${editingConfig?.value_type})`}
        >
          {editingConfig && (
            <form onSubmit={handleUpdateConfig} className="space-y-4">
              {editError && (
                <Alert variant="danger" title="Update Failed">
                  {editError}
                </Alert>
              )}

              {editingConfig.value_type === 'BOOLEAN' ? (
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                    Parameter Status
                  </label>
                  <select
                    value={editValue.toLowerCase()}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    <option value="true">ENABLED (True)</option>
                    <option value="false">DISABLED (False)</option>
                  </select>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                    Parameter Value {HUMAN_LABELS[editingConfig.key]?.unit && `(${HUMAN_LABELS[editingConfig.key].unit})`}
                  </label>
                  <input
                    type={editingConfig.value_type === 'INTEGER' ? 'number' : 'text'}
                    required
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="w-full px-3 py-2 text-xs font-mono rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              )}

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                  Description
                </label>
                <textarea
                  rows={2}
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditingConfig(null)}
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
                  Save Parameter
                </Button>
              </div>
            </form>
          )}
        </Modal>

        {/* Create Parameter Modal */}
        <Modal
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          title="Add Configuration Parameter"
          description="Register a new typed configuration setting in the system registry."
        >
          <form onSubmit={handleCreateConfig} className="space-y-4">
            {createError && (
              <Alert variant="danger" title="Registration Failed">
                {createError}
              </Alert>
            )}

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                Configuration Key (lowercase, underscores)
              </label>
              <input
                type="text"
                required
                placeholder="e.g. max_file_upload_mb"
                value={createForm.key}
                onChange={(e) => setCreateForm({ ...createForm, key: e.target.value })}
                className="w-full px-3 py-2 text-xs font-mono rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                  Data Type
                </label>
                <select
                  value={createForm.value_type}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, value_type: e.target.value as ConfigValueType })
                  }
                  className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                >
                  <option value="STRING">STRING</option>
                  <option value="INTEGER">INTEGER</option>
                  <option value="BOOLEAN">BOOLEAN</option>
                  <option value="JSON">JSON</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                  Initial Value
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 50"
                  value={createForm.value}
                  onChange={(e) => setCreateForm({ ...createForm, value: e.target.value })}
                  className="w-full px-3 py-2 text-xs font-mono rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                Description
              </label>
              <textarea
                rows={2}
                placeholder="Explain the purpose and scope of this parameter..."
                value={createForm.description}
                onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

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
              >
                Register Parameter
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </AppShell>
  );
}
