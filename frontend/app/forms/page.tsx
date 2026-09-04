'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/providers/AuthProvider';
import { AppShell } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { Modal } from '@/components/ui/Modal';
import { EmptyState } from '@/components/common/EmptyState';
import { UniversalAudienceSelector, AudienceItem, UserSelector } from '@/components/selectors';

import { formsApi, organizationApi } from '@/lib/api';
import {
  ChecklistStatus,
  DistributionSummaryResponse,
  FormChecklistItemResponse,
  FormCreate,
  FormDashboardStats,
  FormFieldSchema,
  FormFieldType,
  FormResponse,
  FormResponseDetailsResponse,
  FormSectionSchema,
} from '@/types/form';
import { Vertical, UniversalAudienceSelection } from '@/types/organization';
import {
  FileText,
  Plus,
  Send,
  CheckCircle2,
  Clock,
  RotateCcw,
  Share2,
  Eye,
  Trash2,
  ExternalLink,
  Layers,
  Inbox,
  UserCheck,
  History,
  Sparkles,
  Search,
  Users,
  ShieldCheck,
  Save,
  Copy,
  ArrowUp,
  ArrowDown,
  User,
} from 'lucide-react';


type WorkspaceTab =
  | 'assigned_to_me'
  | 'my_created'
  | 'pending_review'
  | 'returned'
  | 'completed'
  | 'shared_with_me';


const FIELD_TYPE_LABELS: Record<FormFieldType, string> = {
  TEXT: 'Short Text',
  LONG_TEXT: 'Long Text / Paragraph',
  NUMBER: 'Number',
  BOOLEAN: 'Yes / No Toggle',
  DATE: 'Date',
  DATETIME: 'Date & Time',
  SELECT: 'Dropdown Select',
  MULTI_SELECT: 'Multiple Choice (Checkboxes)',
  CHECKBOX: 'Single Checkbox',
  RADIO: 'Single Choice (Radio)',
  YES_NO: 'Yes / No Confirmation',
  REFERENCE_LINK: 'Document / Cloud Reference URL',
  URL: 'Website URL',
  EMAIL: 'Email Address',
  PHONE: 'Phone Number',
  USER_REFERENCE: 'Assignee / User Reference',
  VERTICAL_REFERENCE: 'Vertical Reference',
};

const INITIAL_FORM_SECTIONS: FormSectionSchema[] = [
  {
    id: 'sec-1',
    title: 'Section 1: General Information',
    description: 'Primary details required for this submission',
    ordering: 1,
    fields: [
      {
        id: 'f-1',
        key: 'title',
        label: 'Item / Event Title',
        type: 'TEXT',
        required: true,
        placeholder: 'Enter title...',
        ordering: 1,
      },
      {
        id: 'f-2',
        key: 'reference_url',
        label: 'Documentation Reference URL',
        type: 'REFERENCE_LINK',
        required: true,
        placeholder: 'https://drive.google.com/...',
        help_text: 'Paste authoritative Google Drive, OneDrive, or Dropbox reference link.',
        ordering: 2,
      },
    ],
  },
];

const formatAudienceLabel = (form: FormResponse): string => {
  const dist = (form.distribution_config as Record<string, any>) || {};
  if (dist.audience_items && dist.audience_items.length > 0) {
    if (dist.audience_items.length === 1) {
      return dist.audience_items[0].label || dist.audience_items[0].type;
    }
    return `${dist.audience_items[0].label} (+${dist.audience_items.length - 1} more)`;
  }
  if (form.vertical_name) {
    return form.vertical_name;
  }
  if (form.target_audience === 'ORGANIZATION' || form.target_audience === 'ALL') {
    return 'Organization-wide';
  }
  if (form.target_audience) {
    return String(form.target_audience);
  }
  return 'Configured Audience';
};

const formatDeadline = (dl?: string | null): string => {
  if (!dl) return 'No deadline set';
  try {
    const d = new Date(dl);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(dl);
  }
};

const isOverdue = (dl?: string | null): boolean => {
  if (!dl) return false;
  try {
    return new Date(dl).getTime() < Date.now();
  } catch {
    return false;
  }
};

