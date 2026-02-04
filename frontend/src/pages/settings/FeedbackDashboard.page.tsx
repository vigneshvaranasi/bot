import React, { useEffect, useState, useCallback } from "react";
import { Button } from "../../components/ui/Button";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { toast } from "react-hot-toast";
import { logger } from "../../utils/logger";
import { SkeletonTable } from "../../components/ui/Skeleton";
import Modal, { ConfirmModal } from "../../components/ui/Modal";
import { Pagination, DEFAULT_PAGE_SIZE_OPTIONS } from "../../components/ui/Pagination";
import { useDelayedLoading } from "../../hooks/useDelayedLoading";
import Toggle from "../../components/ui/Toggle";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";
import type { FeedbackItem, FeedbackStats, FeedbackSettings } from "../../types";
import {
  fetchFeedbackList,
  fetchFeedbackStats,
  fetchFeedbackSettings,
  updateFeedbackSettings,
  resolveFeedback,
  dismissFeedback,
  deleteFeedback,
  restoreFeedback,
  updateGoldenExample,
} from "../../handlers/feedbackHandler";

marked.setOptions({
  breaks: true,
  gfm: true
});

function renderMarkdown(content: string): string {
  try {
    const htmlContent = marked.parse(content) as string;
    return DOMPurify.sanitize(htmlContent, {
      ALLOWED_TAGS: [
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'code', 'pre', 
        'strong', 'em', 'blockquote', 'br', 'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
      ],
      ADD_ATTR: ['class', 'href', 'target', 'rel'],
    });
  } catch (error) {
    console.error('Markdown parsing error:', error);
    return content;
  }
}

const DEFAULT_PAGE_SIZE = 10;


