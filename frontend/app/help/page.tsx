'use client';

/**
 * Operational Help & FAQ Directory (/help)
 * Authoritative operational FAQs, official procedures, and event workflows.
 */

import React, { useState, useEffect } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { useAuth } from '@/hooks/useAuth';
import { faqsApi, ApiException } from '@/lib/api';
import { FAQResponse, FAQStatus } from '@/types/faq';
import {
  HelpCircle,
  Search,
  BookOpen,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Plus,
  Edit2,
  Trash2,
  RefreshCw,
} from 'lucide-react';

export default function HelpPage() {
  const { user, hasRole } = useAuth();
  const [faqs, setFaqs] = useState<FAQResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // FAQ Editor Modal state
  const [isFaqModalOpen, setIsFaqModalOpen] = useState<boolean>(false);
  const [editingFaq, setEditingFaq] = useState<FAQResponse | null>(null);
  const [faqForm, setFaqForm] = useState<{
    question: string;
    answer: string;
    category: string;
    display_order: number;
    status: FAQStatus;
    related_route: string;
    route_label: string;
  }>({
    question: '',
    answer: '',
    category: 'Daily Operations',
    display_order: 0,
    status: 'PUBLISHED',
    related_route: '',
    route_label: '',
  });
  const [faqSubmitting, setFaqSubmitting] = useState<boolean>(false);
  const [faqFormError, setFaqFormError] = useState<string | null>(null);

  const canManageFaqs = hasRole('ADMIN') || hasRole('SPORTS_CORE') || hasRole('DEPUTY_CORE');

  const categories = [
    'ALL',
    'Daily Operations',
    'Account & Identity',
    'Governance & Compliance',
    'Work Management',
    'Risk & Escalation',
    'Events & Operations',
    'Coordination',
    'General',
  ];

  // Fetch FAQs from PostgreSQL
  useEffect(() => {
    let active = true;
    async function fetchFaqs() {
      try {
        const res = await faqsApi.list({ limit: 100 });
        if (active) {
          setFaqs(res.items || []);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          if (err instanceof ApiException) setErrorMsg(err.message);
          else if (err instanceof Error) setErrorMsg(err.message);
          setLoading(false);
        }
      }
    }
    fetchFaqs();
    return () => {
      active = false;
    };
  }, [refreshTrigger]);

  const filteredFaqs = faqs.filter((f) => {
    const matchesSearch =
      f.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.answer.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCat = selectedCategory === 'ALL' || f.category === selectedCategory;
    return matchesSearch && matchesCat;
  });

  const handleOpenCreateFaq = () => {
    setEditingFaq(null);
    setFaqForm({
      question: '',
      answer: '',
      category: 'Daily Operations',
      display_order: faqs.length + 1,
      status: 'PUBLISHED',
      related_route: '',
      route_label: '',
    });
    setFaqFormError(null);
    setIsFaqModalOpen(true);
  };

  const handleOpenEditFaq = (faq: FAQResponse) => {
    setEditingFaq(faq);
    setFaqForm({
      question: faq.question,
      answer: faq.answer,
      category: faq.category,
      display_order: faq.display_order,
      status: faq.status,
      related_route: faq.related_route || '',
      route_label: faq.route_label || '',
    });
    setFaqFormError(null);
    setIsFaqModalOpen(true);
  };

  const handleSaveFaq = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!faqForm.question.trim() || !faqForm.answer.trim()) {
      setFaqFormError('Question and Answer are required.');
      return;
    }

    setFaqSubmitting(true);
    setFaqFormError(null);

    try {
      if (editingFaq) {
        await faqsApi.update(editingFaq.id, {
          question: faqForm.question.trim(),
          answer: faqForm.answer.trim(),
          category: faqForm.category.trim(),
          display_order: Number(faqForm.display_order),
          status: faqForm.status,
          related_route: faqForm.related_route.trim() || undefined,
          route_label: faqForm.route_label.trim() || undefined,
        });
      } else {
        await faqsApi.create({
          question: faqForm.question.trim(),
          answer: faqForm.answer.trim(),
          category: faqForm.category.trim(),
          display_order: Number(faqForm.display_order),
          status: faqForm.status,
          related_route: faqForm.related_route.trim() || undefined,
          route_label: faqForm.route_label.trim() || undefined,
        });
      }
      setIsFaqModalOpen(false);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setFaqFormError(err.message);
      else if (err instanceof Error) setFaqFormError(err.message);
    } finally {
      setFaqSubmitting(false);
    }
  };

  const handleDeleteFaq = async (id: string) => {
    if (!confirm('Are you sure you want to delete this FAQ?')) return;
    try {
      await faqsApi.delete(id);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiException) setErrorMsg(err.message);
    }
  };

  return (
    <AppShell isEventTeamAllowed={true}>
      <div className="space-y-6 max-w-6xl mx-auto">
        {/* Header Title Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-indigo-950/30 via-sky-950/20 to-zinc-900 border border-indigo-200/50 dark:border-indigo-800/40">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                <HelpCircle className="w-5 h-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                Help & Frequently Asked Questions
              </h1>
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Official operational workflows, system guidance, answers to common procedures, and policy FAQs.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {canManageFaqs && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleOpenCreateFaq}
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                New FAQ
              </Button>
            )}
          </div>
        </div>

        {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

        {/* Search & Category Filter Toolbar */}
        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                placeholder="Search FAQs by question, keyword, or workflow (e.g. daily report, directives, tasks)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400"
              />
            </div>

            {/* Category Chips */}
            <div className="flex items-center gap-1.5 overflow-x-auto pt-1 pb-1">
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                    selectedCategory === cat
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                  }`}
                >
                  {cat === 'ALL' ? 'All Categories' : cat}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* FAQs Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-indigo-500" />
              Frequently Asked Questions ({filteredFaqs.length})
            </h2>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs px-2"
              onClick={() => setRefreshTrigger((prev) => prev + 1)}
            >
              <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </div>

          {loading ? (
            <div className="p-8 flex justify-center">
              <Spinner size="md" />
            </div>
          ) : filteredFaqs.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-zinc-500 text-xs">
                No FAQs found matching the selected criteria.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {filteredFaqs.map((faq, idx) => {
                const isOpen = openFaqIndex === idx;
                return (
                  <div
                    key={faq.id}
                    className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden transition-all"
                  >
                    <div className="flex items-center justify-between pr-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                      <button
                        type="button"
                        onClick={() => setOpenFaqIndex(isOpen ? null : idx)}
                        className="w-full p-4 text-left flex items-center justify-between gap-3"
                      >
                        <div className="space-y-0.5 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 block">
                              {faq.category}
                            </span>
                            {faq.status !== 'PUBLISHED' && (
                              <span className="text-[9px] px-1.5 py-0.2 bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 rounded font-semibold">
                                {faq.status}
                              </span>
                            )}
                          </div>
                          <span className="font-semibold text-xs text-zinc-900 dark:text-zinc-100 block">
                            {faq.question}
                          </span>
                        </div>

                        <div className="text-zinc-400 shrink-0">
                          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </div>
                      </button>

                      {canManageFaqs && (
                        <div className="flex items-center gap-1 shrink-0 ml-2">
                          <button
                            type="button"
                            onClick={() => handleOpenEditFaq(faq)}
                            className="text-zinc-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                            title="Edit FAQ"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteFaq(faq.id)}
                            className="text-zinc-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                            title="Delete FAQ"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>

                    {isOpen && (
                      <div className="p-4 pt-0 text-xs text-zinc-600 dark:text-zinc-300 leading-relaxed border-t border-zinc-100 dark:border-zinc-800/80 space-y-3">
                        <p className="pt-3 whitespace-pre-wrap">{faq.answer}</p>
                        {faq.related_route && (
                          <div>
                            <a
                              href={faq.related_route}
                              className="inline-flex items-center gap-1 font-semibold text-indigo-600 dark:text-indigo-400 hover:underline text-[11px]"
                            >
                              <span>{faq.route_label || 'Navigate to Workspace'}</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* FAQ Create / Edit Modal */}
        {isFaqModalOpen && (
          <Modal
            isOpen={true}
            onClose={() => setIsFaqModalOpen(false)}
            title={editingFaq ? 'Edit Operational FAQ' : 'Create Operational FAQ'}
            description="Manage knowledge base answers and official procedural guidance."
            size="lg"
          >
            <form onSubmit={handleSaveFaq} className="space-y-4 text-xs">
              {faqFormError && <Alert variant="danger">{faqFormError}</Alert>}

              <div>
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                  Question *
                </label>
                <Input
                  required
                  placeholder="e.g. How do I convert a meeting action item to a task?"
                  value={faqForm.question}
                  onChange={(e) => setFaqForm({ ...faqForm, question: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                    Category *
                  </label>
                  <select
                    value={faqForm.category}
                    onChange={(e) => setFaqForm({ ...faqForm, category: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="Daily Operations">Daily Operations</option>
                    <option value="Account & Identity">Account & Identity</option>
                    <option value="Governance & Compliance">Governance & Compliance</option>
                    <option value="Work Management">Work Management</option>
                    <option value="Risk & Escalation">Risk & Escalation</option>
                    <option value="Events & Operations">Events & Operations</option>
                    <option value="Coordination">Coordination</option>
                    <option value="General">General</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                    Status *
                  </label>
                  <select
                    value={faqForm.status}
                    onChange={(e) => setFaqForm({ ...faqForm, status: e.target.value as FAQStatus })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="PUBLISHED">Published</option>
                    <option value="DRAFT">Draft</option>
                    <option value="ARCHIVED">Archived</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                    Display Order
                  </label>
                  <Input
                    type="number"
                    value={faqForm.display_order}
                    onChange={(e) => setFaqForm({ ...faqForm, display_order: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                  Answer *
                </label>
                <textarea
                  rows={4}
                  required
                  placeholder="Provide detailed procedural steps or operational explanation..."
                  value={faqForm.answer}
                  onChange={(e) => setFaqForm({ ...faqForm, answer: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                    Related Workspace Route
                  </label>
                  <Input
                    placeholder="e.g. /tasks, /reports, /meetings"
                    value={faqForm.related_route}
                    onChange={(e) => setFaqForm({ ...faqForm, related_route: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                    Route Label
                  </label>
                  <Input
                    placeholder="e.g. Go to Tasks"
                    value={faqForm.route_label}
                    onChange={(e) => setFaqForm({ ...faqForm, route_label: e.target.value })}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100 dark:border-zinc-800">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsFaqModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" size="sm" isLoading={faqSubmitting}>
                  {editingFaq ? 'Update FAQ' : 'Create FAQ'}
                </Button>
              </div>
            </form>
          </Modal>
        )}
      </div>
    </AppShell>
  );
}