export default function FormsWorkflowPage() {
  const { user, hasPermission, hasRole } = useAuth();

  // Role permissions
  const canCreateForms =
    hasPermission('forms.create') ||
    hasRole('ADMIN') ||
    hasRole('SPORTS_CORE') ||
    hasRole('DEPUTY_CORE') ||
    hasRole('SUPER_COORDINATOR');
  const canReviewForms =
    hasPermission('forms.review') ||
    hasRole('ADMIN') ||
    hasRole('SPORTS_CORE') ||
    hasRole('DEPUTY_CORE') ||
    hasRole('SUPER_COORDINATOR') ||
    hasRole('COORDINATOR');
  const isExecutive = hasRole('ADMIN') || hasRole('SPORTS_CORE') || hasRole('DEPUTY_CORE');

  // Workspace State
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('assigned_to_me');
  const [stats, setStats] = useState<FormDashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Forms Catalog & Responses Data
  const [formsList, setFormsList] = useState<FormResponse[]>([]);
  const [responsesList, setResponsesList] = useState<FormResponseDetailsResponse[]>([]);
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  // 1. Unified Dynamic Form Builder State
  const [isCreateTemplateOpen, setIsCreateTemplateOpen] = useState(false);
  const [builderMode, setBuilderMode] = useState<'BUILD' | 'PREVIEW'>('BUILD');
  const [editingFormId, setEditingFormId] = useState<string | null>(null);
  const [newFormName, setNewFormName] = useState('');
  const [newFormPurpose, setNewFormPurpose] = useState('');
  const [newFormInstructions, setNewFormInstructions] = useState('');
  const [newFormCategory, setNewFormCategory] = useState('Operational');
  const [newFormVerticalId, setNewFormVerticalId] = useState<string>('');
  const [newFormSections, setNewFormSections] = useState<FormSectionSchema[]>(INITIAL_FORM_SECTIONS);
  const [builderAudienceItems, setBuilderAudienceItems] = useState<AudienceItem[]>([]);
  const [builderRecipientIds, setBuilderRecipientIds] = useState<string[]>([]);
  const [builderDeadline, setBuilderDeadline] = useState('');
  const [builderDistributionInstructions, setBuilderDistributionInstructions] = useState('');
  const [isSubmittingTemplate, setIsSubmittingTemplate] = useState(false);

  // 3. Distribution Summary Matrix Modal State
  const [summaryTargetForm, setSummaryTargetForm] = useState<FormResponse | null>(null);
  const [distributionSummary, setDistributionSummary] = useState<DistributionSummaryResponse | null>(null);
  const [isSummaryLoading, setIsSummaryLoading] = useState(false);

  // 4. Form Filling & Response View State
  const [activeResponseItem, setActiveResponseItem] = useState<FormResponseDetailsResponse | null>(null);
  const [responseFormValues, setResponseFormValues] = useState<Record<string, unknown>>({});
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [isSubmittingResponse, setIsSubmittingResponse] = useState(false);

  // 5. Review & Return Modal State
  const [isReturnModalOpen, setIsReturnModalOpen] = useState(false);
  const [returnReason, setReturnReason] = useState('');
  const [reviewerRemarks, setReviewerRemarks] = useState('');
  const [isReviewing, setIsReviewing] = useState(false);

  // 6. Forward Modal State
  const [isForwardModalOpen, setIsForwardModalOpen] = useState(false);
  const [forwardTargetUserId, setForwardTargetUserId] = useState('');
  const [forwardMessage, setForwardMessage] = useState('');
  const [forwardRoleLabel, setForwardRoleLabel] = useState('Vertical Head');
  const [isForwarding, setIsForwarding] = useState(false);

  // Fetch dashboard stats & metadata
  const loadStatsAndMetadata = useCallback(async () => {
    try {
      const [statsRes, vertsRes] = await Promise.all([
        formsApi.getStats().catch(() => null),
        organizationApi.listVerticals({ status: 'ACTIVE' }).catch(() => ({ total: 0, items: [] })),
      ]);
      if (statsRes) setStats(statsRes);
      if (vertsRes && vertsRes.items) setVerticals(vertsRes.items);
    } catch (e) {
      console.error('Failed to load form stats/metadata', e);
    }
  }, []);

  // Fetch workspace items based on strictly scoped active tab
  const loadWorkspaceData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (activeTab === 'my_created') {
        const res = await formsApi.list({ workspace_tab: 'my_created', limit: 100 });
        setFormsList(res.items);
        setResponsesList([]);
      } else {
        const res = await formsApi.listResponses({ workspace_tab: activeTab, limit: 100 });
        setResponsesList(res.items);
        setFormsList([]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load forms data.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadStatsAndMetadata();
  }, [loadStatsAndMetadata]);

  useEffect(() => {
    loadWorkspaceData();
  }, [loadWorkspaceData]);

  // Section & Question Builder Helpers
  const addSection = () => {
    const nextNum = newFormSections.length + 1;
    const newSec: FormSectionSchema = {
      id: `sec-${Date.now()}-${nextNum}`,
      title: `Section ${nextNum}: New Section`,
      description: '',
      ordering: nextNum,
      fields: [
        {
          id: `f-${Date.now()}-1`,
          key: `q_${Date.now()}`,
          label: 'Question 1',
          type: 'TEXT',
          required: true,
          ordering: 1,
        },
      ],
    };
    setNewFormSections([...newFormSections, newSec]);
  };

  const updateSection = (secIndex: number, updates: Partial<FormSectionSchema>) => {
    const updated = [...newFormSections];
    updated[secIndex] = { ...updated[secIndex], ...updates };
    setNewFormSections(updated);
  };

  const removeSection = (secIndex: number) => {
    if (newFormSections.length <= 1) {
      setError('Form must have at least one section.');
      return;
    }
    const updated = newFormSections.filter((_, idx) => idx !== secIndex);
    setNewFormSections(updated);
  };

  const moveSection = (secIndex: number, direction: 'UP' | 'DOWN') => {
    const targetIdx = direction === 'UP' ? secIndex - 1 : secIndex + 1;
    if (targetIdx < 0 || targetIdx >= newFormSections.length) return;
    const updated = [...newFormSections];
    const [moved] = updated.splice(secIndex, 1);
    updated.splice(targetIdx, 0, moved);
    setNewFormSections(updated);
  };

  const addQuestion = (secIndex: number) => {
    const sec = newFormSections[secIndex];
    const nextFieldNum = sec.fields.length + 1;
    const newField: FormFieldSchema = {
      id: `f-${Date.now()}-${nextFieldNum}`,
      key: `field_${Date.now()}`,
      label: `Question ${nextFieldNum}`,
      type: 'TEXT',
      required: true,
      ordering: nextFieldNum,
    };
    const updatedSec = { ...sec, fields: [...sec.fields, newField] };
    const updatedSections = [...newFormSections];
    updatedSections[secIndex] = updatedSec;
    setNewFormSections(updatedSections);
  };

  const updateQuestion = (secIndex: number, fieldIndex: number, updates: Partial<FormFieldSchema>) => {
    const sec = newFormSections[secIndex];
    const updatedFields = [...sec.fields];
    updatedFields[fieldIndex] = { ...updatedFields[fieldIndex], ...updates };
    const updatedSections = [...newFormSections];
    updatedSections[secIndex] = { ...sec, fields: updatedFields };
    setNewFormSections(updatedSections);
  };

  const duplicateQuestion = (secIndex: number, fieldIndex: number) => {
    const sec = newFormSections[secIndex];
    const target = sec.fields[fieldIndex];
    const duplicated: FormFieldSchema = {
      ...target,
      id: `f-${Date.now()}-dup`,
      key: `${target.key}_copy_${Date.now().toString().slice(-4)}`,
      label: `${target.label} (Copy)`,
      ordering: target.ordering ? target.ordering + 1 : sec.fields.length + 1,
    };
    const updatedFields = [...sec.fields];
    updatedFields.splice(fieldIndex + 1, 0, duplicated);
    const updatedSections = [...newFormSections];
    updatedSections[secIndex] = { ...sec, fields: updatedFields };
    setNewFormSections(updatedSections);
  };

  const removeQuestion = (secIndex: number, fieldIndex: number) => {
    const sec = newFormSections[secIndex];
    if (sec.fields.length <= 1) {
      setError('Each section must contain at least one question.');
      return;
    }
    const updatedFields = sec.fields.filter((_, idx) => idx !== fieldIndex);
    const updatedSections = [...newFormSections];
    updatedSections[secIndex] = { ...sec, fields: updatedFields };
    setNewFormSections(updatedSections);
  };

  const moveQuestion = (secIndex: number, fieldIndex: number, direction: 'UP' | 'DOWN') => {
    const sec = newFormSections[secIndex];
    const targetIdx = direction === 'UP' ? fieldIndex - 1 : fieldIndex + 1;
    if (targetIdx < 0 || targetIdx >= sec.fields.length) return;
    const updatedFields = [...sec.fields];
    const [moved] = updatedFields.splice(fieldIndex, 1);
    updatedFields.splice(targetIdx, 0, moved);
    const updatedSections = [...newFormSections];
    updatedSections[secIndex] = { ...sec, fields: updatedFields };
    setNewFormSections(updatedSections);
  };

  // Open Builder for new form
  const handleOpenCreateBuilder = () => {
    setEditingFormId(null);
    setNewFormName('');
    setNewFormPurpose('');
    setNewFormInstructions('');
    setNewFormCategory('Operational');
    setNewFormVerticalId('');
    setNewFormSections(INITIAL_FORM_SECTIONS);
    setBuilderAudienceItems([]);
    setBuilderRecipientIds([]);
    setBuilderDeadline('');
    setBuilderDistributionInstructions('');
    setBuilderMode('BUILD');
    setIsCreateTemplateOpen(true);
  };

  // Open Builder for existing form template / draft
  const handleOpenEditBuilder = (form: FormResponse) => {
    setEditingFormId(form.id);
    setNewFormName(form.name);
    setNewFormPurpose(form.purpose);
    setNewFormInstructions(form.instructions || '');
    setNewFormCategory(form.category || 'Operational');
    setNewFormVerticalId(form.vertical_id || '');

    const sections =
      form.latest_version?.sections && form.latest_version.sections.length > 0
        ? form.latest_version.sections
        : INITIAL_FORM_SECTIONS;
    setNewFormSections(sections);

    const dist = (form.distribution_config as Record<string, any>) || {};
    setBuilderAudienceItems(dist.audience_items || []);
    setBuilderRecipientIds(dist.recipient_ids || []);
    if (dist.deadline) {
      try {
        setBuilderDeadline(new Date(dist.deadline).toISOString().slice(0, 16));
      } catch {
        setBuilderDeadline('');
      }
    } else {
      setBuilderDeadline('');
    }
    setBuilderDistributionInstructions(dist.distribution_instructions || '');

    setBuilderMode('BUILD');
    setIsCreateTemplateOpen(true);
  };

  // Handle Audience Selection Change & Resolve
  const handleAudienceChange = async (
    items: AudienceItem[],
    structured?: UniversalAudienceSelection
  ) => {
    setBuilderAudienceItems(items);
    const directUids = items.filter((it) => it.type === 'USER').map((it) => it.rawId);

    const hasGroupItems = items.some((it) => it.type !== 'USER');
    if (hasGroupItems && structured) {
      try {
        const resolved = await organizationApi.resolveAudience({
          all_users: structured.include_all,
          vertical_ids: structured.vertical_ids,
          role_ids: structured.role_ids,
          user_ids: directUids,
          usage: 'assignment',
        });
        setBuilderRecipientIds(resolved.user_ids && resolved.user_ids.length > 0 ? resolved.user_ids : directUids);
      } catch {
        setBuilderRecipientIds(directUids);
      }
    } else {
      setBuilderRecipientIds(directUids);
    }
  };

  // Handle Unified Save Draft or Publish & Distribute
  const handleSaveForm = async (publishAndDistribute: boolean) => {
    if (!newFormName.trim() || !newFormPurpose.trim()) {
      setError('Form title and operational purpose are required.');
      return;
    }

    let activeRecipientIds = [...builderRecipientIds];

    if (publishAndDistribute) {
      if (activeRecipientIds.length === 0 && builderAudienceItems.length > 0) {
        try {
          const directUids = builderAudienceItems.filter((it) => it.type === 'USER').map((it) => it.rawId);
          const resolved = await organizationApi.resolveAudience({
            all_users: builderAudienceItems.some((it) => it.type === 'ALL' || it.rawId === 'ALL'),
            vertical_ids: builderAudienceItems.filter((it) => it.type === 'VERTICAL').map((it) => it.rawId),
            role_ids: builderAudienceItems.filter((it) => it.type === 'ROLE').map((it) => it.rawId),
            user_ids: directUids,
            usage: 'assignment',
          });
          if (resolved.user_ids && resolved.user_ids.length > 0) {
            activeRecipientIds = resolved.user_ids;
            setBuilderRecipientIds(activeRecipientIds);
          }
        } catch {
          // Keep activeRecipientIds
        }
      }

      if (activeRecipientIds.length === 0 && builderAudienceItems.length === 0) {
        setError(
          'Target Audience / Recipients is required to Publish & Distribute. Please select at least one recipient user, team, or group.'
        );
        return;
      }
      if (newFormSections.length === 0 || newFormSections.some((s) => s.fields.length === 0)) {
        setError('Form must contain at least one section with at least one question.');
        return;
      }
    }

    setIsSubmittingTemplate(true);
    setError(null);
    try {
      const distConfig = {
        audience_items: builderAudienceItems,
        recipient_ids: activeRecipientIds,
        deadline: builderDeadline ? new Date(builderDeadline).toISOString() : null,
        distribution_instructions: builderDistributionInstructions.trim() || null,
      };

      if (editingFormId) {
        await formsApi.update(editingFormId, {
          name: newFormName.trim(),
          purpose: newFormPurpose.trim(),
          instructions: newFormInstructions.trim() || undefined,
          category: newFormCategory,
          vertical_id: newFormVerticalId || undefined,
          sections: newFormSections,
          distribution_config: distConfig,
          publish_and_distribute: publishAndDistribute,
          recipient_ids: activeRecipientIds,
          distribution_deadline: builderDeadline ? new Date(builderDeadline).toISOString() : undefined,
          distribution_instructions: builderDistributionInstructions.trim() || undefined,
        });
        setSuccessMsg(
          publishAndDistribute
            ? `Form '${newFormName.trim()}' published and distributed to ${activeRecipientIds.length} recipient(s).`
            : `Form draft '${newFormName.trim()}' saved.`
        );
      } else {
        const payload: FormCreate = {
          name: newFormName.trim(),
          purpose: newFormPurpose.trim(),
          instructions: newFormInstructions.trim() || undefined,
          category: newFormCategory,
          vertical_id: newFormVerticalId || undefined,
          target_audience: 'ORGANIZATION',
          sections: newFormSections,
          distribution_config: distConfig,
          publish_and_distribute: publishAndDistribute,
          recipient_ids: activeRecipientIds,
          distribution_deadline: builderDeadline ? new Date(builderDeadline).toISOString() : undefined,
          distribution_instructions: builderDistributionInstructions.trim() || undefined,
        };

        const created = await formsApi.create(payload);
        setSuccessMsg(
          publishAndDistribute
            ? `Form '${created.name}' published and distributed to ${activeRecipientIds.length} recipient(s).`
            : `Form draft '${created.name}' saved.`
        );
      }

      setIsCreateTemplateOpen(false);
      setEditingFormId(null);
      loadWorkspaceData();
      loadStatsAndMetadata();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save form.';
      setError(msg);
    } finally {
      setIsSubmittingTemplate(false);
    }
  };

  // Handle Open Distribution Summary
  const handleOpenSummary = async (form: FormResponse) => {
    setSummaryTargetForm(form);
    setIsSummaryLoading(true);
    try {
      const dist = form.distributions && form.distributions.length > 0 ? form.distributions[0] : null;
      if (!dist) {
        setError('No active distribution found for this template.');
        setIsSummaryLoading(false);
        return;
      }
      const summary = await formsApi.getDistributionSummary(dist.id);
      setDistributionSummary(summary);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load distribution summary matrix.';
      setError(msg);
    } finally {
      setIsSummaryLoading(false);
    }
  };

  // Save Draft Response
  const handleSaveDraft = async () => {
    if (!activeResponseItem) return;
    setIsSavingDraft(true);
    setError(null);
    try {
      const updated = await formsApi.saveDraft(activeResponseItem.id, {
        response_data: responseFormValues,
      });
      setActiveResponseItem(updated);
      setSuccessMsg('Draft responses saved to database.');
      loadWorkspaceData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save draft.';
      setError(msg);
    } finally {
      setIsSavingDraft(false);
    }
  };

  // Submit Final Response
  const handleSubmitResponse = async () => {
    if (!activeResponseItem) return;
    setIsSubmittingResponse(true);
    setError(null);
    try {
      const updated = await formsApi.submitResponse(activeResponseItem.id, {
        response_data: responseFormValues,
      });
      setActiveResponseItem(updated);
      setSuccessMsg('Form response submitted successfully for review.');
      loadWorkspaceData();
      loadStatsAndMetadata();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to submit form.';
      setError(msg);
    } finally {
      setIsSubmittingResponse(false);
    }
  };

  // Review (Approve / Return)
  const handleReviewDecision = async (action: 'APPROVE' | 'RETURN') => {
    if (!activeResponseItem) return;
    if (action === 'RETURN' && (!returnReason || returnReason.trim().length < 3)) {
      setError('Please provide a mandatory Return Reason.');
      return;
    }

    setIsReviewing(true);
    setError(null);
    try {
      const updated = await formsApi.reviewResponse(activeResponseItem.id, {
        action,
        return_reason: action === 'RETURN' ? returnReason.trim() : undefined,
        reviewer_remarks: reviewerRemarks.trim() || undefined,
        execute_transformation: true,
      });
      setActiveResponseItem(updated);
      setIsReturnModalOpen(false);
      setReturnReason('');
      setReviewerRemarks('');
      setSuccessMsg(`Response #${activeResponseItem.id.slice(0, 8)} ${action === 'APPROVE' ? 'Approved' : 'Returned'}.`);
      loadWorkspaceData();
      loadStatsAndMetadata();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Review action failed.';
      setError(msg);
    } finally {
      setIsReviewing(false);
    }
  };

  // Checklist Item Status Toggle
  const handleToggleChecklistItem = async (item: FormChecklistItemResponse, nextStatus: ChecklistStatus) => {
    try {
      await formsApi.updateChecklistItem(item.id, {
        status: nextStatus,
      });
      if (activeResponseItem) {
        const fresh = await formsApi.getResponse(activeResponseItem.id);
        setActiveResponseItem(fresh);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update checklist item.';
      setError(msg);
    }
  };

  // Forward / Share Response
  const handleForwardResponse = async () => {
    if (!activeResponseItem || !forwardTargetUserId) {
      setError('Please select a target user to forward this response.');
      return;
    }
    if (!forwardMessage.trim()) {
      setError('Please enter a note for the recipient.');
      return;
    }

    setIsForwarding(true);
    setError(null);
    try {
      const updated = await formsApi.forwardResponse(activeResponseItem.id, {
        target_user_id: forwardTargetUserId,
        message: forwardMessage.trim(),
        role_label: forwardRoleLabel,
      });
      setActiveResponseItem(updated);
      setIsForwardModalOpen(false);
      setForwardMessage('');
      setSuccessMsg('Response successfully forwarded.');
      loadWorkspaceData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to forward response.';
      setError(msg);
    } finally {
      setIsForwarding(false);
    }
  };

  // Filtered lists by search query
  const filteredForms = formsList.filter((f) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return f.name.toLowerCase().includes(q) || (f.purpose && f.purpose.toLowerCase().includes(q));
  });

  const filteredResponses = responsesList.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (r.form_name && r.form_name.toLowerCase().includes(q)) ||
      (r.recipient_name && r.recipient_name.toLowerCase().includes(q)) ||
      (r.recipient_username && r.recipient_username.toLowerCase().includes(q))
    );
  });

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        {/* HEADER */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-2 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl">
                <FileText className="w-5 h-5" />
              </span>
              <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">Forms Workspace</h1>
            </div>
            <p className="text-xs text-zinc-500 mt-1">
              Dynamic template builder, multi-recipient distribution, phase checklists, return workflows &amp; response tracking.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {canCreateForms && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleOpenCreateBuilder}
                className="shadow-sm"
              >
                <Plus className="w-4 h-4 mr-1.5" />
                Build Dynamic Form
              </Button>
            )}
          </div>
        </div>

        {/* ALERTS */}
        {error && (
          <Alert variant="danger" title="Error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" title="Success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {/* STATS OVERVIEW CARDS */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <Card className="p-3 bg-zinc-50/50 dark:bg-zinc-900/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[11px] font-medium">My Created</span>
                <Layers className="w-4 h-4 text-indigo-500" />
              </div>
              <div className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">{stats.total_forms}</div>
            </Card>

            <Card className="p-3 bg-zinc-50/50 dark:bg-zinc-900/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[11px] font-medium">Assigned To Me</span>
                <Clock className="w-4 h-4 text-amber-500" />
              </div>
              <div className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">{stats.total_responses || 0}</div>
            </Card>

            <Card className="p-3 bg-zinc-50/50 dark:bg-zinc-900/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[11px] font-medium">Pending Review</span>
                <UserCheck className="w-4 h-4 text-violet-500" />
              </div>
              <div className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">{stats.pending_review || 0}</div>
            </Card>

            <Card className="p-3 bg-zinc-50/50 dark:bg-zinc-900/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[11px] font-medium">Returned</span>
                <RotateCcw className="w-4 h-4 text-rose-500" />
              </div>
              <div className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">
                {stats.returned_responses || stats.returned || 0}
              </div>
            </Card>

            <Card className="p-3 bg-zinc-50/50 dark:bg-zinc-900/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[11px] font-medium">Completed</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              </div>
              <div className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">
                {stats.approved_responses || stats.approved || 0}
              </div>
            </Card>
          </div>
        )}

        {/* WORKSPACE TAB NAVIGATION */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 border-b border-zinc-200 dark:border-zinc-800 text-xs font-medium">
          <button
            onClick={() => setActiveTab('assigned_to_me')}
            className={`px-3.5 py-2 rounded-xl flex items-center gap-1.5 transition-all whitespace-nowrap ${
              activeTab === 'assigned_to_me'
                ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            Assigned to Me
          </button>

          {canCreateForms && (
            <button
              onClick={() => setActiveTab('my_created')}
              className={`px-3.5 py-2 rounded-xl flex items-center gap-1.5 transition-all whitespace-nowrap ${
                activeTab === 'my_created'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              My Created
            </button>
          )}

          {canReviewForms && (
            <button
              onClick={() => setActiveTab('pending_review')}
              className={`px-3.5 py-2 rounded-xl flex items-center gap-1.5 transition-all whitespace-nowrap ${
                activeTab === 'pending_review'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
              }`}
            >
              <UserCheck className="w-3.5 h-3.5" />
              Pending Review
            </button>
          )}

          <button
            onClick={() => setActiveTab('returned')}
            className={`px-3.5 py-2 rounded-xl flex items-center gap-1.5 transition-all whitespace-nowrap ${
              activeTab === 'returned'
                ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
            }`}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Returned
          </button>

          <button
            onClick={() => setActiveTab('completed')}
            className={`px-3.5 py-2 rounded-xl flex items-center gap-1.5 transition-all whitespace-nowrap ${
              activeTab === 'completed'
                ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Completed
          </button>

          <button
            onClick={() => setActiveTab('shared_with_me')}
            className={`px-3.5 py-2 rounded-xl flex items-center gap-1.5 transition-all whitespace-nowrap ${
              activeTab === 'shared_with_me'
                ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
            }`}
          >
            <Share2 className="w-3.5 h-3.5" />
            Shared With Me
          </button>
        </div>

        {/* SEARCH BAR */}
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search forms, recipients, or submissions..."
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {/* WORKSPACE CONTENT AREA */}
        {isLoading ? (
          <div className="flex justify-center items-center py-20">
            <Spinner size="lg" />
          </div>
        ) : (
          <div>
            {/* VIEW A: FORM TEMPLATES (MY CREATED) */}
            {activeTab === 'my_created' && (
              <>
                {filteredForms.length === 0 ? (
                  <EmptyState
                    icon={<FileText className="w-8 h-8 text-zinc-400" />}
                    title="You haven't created any forms yet."
                    description="Create custom multi-section forms with arbitrary questions and target audience distribution in one builder."
                    actionLabel={canCreateForms ? 'Build Form' : undefined}
                    onAction={canCreateForms ? handleOpenCreateBuilder : undefined}
                    actionIcon={<Plus className="w-4 h-4 mr-1.5" />}
                  />
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredForms.map((form) => {
                      const isOwner = form.owner_id === user?.id;
                      return (
                        <Card
                          key={form.id}
                          className="p-5 border border-zinc-200 dark:border-zinc-800 rounded-2xl hover:shadow-lg hover:border-zinc-300 dark:hover:border-zinc-700 transition-all flex flex-col justify-between bg-white dark:bg-zinc-900"
                        >
                          <div className="space-y-3.5">
                            {/* Top Tag & Status Header */}
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-800/50">
                                  {form.category || 'Operational'}
                                </span>
                                {form.vertical_name && (
                                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 border border-zinc-200/60 dark:border-zinc-700/60">
                                    {form.vertical_name}
                                  </span>
                                )}
                              </div>
                              <StatusBadge status={form.status} size="sm" />
                            </div>

                            {/* Title & Purpose */}
                            <div>
                              <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100 tracking-tight leading-snug">
                                {form.name}
                              </h3>
                              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                                {form.purpose}
                              </p>
                            </div>

                            {/* Metadata: Creator, Audience, Deadline */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-zinc-500 dark:text-zinc-400 pt-0.5 border-t border-zinc-100 dark:border-zinc-800/60">
                              <div className="flex items-center gap-1.5 truncate">
                                <User className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                                <span className="truncate">Creator: <span className="font-semibold text-zinc-700 dark:text-zinc-300">@{form.owner_username || 'Admin'}</span></span>
                              </div>

                              <div className="flex items-center gap-1.5 truncate">
                                <Users className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                                <span className="truncate">Audience: <span className="font-semibold text-zinc-700 dark:text-zinc-300">{formatAudienceLabel(form)}</span></span>
                              </div>

                              <div className="flex items-center gap-1.5 col-span-1 sm:col-span-2 truncate">
                                <Clock className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                                <span>Deadline: <span className={`font-semibold ${isOverdue(form.deadline) ? 'text-rose-600 dark:text-rose-400' : 'text-zinc-700 dark:text-zinc-300'}`}>{formatDeadline(form.deadline)}</span></span>
                              </div>
                            </div>

                            {/* Prominent Response Tracking Section */}
                            {form.status === 'PUBLISHED' ? (
                              <div className="p-3 bg-zinc-50/80 dark:bg-zinc-800/40 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-2.5">
                                <div className="flex items-center justify-between">
                                  <span className="text-[11px] font-bold text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                    Response Tracking
                                  </span>
                                  <span className="text-xs font-bold text-zinc-900 dark:text-zinc-100">
                                    {form.responses_received ?? 0} / {form.total_recipients ?? 0} Responses
                                    <span className="ml-1 text-[11px] font-semibold text-indigo-600 dark:text-indigo-400">
                                      ({form.completion_percentage ?? 0}%)
                                    </span>
                                  </span>
                                </div>

                                {/* Progress Bar */}
                                <div className="w-full h-2 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden flex">
                                  <div
                                    className="h-full bg-emerald-500 transition-all duration-500"
                                    style={{ width: `${Math.min(100, Math.max(0, form.completion_percentage ?? 0))}%` }}
                                  />
                                </div>

                                {/* Distinct Status Counters */}
                                <div className="grid grid-cols-3 gap-1.5 pt-0.5 text-[10px]">
                                  <div className="px-2 py-1 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200/60 dark:border-emerald-800/60 rounded-lg text-center">
                                    <span className="text-emerald-700 dark:text-emerald-400 font-bold block">{form.completed_responses ?? 0}</span>
                                    <span className="text-emerald-600/80 dark:text-emerald-400/80">Completed</span>
                                  </div>

                                  <div className="px-2 py-1 bg-amber-50 dark:bg-amber-950/40 border border-amber-200/60 dark:border-amber-800/60 rounded-lg text-center">
                                    <span className="text-amber-700 dark:text-amber-400 font-bold block">{form.pending_responses ?? 0}</span>
                                    <span className="text-amber-600/80 dark:text-amber-400/80">Pending</span>
                                  </div>

                                  <div className="px-2 py-1 bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/60 dark:border-zinc-700/60 rounded-lg text-center">
                                    <span className="text-zinc-700 dark:text-zinc-300 font-bold block">{form.not_started_responses ?? 0}</span>
                                    <span className="text-zinc-500">Not Started</span>
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <div className="p-3 bg-amber-50/60 dark:bg-amber-950/30 rounded-xl border border-amber-200/60 dark:border-amber-800/40 flex items-center justify-between text-xs text-amber-700 dark:text-amber-300">
                                <span className="flex items-center gap-1.5 font-medium">
                                  <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                                  Draft Form Template
                                </span>
                                <span className="text-[11px] font-semibold text-amber-600 dark:text-amber-400">
                                  Ready to publish
                                </span>
                              </div>
                            )}
                          </div>

                          {/* Footer Actions */}
                          <div className="pt-3.5 border-t border-zinc-100 dark:border-zinc-800/80 mt-4 flex items-center justify-between gap-2">
                            {form.status === 'PUBLISHED' && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleOpenSummary(form)}
                                className="text-[11px] h-8 font-medium"
                              >
                                <Users className="w-3.5 h-3.5 mr-1" />
                                Tracker Matrix
                              </Button>
                            )}

                            {isOwner && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleOpenEditBuilder(form)}
                                className="text-[11px] h-8 ml-auto font-medium"
                              >
                                {form.status === 'DRAFT' ? (
                                  <>
                                    <Sparkles className="w-3.5 h-3.5 mr-1 text-amber-500" />
                                    Edit Draft
                                  </>
                                ) : (
                                  <>
                                    <Eye className="w-3.5 h-3.5 mr-1 text-indigo-500" />
                                    View Template
                                  </>
                                )}
                              </Button>
                            )}
                          </div>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </>
            )}

            {/* VIEW B: FORM RESPONSES TABLE (ASSIGNED, PENDING REVIEW, RETURNED, COMPLETED, SHARED) */}
            {activeTab !== 'my_created' && (

              <>
                {filteredResponses.length === 0 ? (
                  <EmptyState
                    icon={<Inbox className="w-8 h-8 text-zinc-400" />}
                    title={
                      activeTab === 'assigned_to_me'
                        ? 'No forms assigned to you.'
                        : activeTab === 'pending_review'
                        ? 'No submissions pending your review.'
                        : activeTab === 'returned'
                        ? 'No returned submissions.'
                        : activeTab === 'completed'
                        ? 'No completed submissions.'
                        : 'No forms shared with you.'
                    }
                    description={
                      activeTab === 'assigned_to_me'
                        ? 'Forms distributed to you for completion will appear here.'
                        : activeTab === 'pending_review'
                        ? 'Submissions requiring multi-phase review checklist sign-off will appear here.'
                        : activeTab === 'returned'
                        ? 'Returned forms requiring correction will appear here.'
                        : activeTab === 'completed'
                        ? 'Submissions you have finalized and approved will be archived here.'
                        : 'Forms forwarded by other coordinators will appear here.'
                    }
                  />
                ) : (
                  <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-zinc-50 dark:bg-zinc-800/60 text-zinc-500 font-semibold border-b border-zinc-200 dark:border-zinc-800">
                        <tr>
                          <th className="p-3.5">Form / Task</th>
                          <th className="p-3.5">Recipient</th>
                          <th className="p-3.5">Status</th>
                          <th className="p-3.5">Review Phase</th>
                          <th className="p-3.5">Assigned / Updated</th>
                          <th className="p-3.5 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                        {filteredResponses.map((r) => {
                          const isAssignedToMe = r.recipient_id === user?.id;
                          const isFillable =
                            isAssignedToMe &&
                            (r.status === 'ASSIGNED' || r.status === 'IN_PROGRESS' || r.status === 'RETURNED');
                          return (
                            <tr key={r.id} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/40">
                              <td className="p-3.5">
                                <div className="font-bold text-zinc-900 dark:text-zinc-100">{r.form_name}</div>
                                {r.form_purpose && (
                                  <div className="text-[11px] text-zinc-400 line-clamp-1">{r.form_purpose}</div>
                                )}
                                {r.return_reason && r.status === 'RETURNED' && (
                                  <div className="text-[11px] text-rose-500 font-medium mt-0.5">
                                    Return Reason: {r.return_reason}
                                  </div>
                                )}
                              </td>

                              <td className="p-3.5 text-zinc-700 dark:text-zinc-300">
                                <div>{r.recipient_name || `@${r.recipient_username}`}</div>
                                {r.event_name && <div className="text-[10px] text-zinc-400">{r.event_name}</div>}
                              </td>

                              <td className="p-3.5">
                                <StatusBadge status={r.status} size="sm" />
                              </td>

                              <td className="p-3.5 text-zinc-500">
                                <div className="font-semibold text-zinc-700 dark:text-zinc-300">
                                  Phase {r.current_phase}
                                </div>
                                <div className="text-[10px] text-zinc-400">
                                  {r.checklist_items?.filter((c) => c.status === 'PASSED').length || 0} /{' '}
                                  {r.checklist_items?.length || 0} checks
                                </div>
                              </td>

                              <td className="p-3.5 text-zinc-500 text-[11px]">
                                {new Date(r.updated_at || r.created_at).toLocaleDateString()}
                              </td>

                              <td className="p-3.5 text-right">
                                <Button
                                  variant={isFillable ? 'primary' : 'outline'}
                                  size="sm"
                                  onClick={() => {
                                    setActiveResponseItem(r);
                                    setResponseFormValues(r.response_data || {});
                                  }}
                                  className="text-[11px] h-8"
                                >
                                  {isFillable ? (
                                    <>
                                      <FileText className="w-3.5 h-3.5 mr-1" />
                                      {r.status === 'RETURNED' ? 'Fix & Resubmit' : 'Fill Form'}
                                    </>
                                  ) : (
                                    <>
                                      <Eye className="w-3.5 h-3.5 mr-1" />
                                      Inspect
                                    </>
                                  )}
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* 1. DYNAMIC FORM BUILDER & LIVE PREVIEW MODAL                  */}
        {/* ------------------------------------------------------------- */}
        {isCreateTemplateOpen && (
          <Modal
            isOpen={true}
            onClose={() => setIsCreateTemplateOpen(false)}
            title={builderMode === 'BUILD' ? 'Dynamic Form Builder' : `Preview: ${newFormName || 'Untitled Form'}`}
            description="Build multi-section forms with arbitrary questions, custom field types, validation rules, and live preview."
            size="xl"
          >
            <div className="space-y-6 text-xs max-h-[75vh] overflow-y-auto pr-1">
              {/* BUILDER / PREVIEW MODE TOGGLE */}
              <div className="flex items-center justify-between p-1 bg-zinc-100 dark:bg-zinc-800/80 rounded-xl">
                <button
                  type="button"
                  onClick={() => setBuilderMode('BUILD')}
                  className={`flex-1 py-1.5 rounded-lg text-center font-bold transition-all ${
                    builderMode === 'BUILD'
                      ? 'bg-white dark:bg-zinc-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100'
                  }`}
                >
                  Builder Mode
                </button>
                <button
                  type="button"
                  onClick={() => setBuilderMode('PREVIEW')}
                  className={`flex-1 py-1.5 rounded-lg text-center font-bold transition-all ${
                    builderMode === 'PREVIEW'
                      ? 'bg-white dark:bg-zinc-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100'
                  }`}
                >
                  Live Respondent Preview
                </button>
              </div>

              {builderMode === 'BUILD' ? (
                /* BUILDER MODE */
                <div className="space-y-6">
                  {/* FORM METADATA */}
                  <div className="p-4 bg-zinc-50 dark:bg-zinc-900/60 rounded-2xl border border-zinc-200 dark:border-zinc-800 space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                          Form Title <span className="text-rose-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={newFormName}
                          onChange={(e) => setNewFormName(e.target.value)}
                          placeholder="e.g. Event Equipment & Pitch Readiness Form"
                          className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                        />
                      </div>

                      <div>
                        <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                          Operational Purpose <span className="text-rose-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={newFormPurpose}
                          onChange={(e) => setNewFormPurpose(e.target.value)}
                          placeholder="e.g. Field readiness & document compliance check"
                          className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">Category (Optional)</label>
                        <select
                          value={newFormCategory}
                          onChange={(e) => setNewFormCategory(e.target.value)}
                          className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                        >
                          <option value="Operational">Operational</option>
                          <option value="Event Readiness">Event Readiness</option>
                          <option value="Logistics">Logistics</option>
                          <option value="Finance & Budget">Finance &amp; Budget</option>
                          <option value="Medical & Safety">Medical &amp; Safety</option>
                          <option value="Compliance">Compliance</option>
                        </select>
                      </div>

                      <div>
                        <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                          Target Vertical (Optional)
                        </label>
                        <select
                          value={newFormVerticalId}
                          onChange={(e) => setNewFormVerticalId(e.target.value)}
                          className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                        >
                          <option value="">Organization-wide / All Verticals</option>
                          {verticals.map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                        Respondent Instructions (Optional)
                      </label>
                      <textarea
                        rows={2}
                        value={newFormInstructions}
                        onChange={(e) => setNewFormInstructions(e.target.value)}
                        placeholder="Provide guidelines, checklist references or deadline instructions for respondents..."
                        className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                      />
                    </div>

                    {/* TARGET AUDIENCE & DISTRIBUTION SETTINGS */}
                    <div className="pt-3 border-t border-zinc-200 dark:border-zinc-800 space-y-3">
                      <UniversalAudienceSelector
                        usage="audience"
                        label="Target Audience / Recipients"
                        required
                        showResolvedPreview
                        description="Select the users, event teams, or vertical divisions to receive this form."
                        placeholder="Search audience groups, roles, divisions, event teams, or people..."
                        value={builderAudienceItems}
                        onChange={(items, structured) => handleAudienceChange(items, structured)}
                      />

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                            Completion Deadline (Optional)
                          </label>
                          <input
                            type="datetime-local"
                            value={builderDeadline}
                            onChange={(e) => setBuilderDeadline(e.target.value)}
                            className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                            Distribution Instructions (Optional)
                          </label>
                          <input
                            type="text"
                            value={builderDistributionInstructions}
                            onChange={(e) => setBuilderDistributionInstructions(e.target.value)}
                            placeholder="e.g. Please submit all verification proofs by the deadline"
                            className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* SECTIONS LIST */}
                  <div className="space-y-5">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                        <Layers className="w-4 h-4 text-indigo-500" />
                        Form Sections ({newFormSections.length})
                      </h3>
                      <Button variant="outline" size="sm" onClick={addSection}>
                        <Plus className="w-3.5 h-3.5 mr-1" />
                        Add Section
                      </Button>
                    </div>

                    {newFormSections.map((sec, sIdx) => (
                      <div
                        key={sec.id || sIdx}
                        className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm space-y-4"
                      >
                        {/* SECTION HEADER */}
                        <div className="flex items-start justify-between gap-3 border-b border-zinc-100 dark:border-zinc-800 pb-3">
                          <div className="flex-1 space-y-2">
                            <input
                              type="text"
                              value={sec.title}
                              onChange={(e) => updateSection(sIdx, { title: e.target.value })}
                              placeholder="Section Title"
                              className="w-full font-bold text-sm text-zinc-900 dark:text-zinc-100 p-1.5 rounded-lg border border-transparent hover:border-zinc-300 dark:hover:border-zinc-700 focus:border-indigo-500 focus:bg-white dark:focus:bg-zinc-900"
                            />
                            <input
                              type="text"
                              value={sec.description || ''}
                              onChange={(e) => updateSection(sIdx, { description: e.target.value })}
                              placeholder="Section Description / Context"
                              className="w-full text-xs text-zinc-500 p-1 rounded-lg border border-transparent hover:border-zinc-200 dark:hover:border-zinc-700 focus:border-indigo-500"
                            />
                          </div>

                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={sIdx === 0}
                              onClick={() => moveSection(sIdx, 'UP')}
                              className="p-1 h-7 w-7"
                            >
                              <ArrowUp className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={sIdx === newFormSections.length - 1}
                              onClick={() => moveSection(sIdx, 'DOWN')}
                              className="p-1 h-7 w-7"
                            >
                              <ArrowDown className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeSection(sIdx)}
                              className="p-1 h-7 w-7 text-rose-500 hover:text-rose-600 hover:bg-rose-50"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </div>

                        {/* QUESTIONS IN SECTION */}
                        <div className="space-y-3 pl-2 border-l-2 border-indigo-500/20">
                          {sec.fields.map((field, fIdx) => (
                            <div
                              key={field.id || fIdx}
                              className="p-3 bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200/80 dark:border-zinc-800 rounded-xl space-y-3"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                  <div className="sm:col-span-2">
                                    <label className="block text-[10px] font-bold text-zinc-500 mb-1">
                                      Question Label
                                    </label>
                                    <input
                                      type="text"
                                      value={field.label}
                                      onChange={(e) =>
                                        updateQuestion(sIdx, fIdx, {
                                          label: e.target.value,
                                          key:
                                            field.key.startsWith('field_') || field.key.startsWith('q_')
                                              ? e.target.value
                                                  .toLowerCase()
                                                  .replace(/[^a-z0-9_]/g, '_')
                                                  .slice(0, 32) || field.key
                                              : field.key,
                                        })
                                      }
                                      placeholder="e.g. Number of required training bibs"
                                      className="w-full p-2 text-xs rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                                    />
                                  </div>

                                  <div>
                                    <label className="block text-[10px] font-bold text-zinc-500 mb-1">Field Type</label>
                                    <select
                                      value={field.type}
                                      onChange={(e) =>
                                        updateQuestion(sIdx, fIdx, {
                                          type: e.target.value as FormFieldType,
                                          options:
                                            e.target.value === 'SELECT' ||
                                            e.target.value === 'RADIO' ||
                                            e.target.value === 'MULTI_SELECT'
                                              ? field.options || ['Option 1', 'Option 2']
                                              : undefined,
                                        })
                                      }
                                      className="w-full p-2 text-xs rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                                    >
                                      {Object.entries(FIELD_TYPE_LABELS).map(([tKey, tLabel]) => (
                                        <option key={tKey} value={tKey}>
                                          {tLabel}
                                        </option>
                                      ))}
                                    </select>
                                  </div>
                                </div>

                                <div className="flex items-center gap-1 pt-4">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => duplicateQuestion(sIdx, fIdx)}
                                    title="Duplicate Question"
                                    className="p-1 h-7 w-7"
                                  >
                                    <Copy className="w-3.5 h-3.5" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    disabled={fIdx === 0}
                                    onClick={() => moveQuestion(sIdx, fIdx, 'UP')}
                                    className="p-1 h-7 w-7"
                                  >
                                    <ArrowUp className="w-3.5 h-3.5" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    disabled={fIdx === sec.fields.length - 1}
                                    onClick={() => moveQuestion(sIdx, fIdx, 'DOWN')}
                                    className="p-1 h-7 w-7"
                                  >
                                    <ArrowDown className="w-3.5 h-3.5" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => removeQuestion(sIdx, fIdx)}
                                    className="p-1 h-7 w-7 text-rose-500 hover:text-rose-600"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </Button>
                                </div>
                              </div>

                              {/* OPTIONS MANAGER (FOR SELECT, RADIO, MULTI_SELECT) */}
                              {(field.type === 'SELECT' ||
                                field.type === 'RADIO' ||
                                field.type === 'MULTI_SELECT') && (
                                <div className="p-2.5 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700 space-y-2">
                                  <div className="flex items-center justify-between">
                                    <span className="text-[10px] font-bold text-zinc-500">Choice Options</span>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => {
                                        const curOpts = field.options || [];
                                        updateQuestion(sIdx, fIdx, {
                                          options: [...curOpts, `Option ${curOpts.length + 1}`],
                                        });
                                      }}
                                      className="text-[10px] h-6 px-2"
                                    >
                                      + Add Option
                                    </Button>
                                  </div>

                                  <div className="space-y-1.5">
                                    {(field.options || []).map((opt, oIdx) => (
                                      <div key={oIdx} className="flex items-center gap-2">
                                        <input
                                          type="text"
                                          value={opt}
                                          onChange={(e) => {
                                            const updated = [...(field.options || [])];
                                            updated[oIdx] = e.target.value;
                                            updateQuestion(sIdx, fIdx, { options: updated });
                                          }}
                                          className="flex-1 p-1.5 text-xs rounded-md border border-zinc-200 dark:border-zinc-700"
                                        />
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => {
                                            const updated = (field.options || []).filter((_, idx) => idx !== oIdx);
                                            updateQuestion(sIdx, fIdx, { options: updated });
                                          }}
                                          className="p-1 h-6 w-6 text-rose-500"
                                        >
                                          ×
                                        </Button>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* FIELD CONFIGURATION (REQUIRED, PLACEHOLDER, HELP TEXT) */}
                              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                                <div className="flex items-center gap-2 pt-2">
                                  <input
                                    type="checkbox"
                                    id={`req-${sIdx}-${fIdx}`}
                                    checked={field.required ?? true}
                                    onChange={(e) => updateQuestion(sIdx, fIdx, { required: e.target.checked })}
                                    className="rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                                  />
                                  <label
                                    htmlFor={`req-${sIdx}-${fIdx}`}
                                    className="text-[11px] font-semibold text-zinc-700 dark:text-zinc-300"
                                  >
                                    Required Question
                                  </label>
                                </div>

                                <div>
                                  <input
                                    type="text"
                                    value={field.placeholder || ''}
                                    onChange={(e) => updateQuestion(sIdx, fIdx, { placeholder: e.target.value })}
                                    placeholder="Placeholder text (optional)"
                                    className="w-full p-1.5 text-[11px] rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                                  />
                                </div>

                                <div>
                                  <input
                                    type="text"
                                    value={field.help_text || ''}
                                    onChange={(e) => updateQuestion(sIdx, fIdx, { help_text: e.target.value })}
                                    placeholder="Help text / instruction"
                                    className="w-full p-1.5 text-[11px] rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                                  />
                                </div>
                              </div>
                            </div>
                          ))}

                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => addQuestion(sIdx)}
                            className="text-indigo-600 dark:text-indigo-400 text-xs font-semibold"
                          >
                            + Add Question to {sec.title}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                /* LIVE PREVIEW MODE */
                <div className="p-6 bg-zinc-50 dark:bg-zinc-900/60 rounded-2xl border border-zinc-200 dark:border-zinc-800 space-y-6">
                  <div className="border-b border-zinc-200 dark:border-zinc-800 pb-4">
                    <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                      {newFormCategory}
                    </span>
                    <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-2">
                      {newFormName || 'Untitled Form'}
                    </h2>
                    <p className="text-xs text-zinc-500 mt-1">{newFormPurpose || 'No purpose specified'}</p>
                    {newFormInstructions && (
                      <p className="text-xs text-zinc-600 dark:text-zinc-400 italic bg-white dark:bg-zinc-900 p-3 rounded-xl border border-zinc-200 dark:border-zinc-800 mt-3">
                        Instructions: {newFormInstructions}
                      </p>
                    )}
                  </div>

                  {newFormSections.map((sec, sIdx) => (
                    <div key={sIdx} className="space-y-4">
                      <div className="border-b border-zinc-200/60 dark:border-zinc-800 pb-1">
                        <h4 className="font-bold text-zinc-900 dark:text-zinc-100 text-sm">{sec.title}</h4>
                        {sec.description && <p className="text-xs text-zinc-400">{sec.description}</p>}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {sec.fields.map((f, fIdx) => (
                          <div
                            key={fIdx}
                            className={
                              f.type === 'LONG_TEXT' || f.type === 'MULTI_SELECT'
                                ? 'md:col-span-2 space-y-1'
                                : 'space-y-1'
                            }
                          >
                            <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                              {f.label} {f.required && <span className="text-rose-500">*</span>}
                            </label>

                            {/* TEXT / EMAIL / URL / PHONE */}
                            {(f.type === 'TEXT' ||
                              f.type === 'EMAIL' ||
                              f.type === 'URL' ||
                              f.type === 'PHONE' ||
                              f.type === 'USER_REFERENCE' ||
                              f.type === 'VERTICAL_REFERENCE') && (
                              <input
                                type={f.type === 'EMAIL' ? 'email' : f.type === 'PHONE' ? 'tel' : 'text'}
                                placeholder={f.placeholder || `Enter ${f.label.toLowerCase()}...`}
                                disabled
                                className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs opacity-80"
                              />
                            )}

                            {/* REFERENCE LINK */}
                            {f.type === 'REFERENCE_LINK' && (
                              <div className="relative">
                                <ExternalLink className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
                                <input
                                  type="url"
                                  placeholder={f.placeholder || 'https://drive.google.com/...'}
                                  disabled
                                  className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs opacity-80"
                                />
                              </div>
                            )}

                            {/* NUMBER */}
                            {f.type === 'NUMBER' && (
                              <input
                                type="number"
                                placeholder={f.placeholder || '0'}
                                disabled
                                className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs opacity-80"
                              />
                            )}

                            {/* LONG TEXT */}
                            {f.type === 'LONG_TEXT' && (
                              <textarea
                                rows={3}
                                placeholder={f.placeholder || 'Enter detailed response...'}
                                disabled
                                className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs opacity-80"
                              />
                            )}

                            {/* DATE / DATETIME */}
                            {(f.type === 'DATE' || f.type === 'DATETIME') && (
                              <input
                                type={f.type === 'DATETIME' ? 'datetime-local' : 'date'}
                                disabled
                                className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs opacity-80"
                              />
                            )}

                            {/* SELECT */}
                            {f.type === 'SELECT' && (
                              <select
                                disabled
                                className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs opacity-80"
                              >
                                <option value="">Select option...</option>
                                {(f.options || []).map((opt, oIdx) => (
                                  <option key={oIdx} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </select>
                            )}

                            {/* RADIO */}
                            {f.type === 'RADIO' && (
                              <div className="space-y-1.5 pt-1">
                                {(f.options || ['Option 1', 'Option 2']).map((opt, oIdx) => (
                                  <div key={oIdx} className="flex items-center gap-2">
                                    <input type="radio" disabled name={`prev-${f.key}`} />
                                    <span className="text-xs text-zinc-700 dark:text-zinc-300">{opt}</span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* MULTI SELECT */}
                            {f.type === 'MULTI_SELECT' && (
                              <div className="space-y-1.5 pt-1">
                                {(f.options || ['Option A', 'Option B']).map((opt, oIdx) => (
                                  <div key={oIdx} className="flex items-center gap-2">
                                    <input type="checkbox" disabled />
                                    <span className="text-xs text-zinc-700 dark:text-zinc-300">{opt}</span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* CHECKBOX / BOOLEAN / YES_NO */}
                            {(f.type === 'CHECKBOX' || f.type === 'BOOLEAN' || f.type === 'YES_NO') && (
                              <div className="flex items-center gap-2 pt-1">
                                <input type="checkbox" disabled className="rounded text-indigo-600" />
                                <span className="text-xs text-zinc-700 dark:text-zinc-300">
                                  {f.help_text || 'Confirm / Yes'}
                                </span>
                              </div>
                            )}

                            {f.help_text && (
                              <p className="text-[10px] text-zinc-400 italic pt-0.5">{f.help_text}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* MODAL FOOTER CONTROLS */}
              <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
                <Button variant="ghost" size="sm" onClick={() => setIsCreateTemplateOpen(false)}>
                  Cancel
                </Button>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isSubmittingTemplate}
                    onClick={() => handleSaveForm(false)}
                  >
                    <Save className="w-3.5 h-3.5 mr-1" />
                    Save Draft
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={isSubmittingTemplate}
                    onClick={() => handleSaveForm(true)}
                  >
                    <Send className="w-3.5 h-3.5 mr-1" />
                    Publish Form
                  </Button>
                </div>
              </div>
            </div>
          </Modal>
        )}

        {/* ------------------------------------------------------------- */}
        {/* 3. DISTRIBUTION SUMMARY TRACKER MODAL                         */}
        {/* ------------------------------------------------------------- */}
        {summaryTargetForm && (
          <Modal
            isOpen={true}
            onClose={() => {
              setSummaryTargetForm(null);
              setDistributionSummary(null);
            }}
            title={`Distribution Tracker: ${summaryTargetForm.name}`}
            description="Live aggregated matrix showing status across all assigned response instances."
            size="xl"
          >
            {isSummaryLoading ? (
              <div className="flex justify-center items-center py-12">
                <Spinner size="md" />
              </div>
            ) : distributionSummary ? (
              <div className="space-y-5 text-xs max-h-[70vh] overflow-y-auto">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="p-3 bg-zinc-50 dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800">
                    <div className="text-zinc-400 text-[10px]">Total Recipients</div>
                    <div className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                      {distributionSummary.total_recipients}
                    </div>
                  </div>

                  <div className="p-3 bg-amber-500/10 rounded-xl border border-amber-500/20">
                    <div className="text-amber-600 dark:text-amber-400 text-[10px]">Pending Completion</div>
                    <div className="text-base font-bold text-amber-700 dark:text-amber-300">
                      {(distributionSummary.counts.ASSIGNED || 0) + (distributionSummary.counts.IN_PROGRESS || 0)}
                    </div>
                  </div>

                  <div className="p-3 bg-violet-500/10 rounded-xl border border-violet-500/20">
                    <div className="text-violet-600 dark:text-violet-400 text-[10px]">Submitted / Review</div>
                    <div className="text-base font-bold text-violet-700 dark:text-violet-300">
                      {(distributionSummary.counts.SUBMITTED || 0) + (distributionSummary.counts.RESUBMITTED || 0)}
                    </div>
                  </div>

                  <div className="p-3 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
                    <div className="text-emerald-600 dark:text-emerald-400 text-[10px]">Approved</div>
                    <div className="text-base font-bold text-emerald-700 dark:text-emerald-300">
                      {distributionSummary.counts.APPROVED || 0}
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
                  <table className="w-full text-left">
                    <thead className="bg-zinc-50 dark:bg-zinc-800/60 text-zinc-500 font-semibold border-b border-zinc-200 dark:border-zinc-800">
                      <tr>
                        <th className="p-3">Recipient</th>
                        <th className="p-3">Status</th>
                        <th className="p-3">Progress</th>
                        <th className="p-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                      {distributionSummary.recipients.map((recip) => (
                        <tr key={recip.response_id} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/40">
                          <td className="p-3 font-semibold text-zinc-900 dark:text-zinc-100">
                            {recip.recipient_name}{' '}
                            <span className="text-zinc-400 font-normal">(@{recip.recipient_username})</span>
                            {recip.event_name && <div className="text-[10px] text-zinc-400">{recip.event_name}</div>}
                          </td>
                          <td className="p-3">
                            <StatusBadge status={recip.status} size="sm" />
                          </td>
                          <td className="p-3 text-zinc-500">
                            Phase {recip.current_phase} • {recip.checklist_completed_count}/
                            {recip.checklist_total_count} items
                          </td>
                          <td className="p-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={async () => {
                                try {
                                  const resp = await formsApi.getResponse(recip.response_id);
                                  setSummaryTargetForm(null);
                                  setActiveResponseItem(resp);
                                  setResponseFormValues(resp.response_data || {});
                                } catch (err: unknown) {
                                  const msg = err instanceof Error ? err.message : 'Cannot inspect response.';
                                  setError(msg);
                                }
                              }}
                            >
                              Inspect
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </Modal>
        )}

        {/* ------------------------------------------------------------- */}
        {/* 4. FORM FILLING & MULTI-PHASE REVIEW WORKSPACE                */}
        {/* ------------------------------------------------------------- */}
        {activeResponseItem && (
          <Modal
            isOpen={true}
            onClose={() => setActiveResponseItem(null)}
            title={activeResponseItem.form_name || 'Form Response'}
            description={`Recipient: ${activeResponseItem.recipient_name || `@${activeResponseItem.recipient_username}`} • Status: ${activeResponseItem.status}`}
            size="xl"
          >
            <div className="space-y-6 text-xs max-h-[75vh] overflow-y-auto pr-1">
              {/* STATUS BANNER */}
              <div className="p-4 rounded-2xl bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={activeResponseItem.status} size="sm" />
                    <span className="font-bold text-zinc-800 dark:text-zinc-200">
                      Phase {activeResponseItem.current_phase} Operational Workflow
                    </span>
                  </div>
                  {activeResponseItem.return_reason && activeResponseItem.status === 'RETURNED' && (
                    <p className="text-rose-600 dark:text-rose-400 font-semibold pt-1">
                      Return Reason: {activeResponseItem.return_reason}
                    </p>
                  )}
                </div>

                {/* Reviewer / Submitter Actions */}
                <div className="flex items-center gap-2">
                  {/* If user is recipient and form is fillable */}
                  {activeResponseItem.recipient_id === user?.id &&
                    (activeResponseItem.status === 'ASSIGNED' ||
                      activeResponseItem.status === 'IN_PROGRESS' ||
                      activeResponseItem.status === 'RETURNED') && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={isSavingDraft}
                          onClick={handleSaveDraft}
                          className="h-8 text-xs"
                        >
                          <Save className="w-3.5 h-3.5 mr-1" />
                          Save Draft
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          disabled={isSubmittingResponse}
                          onClick={handleSubmitResponse}
                          className="h-8 text-xs"
                        >
                          <Send className="w-3.5 h-3.5 mr-1" />
                          {activeResponseItem.status === 'RETURNED' ? 'Resubmit' : 'Submit Final'}
                        </Button>
                      </>
                    )}

                  {/* If user is an authorized reviewer and submission is under review */}
                  {canReviewForms &&
                    activeResponseItem.recipient_id !== user?.id &&
                    (activeResponseItem.status === 'SUBMITTED' ||
                      activeResponseItem.status === 'RESUBMITTED' ||
                      activeResponseItem.status === 'UNDER_REVIEW') && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setIsReturnModalOpen(true)}
                          className="h-8 text-xs text-rose-600 border-rose-200 hover:bg-rose-50"
                        >
                          <RotateCcw className="w-3.5 h-3.5 mr-1" />
                          Return with Reason
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          disabled={isReviewing}
                          onClick={() => handleReviewDecision('APPROVE')}
                          className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                          Approve
                        </Button>
                      </>
                    )}

                  {/* Forward button */}
                  {(canReviewForms || isExecutive) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setIsForwardModalOpen(true)}
                      className="h-8 text-xs"
                    >
                      <Share2 className="w-3.5 h-3.5 mr-1" />
                      Forward
                    </Button>
                  )}
                </div>
              </div>

              {/* SECTIONS & RESPONSE FIELDS */}
              <div className="space-y-5">
                {(activeResponseItem.sections && activeResponseItem.sections.length > 0
                  ? activeResponseItem.sections
                  : [
                      {
                        title: 'Submission Information',
                        fields: activeResponseItem.schema_fields || [],
                      },
                    ]
                ).map((sec, sIdx) => {
                  const isRecipientFillable =
                    activeResponseItem.recipient_id === user?.id &&
                    (activeResponseItem.status === 'ASSIGNED' ||
                      activeResponseItem.status === 'IN_PROGRESS' ||
                      activeResponseItem.status === 'RETURNED');
                  return (
                    <div
                      key={sIdx}
                      className="p-5 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl space-y-4 shadow-sm"
                    >
                      <div className="border-b border-zinc-100 dark:border-zinc-800 pb-2">
                        <h4 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">{sec.title}</h4>
                        {sec.description && <p className="text-xs text-zinc-400">{sec.description}</p>}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {sec.fields.map((field, fIdx) => {
                          const val = responseFormValues[field.key] ?? '';
                          return (
                            <div
                              key={fIdx}
                              className={
                                field.type === 'LONG_TEXT' || field.type === 'MULTI_SELECT'
                                  ? 'md:col-span-2 space-y-1'
                                  : 'space-y-1'
                              }
                            >
                              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                                {field.label} {field.required && <span className="text-rose-500">*</span>}
                              </label>

                              {/* TEXT / EMAIL / URL / PHONE */}
                              {(field.type === 'TEXT' ||
                                field.type === 'EMAIL' ||
                                field.type === 'URL' ||
                                field.type === 'PHONE' ||
                                field.type === 'USER_REFERENCE' ||
                                field.type === 'VERTICAL_REFERENCE') && (
                                <input
                                  type={field.type === 'EMAIL' ? 'email' : field.type === 'PHONE' ? 'tel' : 'text'}
                                  value={String(val)}
                                  disabled={!isRecipientFillable}
                                  onChange={(e) =>
                                    setResponseFormValues({ ...responseFormValues, [field.key]: e.target.value })
                                  }
                                  placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}...`}
                                  className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs"
                                />
                              )}

                              {/* REFERENCE LINK */}
                              {field.type === 'REFERENCE_LINK' && (
                                <div className="space-y-1">
                                  <div className="relative">
                                    <ExternalLink className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
                                    <input
                                      type="url"
                                      value={String(val)}
                                      disabled={!isRecipientFillable}
                                      onChange={(e) =>
                                        setResponseFormValues({ ...responseFormValues, [field.key]: e.target.value })
                                      }
                                      placeholder="https://drive.google.com/..."
                                      className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs"
                                    />
                                  </div>
                                  {val && typeof val === 'string' && val.startsWith('http') && (
                                    <a
                                      href={val}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-[11px] text-indigo-600 dark:text-indigo-400 inline-flex items-center gap-1 font-semibold hover:underline"
                                    >
                                      Open Document Reference <ExternalLink className="w-3 h-3" />
                                    </a>
                                  )}
                                </div>
                              )}

                              {/* NUMBER */}
                              {field.type === 'NUMBER' && (
                                <input
                                  type="number"
                                  value={val === '' ? '' : Number(val)}
                                  disabled={!isRecipientFillable}
                                  onChange={(e) =>
                                    setResponseFormValues({
                                      ...responseFormValues,
                                      [field.key]: e.target.value === '' ? '' : Number(e.target.value),
                                    })
                                  }
                                  className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs"
                                />
                              )}

                              {/* LONG TEXT */}
                              {field.type === 'LONG_TEXT' && (
                                <textarea
                                  rows={3}
                                  value={String(val)}
                                  disabled={!isRecipientFillable}
                                  onChange={(e) =>
                                    setResponseFormValues({ ...responseFormValues, [field.key]: e.target.value })
                                  }
                                  placeholder={field.placeholder || 'Enter notes...'}
                                  className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs"
                                />
                              )}

                              {/* DATE / DATETIME */}
                              {(field.type === 'DATE' || field.type === 'DATETIME') && (
                                <input
                                  type={field.type === 'DATETIME' ? 'datetime-local' : 'date'}
                                  value={String(val)}
                                  disabled={!isRecipientFillable}
                                  onChange={(e) =>
                                    setResponseFormValues({ ...responseFormValues, [field.key]: e.target.value })
                                  }
                                  className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs"
                                />
                              )}

                              {/* SELECT */}
                              {field.type === 'SELECT' && (
                                <select
                                  value={String(val)}
                                  disabled={!isRecipientFillable}
                                  onChange={(e) =>
                                    setResponseFormValues({ ...responseFormValues, [field.key]: e.target.value })
                                  }
                                  className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-xs"
                                >
                                  <option value="">Select option...</option>
                                  {(field.options || []).map((opt, oIdx) => (
                                    <option key={oIdx} value={opt}>
                                      {opt}
                                    </option>
                                  ))}
                                </select>
                              )}

                              {/* RADIO */}
                              {field.type === 'RADIO' && (
                                <div className="space-y-1.5 pt-1">
                                  {(field.options || ['Option 1', 'Option 2']).map((opt, oIdx) => (
                                    <label key={oIdx} className="flex items-center gap-2 cursor-pointer">
                                      <input
                                        type="radio"
                                        name={field.key}
                                        value={opt}
                                        checked={val === opt}
                                        disabled={!isRecipientFillable}
                                        onChange={() =>
                                          setResponseFormValues({ ...responseFormValues, [field.key]: opt })
                                        }
                                        className="text-indigo-600 focus:ring-indigo-500"
                                      />
                                      <span className="text-xs text-zinc-700 dark:text-zinc-300">{opt}</span>
                                    </label>
                                  ))}
                                </div>
                              )}

                              {/* CHECKBOX / BOOLEAN / YES_NO */}
                              {(field.type === 'CHECKBOX' || field.type === 'BOOLEAN' || field.type === 'YES_NO') && (
                                <div className="flex items-center gap-2 pt-1">
                                  <input
                                    type="checkbox"
                                    checked={Boolean(val)}
                                    disabled={!isRecipientFillable}
                                    onChange={(e) =>
                                      setResponseFormValues({
                                        ...responseFormValues,
                                        [field.key]: e.target.checked,
                                      })
                                    }
                                    className="rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                                  />
                                  <span className="text-xs text-zinc-700 dark:text-zinc-300">
                                    {field.help_text || 'Confirmed'}
                                  </span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* REVIEW CHECKLIST ITEMS (MULTI-PHASE) */}
              {activeResponseItem.checklist_items && activeResponseItem.checklist_items.length > 0 && (
                <div className="p-4 bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 rounded-2xl space-y-3">
                  <h4 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-500" />
                    Operational Review Checklists
                  </h4>

                  <div className="space-y-2">
                    {activeResponseItem.checklist_items.map((item) => (
                      <div
                        key={item.id}
                        className="p-3 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 flex items-center justify-between gap-3"
                      >
                        <div className="space-y-0.5">
                          <div className="font-semibold text-zinc-800 dark:text-zinc-200">{item.title}</div>
                          {item.description && <div className="text-zinc-400 text-[11px]">{item.description}</div>}
                          {item.evidence_link && (
                            <a
                              href={item.evidence_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-indigo-600 text-[10px] inline-flex items-center gap-1"
                            >
                              View Evidence Link <ExternalLink className="w-2.5 h-2.5" />
                            </a>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          <StatusBadge status={item.status} size="sm" />
                          {canReviewForms && activeResponseItem.recipient_id !== user?.id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                handleToggleChecklistItem(
                                  item,
                                  item.status === 'PASSED' ? 'PENDING' : 'PASSED'
                                )
                              }
                              className="h-7 text-[11px]"
                            >
                              {item.status === 'PASSED' ? 'Mark Pending' : 'Mark Passed'}
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* WORKFLOW AUDIT HISTORY */}
              {activeResponseItem.workflow_history && activeResponseItem.workflow_history.length > 0 && (
                <div className="p-4 bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 rounded-2xl space-y-3">
                  <h4 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                    <History className="w-4 h-4 text-sky-500" />
                    Workflow Timeline &amp; Audit Trail
                  </h4>

                  <div className="space-y-2">
                    {activeResponseItem.workflow_history.map((hist) => (
                      <div
                        key={hist.id}
                        className="p-2.5 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-100 dark:border-zinc-800 text-[11px] flex items-start justify-between gap-2"
                      >
                        <div>
                          <div className="font-bold text-zinc-800 dark:text-zinc-200">{hist.action}</div>
                          <div className="text-zinc-500">{hist.message}</div>
                        </div>
                        <div className="text-zinc-400 whitespace-nowrap">
                          {new Date(hist.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Modal>
        )}

        {/* ------------------------------------------------------------- */}
        {/* 5. RETURN MODAL (MANDATORY REASON PROMPT)                     */}
        {/* ------------------------------------------------------------- */}
        {isReturnModalOpen && (
          <Modal
            isOpen={true}
            onClose={() => setIsReturnModalOpen(false)}
            title="Return Form Response"
            description="Provide a clear, mandatory reason and corrective action items for the submitter."
            size="md"
          >
            <div className="space-y-4 text-xs">
              <div>
                <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                  Return Reason <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={3}
                  value={returnReason}
                  onChange={(e) => setReturnReason(e.target.value)}
                  placeholder="Explain exactly what deficiencies need correction..."
                  className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                />
              </div>

              <div>
                <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                  Reviewer Internal Remarks (Optional)
                </label>
                <input
                  type="text"
                  value={reviewerRemarks}
                  onChange={(e) => setReviewerRemarks(e.target.value)}
                  placeholder="Additional reviewer notes"
                  className="w-full p-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                />
              </div>

              <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => setIsReturnModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={isReviewing}
                  onClick={() => handleReviewDecision('RETURN')}
                  className="bg-rose-600 hover:bg-rose-700 text-white"
                >
                  {isReviewing ? <Spinner size="sm" /> : <RotateCcw className="w-3.5 h-3.5 mr-1" />}
                  Confirm Return
                </Button>
              </div>
            </div>
          </Modal>
        )}

        {/* ------------------------------------------------------------- */}
        {/* 6. FORWARD / SHARE MODAL                                      */}
        {/* ------------------------------------------------------------- */}
        {isForwardModalOpen && (
          <Modal
            isOpen={true}
            onClose={() => setIsForwardModalOpen(false)}
            title="Forward Form Response"
            description="Route this response instance to another authorized coordinator or vertical lead."
            size="md"
          >
            <div className="space-y-4 text-xs">
              <UserSelector
                usage="assignment"
                label="Target Recipient"
                required
                placeholder="Search and select recipient user..."
                value={forwardTargetUserId}
                onChange={(val) => setForwardTargetUserId(val || '')}
              />

              <div>
                <label className="block font-bold text-zinc-700 dark:text-zinc-300 mb-1">
                  Forwarding Note / Instructions <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={2}
                  value={forwardMessage}
                  onChange={(e) => setForwardMessage(e.target.value)}
                  placeholder="e.g. Please verify medical compliance for this team."
                  className="w-full p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                />
              </div>

              <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => setIsForwardModalOpen(false)}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" disabled={isForwarding} onClick={handleForwardResponse}>
                  {isForwarding ? <Spinner size="sm" /> : <Share2 className="w-3.5 h-3.5 mr-1" />}
                  Forward Response
                </Button>
              </div>
            </div>
          </Modal>
        )}
      </div>
    </AppShell>
  );
}