const FeedbackDashboard: React.FC = () => {
  const { hasPermission } = usePermissions();
  
  const canViewFeedback = hasPermission(PERMISSIONS.FEEDBACK_VIEW);
  const canManageFeedback = hasPermission(PERMISSIONS.FEEDBACK_MANAGE);
  const canEditGoldenExamples = hasPermission(PERMISSIONS.GOLDEN_EXAMPLE_EDIT);

  const [feedbackList, setFeedbackList] = useState<FeedbackItem[]>([]);
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [settings, setSettings] = useState<FeedbackSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingList, setLoadingList] = useState(false);

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [totalItems, setTotalItems] = useState(0);

  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');

  const [selectedFeedback, setSelectedFeedback] = useState<FeedbackItem | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [goldenResponse, setGoldenResponse] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAiResponseExpanded, setIsAiResponseExpanded] = useState(false);
  const [isGoldenResponseExpanded, setIsGoldenResponseExpanded] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedGoldenResponse, setEditedGoldenResponse] = useState('');

  const [savingSettings, setSavingSettings] = useState(false);

  const showLoading = useDelayedLoading(loading);
  const showListLoading = useDelayedLoading(loadingList);

  const loadData = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
      const [statsData, settingsData] = await Promise.all([
        fetchFeedbackStats(token),
        fetchFeedbackSettings(token),
      ]);
      setStats(statsData);
      setSettings(settingsData);
    } catch (error) {
      logger.error('Failed to load feedback data', error);
      toast.error('Failed to load feedback data');
    }
  }, []);

  const loadFeedbackList = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;

    setLoadingList(true);
    try {
      const offset = (currentPage - 1) * pageSize;
      const data = await fetchFeedbackList(
        token,
        pageSize,
        offset,
        statusFilter || undefined,
        typeFilter || undefined,
        searchTerm || undefined
      );
      setFeedbackList(data.items);
      setTotalItems(data.total);
    } catch (error) {
      logger.error('Failed to load feedback list', error);
      toast.error('Failed to load feedback list');
    } finally {
      setLoadingList(false);
    }
  }, [currentPage, pageSize, statusFilter, typeFilter, searchTerm]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await loadData();
      await loadFeedbackList();
      setLoading(false);
    };
    init();
  }, []);

  useEffect(() => {
    loadFeedbackList();
  }, [currentPage, pageSize, statusFilter, typeFilter]);

  const handleSearch = () => {
    setCurrentPage(1);
    loadFeedbackList();
  };

  const handleViewDetails = (feedback: FeedbackItem) => {
    setSelectedFeedback(feedback);
    setGoldenResponse(feedback.original_response);
    setIsAiResponseExpanded(false);
    setIsGoldenResponseExpanded(false);
    setIsEditing(false);
    setEditedGoldenResponse('');
    setIsDetailModalOpen(true);
  };

  const handleResolve = async () => {
    if (!selectedFeedback) return;

    const token = localStorage.getItem('token');
    if (!token) return;

    setIsSubmitting(true);
    try {
      const responseToSend = selectedFeedback.feedback_type === 'negative' 
        ? goldenResponse 
        : undefined;
      
      await resolveFeedback(token, selectedFeedback.id, responseToSend);
      toast.success('Feedback resolved and golden example created');
      setIsDetailModalOpen(false);
      loadFeedbackList();
      loadData();
    } catch (error: any) {
      toast.error(error.message || 'Failed to resolve feedback');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDismiss = async () => {
    if (!selectedFeedback) return;

    const token = localStorage.getItem('token');
    if (!token) return;

    setIsSubmitting(true);
    try {
      await dismissFeedback(token, selectedFeedback.id);
      toast.success('Feedback dismissed');
      setIsDetailModalOpen(false);
      loadFeedbackList();
      loadData();
    } catch (error) {
      toast.error('Failed to dismiss feedback');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedFeedback) return;

    const token = localStorage.getItem('token');
    if (!token) return;

    setIsSubmitting(true);
    try {
      await deleteFeedback(token, selectedFeedback.id);
      toast.success(
        selectedFeedback.has_golden_example 
          ? 'Feedback and golden example deleted' 
          : 'Feedback deleted'
      );
      setIsDeleteConfirmOpen(false);
      setIsDetailModalOpen(false);
      loadFeedbackList();
      loadData();
    } catch (error: any) {
      toast.error(error.message || 'Failed to delete feedback');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRestore = async () => {
    if (!selectedFeedback) return;

    const token = localStorage.getItem('token');
    if (!token) return;

    setIsSubmitting(true);
    try {
      await restoreFeedback(token, selectedFeedback.id);
      toast.success('Feedback restored to pending');
      setIsDetailModalOpen(false);
      loadFeedbackList();
      loadData();
    } catch (error: any) {
      toast.error(error.message || 'Failed to restore feedback');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartEdit = () => {
    if (selectedFeedback?.golden_response) {
      setEditedGoldenResponse(selectedFeedback.golden_response);
      setIsEditing(true);
      setIsGoldenResponseExpanded(true);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedGoldenResponse('');
  };

  const handleSaveEdit = async () => {
    if (!selectedFeedback?.golden_example_id) return;

    const token = localStorage.getItem('token');
    if (!token) return;

    setIsSubmitting(true);
    try {
      await updateGoldenExample(token, selectedFeedback.golden_example_id, editedGoldenResponse);
      toast.success('Golden example updated');
      setIsEditing(false);
      setSelectedFeedback({
        ...selectedFeedback,
        golden_response: editedGoldenResponse,
      });
      loadFeedbackList();
    } catch (error: any) {
      toast.error(error.message || 'Failed to update golden example');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSettingChange = async (key: keyof FeedbackSettings, value: boolean) => {
    const token = localStorage.getItem('token');
    if (!token || !settings) return;

    setSavingSettings(true);
    try {
      const updated = await updateFeedbackSettings(token, { [key]: value });
      setSettings(updated);
      toast.success('Settings updated');
    } catch (error) {
      toast.error('Failed to update settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-amber-50 text-amber-700 border border-amber-200',
      auto_approved: 'bg-sky-50 text-sky-700 border border-sky-200',
      reviewed: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
      dismissed: 'bg-slate-50 text-slate-600 border border-slate-200',
    };
    const labels: Record<string, string> = {
      pending: 'Pending',
      auto_approved: 'Auto Approved',
      reviewed: 'Reviewed',
      dismissed: 'Dismissed',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles[status] || 'bg-slate-50 text-slate-600'}`}>
        {labels[status] || status}
      </span>
    );
  };

  const getTypeBadge = (type: string) => {
    return type === 'positive' ? (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        Positive
      </span>
    ) : (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
        Negative
      </span>
    );
  };

  if (showLoading) {
    return (
      <div className="space-y-6">
        <SettingsHeader
          title="Feedback Dashboard"
          description="Review and manage user feedback on AI responses"
        />
        <div className="border border-gray-200 rounded-lg p-4">
          <SkeletonTable rows={5} columns={6} />
        </div>
      </div>
    );
  }

  if (!canViewFeedback) {
    return (
      <div className="space-y-6">
        <SettingsHeader
          title="Feedback Dashboard"
          description="Review and manage user feedback on AI responses"
        />
        <div className="border border-gray-200 rounded-lg p-6 text-center">
          <div className="text-gray-400 mb-2">
            <svg className="w-12 h-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-1">Access Denied</h3>
          <p className="text-sm text-gray-500">You don't have permission to view the Feedback Dashboard.</p>
          <p className="text-xs text-gray-400 mt-2">Required permission: feedback.view</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Feedback Dashboard"
        description="Review and manage user feedback on AI responses"
      />

      {stats && (
        <section className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-900">Overview</h3>
            <Button variant="secondary" onClick={() => { loadData(); loadFeedbackList(); }} className="text-xs">
              Refresh
            </Button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <p className="text-2xl font-semibold text-slate-900">{stats.total_feedback}</p>
              <p className="text-xs text-slate-500 mt-1">Total Feedback</p>
            </div>
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
              <p className="text-2xl font-semibold text-amber-700">{stats.pending_count}</p>
              <p className="text-xs text-amber-600 mt-1">Pending Review</p>
            </div>
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
              <p className="text-2xl font-semibold text-emerald-700">{stats.positive_count}</p>
              <p className="text-xs text-emerald-600 mt-1">Positive</p>
            </div>
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200">
              <p className="text-2xl font-semibold text-rose-700">{stats.negative_count}</p>
              <p className="text-xs text-rose-600 mt-1">Negative</p>
            </div>
            <div className="p-3 rounded-lg bg-violet-50 border border-violet-200">
              <p className="text-2xl font-semibold text-violet-700">{stats.golden_examples_count}</p>
              <p className="text-xs text-violet-600 mt-1">Golden Examples</p>
            </div>
          </div>
        </section>
      )}

      {settings && canManageFeedback && (
        <section className="border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Auto-Approval Settings</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center justify-between p-3 rounded-lg border border-gray-200 bg-white">
              <div>
                <p className="text-sm font-medium text-gray-900">Auto-approve Positive Feedback</p>
                <p className="text-xs text-gray-500">Automatically add to golden examples</p>
              </div>
              <Toggle
                enabled={settings.auto_approve_positive}
                onChange={(v) => handleSettingChange('auto_approve_positive', v)}
                disabled={savingSettings}
              />
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg border border-gray-200 bg-white">
              <div>
                <p className="text-sm font-medium text-gray-900">Auto-approve Negative Feedback</p>
                <p className="text-xs text-amber-600">Not recommended</p>
              </div>
              <Toggle
                enabled={settings.auto_approve_negative}
                onChange={(v) => handleSettingChange('auto_approve_negative', v)}
                disabled={savingSettings}
              />
            </div>
          </div>
        </section>
      )}

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Feedback List</h3>
          <p className="text-xs text-gray-500">{totalItems} item(s)</p>
        </div>

        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-gray-400 cursor-pointer"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="auto_approved">Auto Approved</option>
            <option value="reviewed">Reviewed</option>
            <option value="dismissed">Dismissed</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setCurrentPage(1); }}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-gray-400 cursor-pointer"
          >
            <option value="">All Types</option>
            <option value="positive">Positive</option>
            <option value="negative">Negative</option>
          </select>

          <div className="flex gap-2 flex-1 max-w-xs">
            <input
              type="text"
              placeholder="Search queries..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-gray-400"
            />
            <Button variant="secondary" onClick={handleSearch} className="text-xs cursor-pointer">
              Search
            </Button>
          </div>
        </div>

        {showListLoading ? (
          <SkeletonTable rows={5} columns={6} />
        ) : feedbackList.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-sm border border-dashed border-gray-300 rounded-lg bg-gray-50">
            No feedback found. User feedback will appear here.
          </div>
        ) : (
          <>
            <div className="overflow-x-auto bg-white rounded-lg border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">Type</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">Query</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">Reason</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">User</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">Date</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {feedbackList.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap">{getTypeBadge(item.feedback_type)}</td>
                      <td className="px-4 py-3">
                        <p className="text-sm text-gray-900 max-w-[180px] truncate" title={item.original_query}>
                          {item.original_query}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm text-gray-500 max-w-[140px] truncate" title={item.reason || ''}>
                          {item.reason || '—'}
                        </p>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">{getStatusBadge(item.status)}</td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <p className="text-sm text-gray-600">{item.user_email || 'Anonymous'}</p>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <p className="text-sm text-gray-500">{new Date(item.created_at).toLocaleDateString()}</p>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <Button
                          variant={item.status === 'pending' ? 'primary' : 'secondary'}
                          onClick={() => handleViewDetails(item)}
                          className="text-xs"
                        >
                          {item.status === 'pending' ? 'Review' : 'View'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              currentPage={currentPage}
              totalPages={Math.ceil(totalItems / pageSize)}
              totalItems={totalItems}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={(size) => { setPageSize(size); setCurrentPage(1); }}
              pageSizeOptions={DEFAULT_PAGE_SIZE_OPTIONS}
            />
          </>
        )}
      </section>

      <Modal
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        title="Feedback Details"
        size="4xl"
        footer={
          <div className="flex items-center justify-between w-full">
            {selectedFeedback?.status === 'pending' ? (
              <>
                <div className="flex items-center gap-2">
                  {canManageFeedback && (
                    <button
                      type="button"
                      onClick={() => setIsDeleteConfirmOpen(true)}
                      disabled={isSubmitting}
                      className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      Delete
                    </button>
                  )}
                  {canManageFeedback && (
                    <button
                      type="button"
                      onClick={handleDismiss}
                      disabled={isSubmitting}
                      className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      Dismiss
                    </button>
                  )}
                </div>
                <div>
                  {canManageFeedback && (
                    <Button
                      variant="primary"
                      onClick={handleResolve}
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? 'Saving...' : 'Create Golden Example'}
                    </Button>
                  )}
                </div>
              </>
            ) : selectedFeedback?.status === 'dismissed' ? (
              <>
                <div className="flex items-center gap-2">
                  {canManageFeedback && (
                    <button
                      type="button"
                      onClick={() => setIsDeleteConfirmOpen(true)}
                      disabled={isSubmitting}
                      className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      Delete
                    </button>
                  )}
                </div>
                <div>
                  {canManageFeedback && (
                    <Button
                      variant="secondary"
                      onClick={handleRestore}
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? 'Restoring...' : 'Restore to Pending'}
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <>
                <div>
                  {canManageFeedback && (
                    <button
                      type="button"
                      onClick={() => setIsDeleteConfirmOpen(true)}
                      disabled={isSubmitting}
                      className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      Delete
                    </button>
                  )}
                </div>
                <div></div>
              </>
            )}
          </div>
        }
      >
        {selectedFeedback && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {getTypeBadge(selectedFeedback.feedback_type)}
              {getStatusBadge(selectedFeedback.status)}
              {selectedFeedback.has_golden_example && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200">
                  Has Golden Example
                </span>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                User Query
              </label>
              <div className="p-3 bg-slate-50 rounded-lg text-sm border border-slate-200 text-gray-900">
                {selectedFeedback.original_query}
              </div>
            </div>

            {selectedFeedback.reason && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  User's Feedback Reason
                </label>
                <div className="p-3 bg-amber-50 rounded-lg text-sm border border-amber-200 text-amber-800">
                  {selectedFeedback.reason}
                </div>
              </div>
            )}

            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setIsAiResponseExpanded(!isAiResponseExpanded)}
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left cursor-pointer"
              >
                <span className="text-sm font-medium text-gray-700">AI Response</span>
                <svg
                  className={`w-5 h-5 text-gray-500 transition-transform ${isAiResponseExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {isAiResponseExpanded && (
                <div 
                  className="p-4 bg-white max-h-[350px] overflow-y-auto markdown-body border-t border-gray-200"
                  dangerouslySetInnerHTML={{ 
                    __html: renderMarkdown(selectedFeedback.original_response) 
                  }}
                />
              )}
            </div>

            {selectedFeedback.has_golden_example && selectedFeedback.golden_response && selectedFeedback.status !== 'pending' && (
              <div className="border border-violet-200 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setIsGoldenResponseExpanded(!isGoldenResponseExpanded)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-violet-50 hover:bg-violet-100 transition-colors text-left cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-violet-700">Golden Response</span>
                    {!isEditing && canEditGoldenExamples && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartEdit();
                        }}
                        className="text-xs text-violet-500 hover:text-violet-700 hover:bg-violet-100 px-2 py-0.5 rounded transition-colors cursor-pointer"
                      >
                        Edit
                      </button>
                    )}
                  </div>
                  <svg
                    className={`w-5 h-5 text-violet-500 transition-transform ${isGoldenResponseExpanded ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {isGoldenResponseExpanded && (
                  <div className="border-t border-violet-200">
                    {isEditing ? (
                      <div className="p-4">
                        <textarea
                          value={editedGoldenResponse}
                          onChange={(e) => setEditedGoldenResponse(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-gray-400 text-sm"
                          rows={10}
                          placeholder="Edit the golden response..."
                        />
                        <div className="flex justify-end gap-2 mt-3">
                          <button
                            type="button"
                            onClick={handleCancelEdit}
                            disabled={isSubmitting}
                            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={handleSaveEdit}
                            disabled={isSubmitting || !editedGoldenResponse.trim()}
                            className="px-3 py-1.5 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                          >
                            {isSubmitting ? 'Saving...' : 'Save Changes'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div 
                        className="p-4 bg-white max-h-[350px] overflow-y-auto markdown-body"
                        dangerouslySetInnerHTML={{ 
                          __html: renderMarkdown(selectedFeedback.golden_response) 
                        }}
                      />
                    )}
                  </div>
                )}
              </div>
            )}

            {selectedFeedback.status === 'pending' && selectedFeedback.feedback_type === 'negative' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Golden Response
                  <span className="font-normal text-gray-500 ml-1">(Write the ideal response)</span>
                </label>
                <textarea
                  value={goldenResponse}
                  onChange={(e) => setGoldenResponse(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-gray-400 text-sm"
                  rows={8}
                  placeholder="Write the ideal response that the AI should have given..."
                />
                <p className="text-xs text-gray-500 mt-1.5">
                  This response will be used as a golden example to improve future AI responses.
                </p>
              </div>
            )}

            {selectedFeedback.status === 'pending' && selectedFeedback.feedback_type === 'positive' && (
              <div className="p-3 bg-emerald-50 rounded-lg text-sm text-emerald-700 border border-emerald-200">
                Approving this will create a golden example using the original AI response shown above.
              </div>
            )}

            <div className="pt-3 border-t border-gray-200 text-xs text-gray-500 space-y-0.5">
              <p><span className="text-gray-600">User:</span> {selectedFeedback.user_email || 'Anonymous'}</p>
              <p><span className="text-gray-600">Submitted:</span> {new Date(selectedFeedback.created_at).toLocaleString()}</p>
              {selectedFeedback.reviewed_at && (
                <p><span className="text-gray-600">Reviewed:</span> {new Date(selectedFeedback.reviewed_at).toLocaleString()} by {selectedFeedback.reviewer_email}</p>
              )}
            </div>
          </div>
        )}
      </Modal>

      <ConfirmModal
        isOpen={isDeleteConfirmOpen}
        onClose={() => setIsDeleteConfirmOpen(false)}
        onConfirm={handleDelete}
        title="Delete Feedback"
        message={
          selectedFeedback?.has_golden_example
            ? "This will permanently delete the feedback and its associated golden example. The golden example will be removed from the AI's knowledge. This action cannot be undone."
            : "This will permanently delete the feedback. This action cannot be undone."
        }
        confirmLabel={isSubmitting ? "Deleting..." : "Delete"}
        confirmVariant="danger"
        isLoading={isSubmitting}
      />
    </div>
  );
};

export default FeedbackDashboard;
