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
import InfoHint from "../../components/ui/InfoHint";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";
import type { FeedbackItem, FeedbackStats, FeedbackSettings, QueryType } from "../../types";
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
  generateGoldenResponse,
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

function aiValidationAccepted(aiValidated: string | null | undefined): boolean {
  return String(aiValidated ?? "").toLowerCase() === "valid";
}

function aiValidationRejected(aiValidated: string | null | undefined): boolean {
  return String(aiValidated ?? "").toLowerCase() === "invalid";
}

function feedbackHasAiValidation(f: FeedbackItem): boolean {
  return (
    (f.ai_validated != null && String(f.ai_validated).trim() !== "") ||
    Boolean(f.ai_reason && f.ai_reason.trim() !== "")
  );
}

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
  const [isAiValidationExpanded, setIsAiValidationExpanded] = useState(false);
  const [isAiResponseExpanded, setIsAiResponseExpanded] = useState(false);
  const [isGoldenResponseExpanded, setIsGoldenResponseExpanded] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedGoldenResponse, setEditedGoldenResponse] = useState('');
  const [queryType, setQueryType] = useState<QueryType>('static');

  const [isGenerating, setIsGenerating] = useState(false);
  const [hasGenerated, setHasGenerated] = useState(false);
  const [generationInfo, setGenerationInfo] = useState<{ toolCalls: number; timeMs: number } | null>(null);
  const [goldenResponseTab, setGoldenResponseTab] = useState<'edit' | 'preview'>('edit');
  const [editGoldenResponseTab, setEditGoldenResponseTab] = useState<'edit' | 'preview'>('edit');

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
    setQueryType(feedback.query_type || 'static');
    setIsAiValidationExpanded(feedbackHasAiValidation(feedback));
    setIsAiResponseExpanded(false);
    setIsGoldenResponseExpanded(false);
    setIsEditing(false);
    setEditedGoldenResponse('');
    setHasGenerated(false);
    setGenerationInfo(null);
    setGoldenResponseTab('edit');
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

      await resolveFeedback(token, selectedFeedback.id, responseToSend, queryType);
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
    } catch {
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

  const handleGenerateResponse = async (forEdit: boolean = false) => {
    if (!selectedFeedback) return;

    const token = localStorage.getItem('token');
    if (!token) return;

    setIsGenerating(true);
    setGenerationInfo(null);
    try {
      const result = await generateGoldenResponse(token, selectedFeedback.id);
      
      if (result.success) {
        if (forEdit) {
          setEditedGoldenResponse(result.generated_response);
        } else {
          setGoldenResponse(result.generated_response);
        }
        setHasGenerated(true);
        setGenerationInfo({
          toolCalls: result.tool_calls_made,
          timeMs: result.generation_time_ms,
        });
        toast.success('Response generated successfully');
      } else {
        toast.error(result.error || 'Failed to generate response');
      }
    } catch (error: any) {
      toast.error(error.message || 'Failed to generate response');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleStartEdit = () => {
    if (selectedFeedback?.golden_response) {
      setEditedGoldenResponse(selectedFeedback.golden_response);
      setIsEditing(true);
      setIsGoldenResponseExpanded(true);
      setEditGoldenResponseTab('edit');
      setHasGenerated(false);
      setGenerationInfo(null);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedGoldenResponse('');
    setEditGoldenResponseTab('edit');
    setHasGenerated(false);
    setGenerationInfo(null);
  };

  const handleSaveEdit = async () => {
    if (!selectedFeedback?.golden_example_id) return;

    const token = localStorage.getItem('token');
    if (!token) return;

    setIsSubmitting(true);
    try {
      await updateGoldenExample(token, selectedFeedback.golden_example_id, editedGoldenResponse, queryType);
      toast.success('Golden example updated');
      setIsEditing(false);
      setSelectedFeedback({
        ...selectedFeedback,
        golden_response: editedGoldenResponse,
        query_type: queryType,
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
    } catch {
      toast.error('Failed to update settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-warning-subtle text-warning-text border border-warning-border',
      auto_approved: 'bg-info-subtle text-info-text border border-info-border',
      ai_approved: 'bg-info-subtle text-info-text border border-info-border',
      ai_rejected: 'bg-danger-subtle text-danger-text border border-danger',
      reviewed: 'bg-success-subtle text-success-text border border-success',
      dismissed: 'bg-surface-tertiary text-text-secondary border border-border-default',
    };
    const labels: Record<string, string> = {
      pending: 'Pending',
      auto_approved: 'Auto Approved',
      ai_approved: 'Approved by AI',
      ai_rejected: 'Rejected by AI',
      reviewed: 'Reviewed',
      dismissed: 'Dismissed',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles[status] || 'bg-surface-tertiary text-text-secondary'}`}>
        {labels[status] || status}
      </span>
    );
  };

  const getTypeBadge = (type: string) => {
    return type === 'positive' ? (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-success-subtle text-success-text border border-success">
        Positive
      </span>
    ) : (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-danger-subtle text-danger-text border border-danger">
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
        <div className="border border-border-default rounded-lg p-4">
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
        <div className="border border-border-default rounded-lg p-6 text-center">
          <div className="text-text-tertiary mb-2">
            <svg className="w-12 h-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-text-primary mb-1">Access Denied</h3>
          <p className="text-sm text-text-secondary">You don't have permission to view the Feedback Dashboard.</p>
          <p className="text-xs text-text-tertiary mt-2">Required permission: feedback.view</p>
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
        <section className="border border-border-default rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-text-primary">Overview</h3>
            <Button variant="secondary" onClick={() => { loadData(); loadFeedbackList(); }} className="text-xs">
              Refresh
            </Button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <div className="p-3 rounded-lg bg-surface-tertiary border border-border-default">
              <p className="text-2xl font-semibold text-text-primary">{stats.total_feedback}</p>
              <p className="text-xs text-text-secondary mt-1">Total Feedback</p>
            </div>
            <div className="p-3 rounded-lg bg-warning-subtle border border-warning-border">
              <p className="text-2xl font-semibold text-warning-text">{stats.pending_count}</p>
              <p className="text-xs text-warning-text mt-1">Pending Review</p>
            </div>
            <div className="p-3 rounded-lg bg-success-subtle border border-success">
              <p className="text-2xl font-semibold text-success-text">{stats.positive_count}</p>
              <p className="text-xs text-success-text mt-1">Positive</p>
            </div>
            <div className="p-3 rounded-lg bg-danger-subtle border border-danger">
              <p className="text-2xl font-semibold text-danger-text">{stats.negative_count}</p>
              <p className="text-xs text-danger-text mt-1">Negative</p>
            </div>
            <div className="p-3 rounded-lg bg-info-subtle border border-info-border">
              <p className="text-2xl font-semibold text-info-text">{stats.golden_examples_count}</p>
              <div className="flex items-center gap-1">
                <p className="text-xs text-info-text mt-1">Golden Examples</p>
                <InfoHint text="Curated question-answer pairs that teach the AI how to respond better. Built from reviewed user feedback." />
              </div>
            </div>
          </div>
        </section>
      )}

      {settings && canManageFeedback && (
        <section className="flex items-center justify-between p-4 rounded-lg border border-border-default bg-surface-primary">
          <div>
            <div className="flex items-center gap-1">
              <h3 className="text-sm font-semibold text-text-primary">AI Auto-Approval</h3>
              <InfoHint text="When enabled, AI validates each feedback. Valid feedback becomes a golden example automatically; invalid feedback stays pending with the AI's reason." />
            </div>
            <p className="text-xs text-text-secondary mt-0.5">
              AI validates feedback and creates golden examples for the valid ones. Disable to review every feedback manually.
            </p>
          </div>
          <Toggle
            enabled={settings.auto_approve_by_ai}
            onChange={(v) => handleSettingChange('auto_approve_by_ai', v)}
            disabled={savingSettings}
          />
        </section>
      )}

      <section className="border border-border-default rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">Feedback List</h3>
          <p className="text-xs text-text-secondary">{totalItems} item(s)</p>
        </div>

        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
            className="px-3 py-1.5 text-sm border border-border-strong rounded-md bg-surface-primary text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-blue cursor-pointer"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="auto_approved">Auto Approved</option>
            <option value="ai_approved">Approved by AI</option>
            <option value="ai_rejected">Rejected by AI</option>
            <option value="reviewed">Reviewed</option>
            <option value="dismissed">Dismissed</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setCurrentPage(1); }}
            className="px-3 py-1.5 text-sm border border-border-strong rounded-md bg-surface-primary text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-blue cursor-pointer"
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
              className="flex-1 px-3 py-1.5 text-sm border border-border-strong rounded-md focus:outline-none focus:ring-1 focus:ring-gray-400"
            />
            <Button variant="secondary" onClick={handleSearch} className="text-xs cursor-pointer">
              Search
            </Button>
          </div>
        </div>

        {showListLoading ? (
          <SkeletonTable rows={5} columns={6} />
        ) : feedbackList.length === 0 ? (
          <div className="p-6 text-center text-text-secondary text-sm border border-dashed border-border-strong rounded-lg bg-surface-secondary">
            No feedback found. User feedback will appear here.
          </div>
        ) : (
          <>
            <div className="overflow-x-auto bg-surface-primary rounded-lg border border-border-default">
              <table className="min-w-full divide-y divide-border-default">
                <thead className="bg-surface-secondary">
                  <tr>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Type</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Query</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Reason</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Status</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">User</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Date</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {feedbackList.map((item) => (
                    <tr key={item.id} className="hover:bg-surface-secondary transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap">{getTypeBadge(item.feedback_type)}</td>
                      <td className="px-4 py-3">
                        <p className="text-sm text-text-primary max-w-[180px] truncate" title={item.original_query}>
                          {item.original_query}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm text-text-secondary max-w-[140px] truncate" title={item.reason || item.ai_reason || ''}>
                          {item.ai_reason ? `AI: ${item.ai_reason.substring(0, 50)}...` : (item.reason || '—')}
                        </p>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div title={item.ai_reason || ''}>
                          {getStatusBadge(item.status)}
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <p className="text-sm text-text-secondary">{item.user_email || 'Anonymous'}</p>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <p className="text-sm text-text-secondary">{new Date(item.created_at).toLocaleDateString()}</p>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <Button
                          variant={item.status === 'pending' || item.status === 'ai_rejected' ? 'primary' : 'secondary'}
                          onClick={() => handleViewDetails(item)}
                          className="text-xs"
                        >
                          {item.status === 'pending' || item.status === 'ai_rejected' ? 'Review' : 'View'}
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
            {selectedFeedback?.status === 'pending' || selectedFeedback?.status === 'ai_rejected' ? (
              <>
                <div className="flex items-center gap-2">
                  {canManageFeedback && (
                    <button
                      type="button"
                      onClick={() => setIsDeleteConfirmOpen(true)}
                      disabled={isSubmitting}
                      className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-danger-text hover:bg-danger-subtle rounded-lg disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      Delete
                    </button>
                  )}
                  {canManageFeedback && (
                    <button
                      type="button"
                      onClick={handleDismiss}
                      disabled={isSubmitting}
                      className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-secondary hover:bg-surface-tertiary rounded-lg disabled:opacity-50 transition-colors cursor-pointer"
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
                      className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-danger-text hover:bg-danger-subtle rounded-lg disabled:opacity-50 transition-colors cursor-pointer"
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
                      className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-danger-text hover:bg-danger-subtle rounded-lg disabled:opacity-50 transition-colors cursor-pointer"
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
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-info-subtle text-info-text border border-info-border">
                  Has Golden Example
                </span>
              )}
              {selectedFeedback.query_type && (
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                  selectedFeedback.query_type === 'temporal'
                    ? 'bg-warning-subtle text-warning-text border border-warning-border'
                    : 'bg-info-subtle text-info-text border border-info-border'
                }`}>
                  {selectedFeedback.query_type === 'temporal' ? 'Temporal Query' : 'Static Query'}
                </span>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                User Query
              </label>
              <div className="p-3 bg-surface-tertiary rounded-lg text-sm border border-border-default text-text-primary">
                {selectedFeedback.original_query}
              </div>
            </div>

            {selectedFeedback.reason && (
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">
                  User's Feedback Reason
                </label>
                <div className="p-3 bg-warning-subtle rounded-lg text-sm border border-warning-border text-warning-text">
                  {selectedFeedback.reason}
                </div>
              </div>
            )}

            {feedbackHasAiValidation(selectedFeedback) && (
              <div
                className={`rounded-lg overflow-hidden border ${
                  aiValidationAccepted(selectedFeedback.ai_validated)
                    ? "border-success"
                    : aiValidationRejected(selectedFeedback.ai_validated)
                      ? "border-danger"
                      : "border-border-default"
                }`}
              >
                <button
                  type="button"
                  onClick={() => setIsAiValidationExpanded(!isAiValidationExpanded)}
                  className={`w-full flex items-center justify-between px-4 py-3 transition-colors text-left cursor-pointer ${
                    aiValidationAccepted(selectedFeedback.ai_validated)
                      ? "bg-success-subtle hover:bg-success-subtle/80"
                      : aiValidationRejected(selectedFeedback.ai_validated)
                        ? "bg-danger-subtle hover:bg-danger-subtle/80"
                        : "bg-surface-secondary hover:bg-surface-tertiary"
                  }`}
                >
                  <span
                    className={`text-sm font-medium min-w-0 ${
                      aiValidationAccepted(selectedFeedback.ai_validated)
                        ? "text-success-text"
                        : aiValidationRejected(selectedFeedback.ai_validated)
                          ? "text-danger-text"
                          : "text-text-secondary"
                    }`}
                  >
                    AI validation
                  </span>
                  <svg
                    className={`w-5 h-5 shrink-0 ml-2 transition-transform ${
                      aiValidationAccepted(selectedFeedback.ai_validated)
                        ? "text-success-text"
                        : aiValidationRejected(selectedFeedback.ai_validated)
                          ? "text-danger-text"
                          : "text-text-secondary"
                    } ${isAiValidationExpanded ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>
                {isAiValidationExpanded && (
                  <div
                    className={`p-4 border-t text-sm ${
                      aiValidationAccepted(selectedFeedback.ai_validated)
                        ? "bg-surface-primary border-success text-success-text"
                        : aiValidationRejected(selectedFeedback.ai_validated)
                          ? "bg-surface-primary border-danger text-danger-text"
                          : "bg-surface-primary border-border-default text-text-primary"
                    }`}
                  >
                    {selectedFeedback.ai_reason ? (
                      <p className="whitespace-pre-wrap leading-relaxed">
                        {selectedFeedback.ai_reason}
                      </p>
                    ) : (
                      <p className="text-text-secondary italic">
                        No written explanation was stored for this verdict.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="border border-border-default rounded-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setIsAiResponseExpanded(!isAiResponseExpanded)}
                className="w-full flex items-center justify-between px-4 py-3 bg-surface-secondary hover:bg-surface-tertiary transition-colors text-left cursor-pointer"
              >
                <span className="text-sm font-medium text-text-secondary">AI Response</span>
                <svg
                  className={`w-5 h-5 text-text-secondary transition-transform ${isAiResponseExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {isAiResponseExpanded && (
                <div 
                  className="p-4 bg-surface-primary max-h-[350px] overflow-y-auto markdown-body border-t border-border-default"
                  dangerouslySetInnerHTML={{ 
                    __html: renderMarkdown(selectedFeedback.original_response) 
                  }}
                />
              )}
            </div>

            {selectedFeedback.has_golden_example && selectedFeedback.golden_response && (selectedFeedback.status === 'ai_approved' || selectedFeedback.status === 'auto_approved' || selectedFeedback.status === 'reviewed') && (
              <div className="border border-info-border rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setIsGoldenResponseExpanded(!isGoldenResponseExpanded)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-accent-subtle hover:bg-surface-hover transition-colors text-left cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-text-primary">Golden Response</span>
                    {!isEditing && canEditGoldenExamples && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartEdit();
                        }}
                        className="text-xs text-text-secondary hover:text-text-primary hover:bg-surface-hover px-2 py-0.5 rounded transition-colors cursor-pointer"
                      >
                        Edit
                      </button>
                    )}
                  </div>
                  <svg
                    className={`w-5 h-5 text-text-secondary transition-transform ${isGoldenResponseExpanded ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {isGoldenResponseExpanded && (
                  <div className="border-t border-info-border">
                    {isEditing ? (
                      <div className="p-4">
                        <div className="flex justify-end mb-2">
                          <button
                            type="button"
                            onClick={() => handleGenerateResponse(true)}
                            disabled={isGenerating || isSubmitting}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-accent-purple text-white rounded-lg hover:bg-accent-purple-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                          >
                            {isGenerating ? (
                              <>
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                Generating...
                              </>
                            ) : (
                              <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                                {hasGenerated ? 'Regenerate' : 'Generate with AI'}
                              </>
                            )}
                          </button>
                        </div>
                        
                        <div className="border border-border-strong rounded-lg overflow-hidden">
                          <div className="flex border-b border-border-strong bg-surface-secondary">
                            <button
                              type="button"
                              onClick={() => setEditGoldenResponseTab('edit')}
                              className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer ${
                                editGoldenResponseTab === 'edit'
                                  ? 'bg-surface-primary text-text-primary border-b-2 border-accent-purple -mb-px'
                                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-tertiary'
                              }`}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditGoldenResponseTab('preview')}
                              className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer ${
                                editGoldenResponseTab === 'preview'
                                  ? 'bg-surface-primary text-text-primary border-b-2 border-accent-purple -mb-px'
                                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-tertiary'
                              }`}
                            >
                              Preview
                            </button>
                          </div>
                          
                          {editGoldenResponseTab === 'edit' ? (
                            <textarea
                              value={editedGoldenResponse}
                              onChange={(e) => setEditedGoldenResponse(e.target.value)}
                              className="w-full px-3 py-2 border-0 focus:outline-none focus:ring-0 text-sm resize-none bg-surface-primary text-text-primary"
                              rows={10}
                              placeholder="Edit the golden response..."
                              disabled={isGenerating}
                            />
                          ) : (
                            <div 
                              className="p-4 bg-surface-primary min-h-[200px] max-h-[350px] overflow-y-auto markdown-body"
                              dangerouslySetInnerHTML={{ 
                                __html: editedGoldenResponse.trim() 
                                  ? renderMarkdown(editedGoldenResponse) 
                                  : '<p class="text-text-tertiary italic">No content to preview</p>'
                              }}
                            />
                          )}
                        </div>
                        
                        {generationInfo && (
                          <p className="text-xs text-accent-blue mt-1.5">
                            Generated in {(generationInfo.timeMs / 1000).toFixed(1)}s
                            {generationInfo.toolCalls > 0 && ` (${generationInfo.toolCalls} tool call${generationInfo.toolCalls > 1 ? 's' : ''} made)`}
                          </p>
                        )}
                        
                        <div className="mt-3">
                          <label className="block text-xs font-medium text-text-secondary mb-1.5">Query Type</label>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => setQueryType('static')}
                              className={`px-3 py-1.5 text-xs rounded-lg border transition-colors cursor-pointer ${
                                queryType === 'static'
                                  ? 'border-accent-blue bg-info-subtle text-info-text font-medium'
                                  : 'border-border-default bg-surface-primary text-text-secondary hover:bg-surface-secondary'
                              }`}
                            >
                              Static
                            </button>
                            <button
                              type="button"
                              onClick={() => setQueryType('temporal')}
                              className={`px-3 py-1.5 text-xs rounded-lg border transition-colors cursor-pointer ${
                                queryType === 'temporal'
                                  ? 'border-warning bg-warning-subtle text-warning-text font-medium'
                                  : 'border-border-default bg-surface-primary text-text-secondary hover:bg-surface-secondary'
                              }`}
                            >
                              Temporal
                            </button>
                            <span className="text-xs text-text-tertiary self-center ml-1">
                              {queryType === 'temporal' ? 'AI use as a reference' : 'Can be used as direct answer'}
                            </span>
                          </div>
                        </div>

                        <div className="flex justify-end gap-2 mt-3">
                          <button
                            type="button"
                            onClick={handleCancelEdit}
                            disabled={isSubmitting || isGenerating}
                            className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-tertiary rounded-lg transition-colors cursor-pointer"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={handleSaveEdit}
                            disabled={isSubmitting || isGenerating || !editedGoldenResponse.trim()}
                            className="px-3 py-1.5 text-sm bg-accent-purple text-white rounded-lg hover:bg-accent-purple-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                          >
                            {isSubmitting ? 'Saving...' : 'Save Changes'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div 
                        className="p-4 bg-surface-primary max-h-[350px] overflow-y-auto markdown-body"
                        dangerouslySetInnerHTML={{ 
                          __html: renderMarkdown(selectedFeedback.golden_response) 
                        }}
                      />
                    )}
                  </div>
                )}
              </div>
            )}

            {(selectedFeedback.status === 'pending' || selectedFeedback.status === 'ai_rejected') && selectedFeedback.feedback_type === 'negative' && (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-sm font-medium text-text-secondary">
                    Golden Response
                    <span className="font-normal text-text-secondary ml-1">(Write the ideal response)</span>
                  </label>
                  {canManageFeedback && (
                    <button
                      type="button"
                      onClick={() => handleGenerateResponse(false)}
                      disabled={isGenerating || isSubmitting}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-accent-purple text-white rounded-lg hover:bg-accent-purple-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    >
                      {isGenerating ? (
                        <>
                          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          Generating...
                        </>
                      ) : (
                        <>
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          {hasGenerated ? 'Regenerate' : 'Generate with AI'}
                        </>
                      )}
                    </button>
                  )}
                </div>
                
                <div className="border border-border-strong rounded-lg overflow-hidden">
                  <div className="flex border-b border-border-strong bg-surface-secondary">
                    <button
                      type="button"
                      onClick={() => setGoldenResponseTab('edit')}
                      className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer ${
                        goldenResponseTab === 'edit'
                          ? 'bg-surface-primary text-text-primary border-b-2 border-accent-purple -mb-px'
                          : 'text-text-secondary hover:text-text-primary hover:bg-surface-tertiary'
                      }`}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setGoldenResponseTab('preview')}
                      className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer ${
                        goldenResponseTab === 'preview'
                          ? 'bg-surface-primary text-text-primary border-b-2 border-accent-purple -mb-px'
                          : 'text-text-secondary hover:text-text-primary hover:bg-surface-tertiary'
                      }`}
                    >
                      Preview
                    </button>
                  </div>
                  
                  {goldenResponseTab === 'edit' ? (
                    <textarea
                      value={goldenResponse}
                      onChange={(e) => setGoldenResponse(e.target.value)}
                      className="w-full px-3 py-2 border-0 focus:outline-none focus:ring-0 text-sm resize-none bg-surface-primary text-text-primary"
                      rows={10}
                      placeholder="Write the ideal response that the AI should have given, or click 'Generate with AI' to auto-generate..."
                      disabled={isGenerating}
                    />
                  ) : (
                    <div 
                      className="p-4 bg-surface-primary min-h-[200px] max-h-[350px] overflow-y-auto markdown-body"
                      dangerouslySetInnerHTML={{ 
                        __html: goldenResponse.trim() 
                          ? renderMarkdown(goldenResponse) 
                          : '<p class="text-text-tertiary italic">No content to preview</p>'
                      }}
                    />
                  )}
                </div>
                
                {generationInfo && (
                  <p className="text-xs text-accent-blue mt-1.5">
                    Generated in {(generationInfo.timeMs / 1000).toFixed(1)}s
                    {generationInfo.toolCalls > 0 && ` (${generationInfo.toolCalls} tool call${generationInfo.toolCalls > 1 ? 's' : ''} made)`}
                  </p>
                )}
                <p className="text-xs text-text-secondary mt-1.5">
                  This response will be used as a golden example to improve future AI responses.
                </p>
              </div>
            )}

            {(selectedFeedback.status === 'pending' || selectedFeedback.status === 'ai_rejected') && selectedFeedback.feedback_type === 'positive' && (
              <div className="p-3 bg-success-subtle rounded-lg text-sm text-success-text border border-success">
                Approving this will create a golden example using the original AI response shown above.
              </div>
            )}

            {(selectedFeedback.status === 'pending' || selectedFeedback.status === 'ai_rejected') && canManageFeedback && (
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">
                  Query Type
                  <span className="font-normal text-text-secondary ml-1">(How should this golden example be used?)</span>
                </label>
                <div className="flex gap-3">
                  <label
                    className={`flex-1 flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      queryType === 'static'
                        ? 'border-accent-blue bg-info-subtle'
                        : 'border-border-default bg-surface-primary hover:bg-surface-secondary'
                    }`}
                  >
                    <input
                      type="radio"
                      name="queryType"
                      value="static"
                      checked={queryType === 'static'}
                      onChange={() => setQueryType('static')}
                      className="mt-0.5"
                    />
                    <div>
                      <p className="text-sm font-medium text-text-primary">Static</p>
                      <p className="text-xs text-text-secondary mt-0.5">Answer doesn't change over time. Can be used as a direct answer for similar queries.</p>
                    </div>
                  </label>
                  <label
                    className={`flex-1 flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      queryType === 'temporal'
                        ? 'border-warning bg-warning-subtle'
                        : 'border-border-default bg-surface-primary hover:bg-surface-secondary'
                    }`}
                  >
                    <input
                      type="radio"
                      name="queryType"
                      value="temporal"
                      checked={queryType === 'temporal'}
                      onChange={() => setQueryType('temporal')}
                      className="mt-0.5"
                    />
                    <div>
                      <p className="text-sm font-medium text-text-primary">Temporal</p>
                      <p className="text-xs text-text-secondary mt-0.5">Answer depends on current data (recent incidents, counts, trends). Used as reference</p>
                    </div>
                  </label>
                </div>
              </div>
            )}

            <div className="pt-3 border-t border-border-default text-xs text-text-secondary space-y-0.5">
              <p><span className="text-text-secondary">User:</span> {selectedFeedback.user_email || 'Anonymous'}</p>
              <p><span className="text-text-secondary">Submitted:</span> {new Date(selectedFeedback.created_at).toLocaleString()}</p>
              {selectedFeedback.reviewed_at && (
                <p><span className="text-text-secondary">Reviewed:</span> {new Date(selectedFeedback.reviewed_at).toLocaleString()} by {selectedFeedback.reviewer_email}</p>
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
