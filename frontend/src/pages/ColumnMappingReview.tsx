import React, { useState, useEffect } from 'react';
import { 
  Layers, 
  CheckCircle2, 
  RotateCcw, 
  AlertCircle, 
  History, 
  ShieldCheck, 
  Sparkles,
  ArrowLeft,
  RefreshCw,
  Play
} from 'lucide-react';
import { api, Source, ColumnMapping, User } from '../api/client';

interface ColumnMappingReviewProps {
  currentUser: User;
  sourceId: string;
  uploadId?: string;
  onBackToUploads: () => void;
}

export const ColumnMappingReview: React.FC<ColumnMappingReviewProps> = ({
  currentUser,
  sourceId,
  uploadId,
  onBackToUploads,
}) => {
  const [source, setSource] = useState<Source | null>(null);
  const [activeMapping, setActiveMapping] = useState<ColumnMapping | null>(null);
  const [versions, setVersions] = useState<ColumnMapping[]>([]);
  const [mappingState, setMappingState] = useState<Record<string, string>>({});
  const [confidenceState, setConfidenceState] = useState<Record<string, { confidence: number; match_type: string }>>({});
  const [sourceColumns, setSourceColumns] = useState<string[]>([]);
  const [canonicalFields, setCanonicalFields] = useState<any[]>([]);
  const [missingRequired, setMissingRequired] = useState<string[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isProcessingUpload, setIsProcessingUpload] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadData();
  }, [sourceId]);

  const loadData = async () => {
    setIsLoading(true);
    setFeedbackMessage(null);
    try {
      const sources = await api.listSources();
      const currentSrc = sources.find((s) => s.id === sourceId) || null;
      setSource(currentSrc);

      // Load active mapping & versions
      let currentActive: ColumnMapping | null = null;
      try {
        currentActive = await api.getActiveMapping(sourceId);
        setActiveMapping(currentActive);
      } catch {
        setActiveMapping(null);
      }

      try {
        const vers = await api.getMappingVersions(sourceId);
        setVersions(vers);
      } catch {
        setVersions([]);
      }

      // If uploadId is provided, get upload details
      if (uploadId) {
        await api.getUpload(uploadId);
      }

      // Request suggestions with sample columns or active mapping
      const initialColumns = currentActive
        ? Object.values(currentActive.mapping_json)
        : ['order_id', 'order_value', 'order_date', 'payment_mode', 'tracking_number', 'status'];

      setSourceColumns(initialColumns);

      const suggestRes = await api.suggestMapping(sourceId, initialColumns);
      setCanonicalFields(suggestRes.canonical_fields || []);
      setMissingRequired(suggestRes.missing_required || []);

      const newMapping: Record<string, string> = {};
      const newConfidence: Record<string, any> = {};

      // If active mapping exists, populate with active mapping
      if (currentActive && currentActive.mapping_json) {
        Object.entries(currentActive.mapping_json).forEach(([k, col]) => {
          newMapping[k] = col;
          newConfidence[k] = { confidence: 1.0, match_type: 'APPROVED_VERSION' };
        });
      } else {
        // Use AI suggestions
        Object.entries(suggestRes.suggestions).forEach(([k, val]: [string, any]) => {
          if (val.column) {
            newMapping[k] = val.column;
            newConfidence[k] = { confidence: val.confidence, match_type: val.match_type };
          }
        });
      }

      setMappingState(newMapping);
      setConfidenceState(newConfidence);
    } catch (err: any) {
      console.error('Failed to load mapping data:', err);
      setFeedbackMessage({ type: 'error', text: err.message || 'Failed to load column mapping data.' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleColumnSelect = (fieldKey: string, columnValue: string) => {
    const updated = { ...mappingState };
    if (!columnValue) {
      delete updated[fieldKey];
    } else {
      updated[fieldKey] = columnValue;
    }
    setMappingState(updated);

    // Update match type to manual
    setConfidenceState({
      ...confidenceState,
      [fieldKey]: { confidence: 1.0, match_type: 'MANUAL' },
    });

    // Check missing required
    if (source) {
      const requiredForSource = canonicalFields
        .filter((f) => f.required_for?.includes(source.source_type))
        .map((f) => f.key);
      const missing = requiredForSource.filter((k) => !updated[k]);
      setMissingRequired(missing);
    }
  };

  const handleApproveMapping = async () => {
    setIsSaving(true);
    setFeedbackMessage(null);
    try {
      const approved = await api.approveMapping(sourceId, mappingState);
      setActiveMapping(approved);
      setFeedbackMessage({
        type: 'success',
        text: `Mapping v${approved.version} successfully approved by ${currentUser.role === 'cofounder' ? 'Co-founder' : 'Finance Executive'}!`,
      });

      // Reload versions
      const vers = await api.getMappingVersions(sourceId);
      setVersions(vers);
    } catch (err: any) {
      setFeedbackMessage({ type: 'error', text: err.message || 'Approval failed' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRollback = async (mappingId: string) => {
    if (!window.confirm('Are you sure you want to rollback to this historical mapping configuration?')) {
      return;
    }
    setIsSaving(true);
    setFeedbackMessage(null);
    try {
      const restored = await api.rollbackMapping(mappingId);
      setActiveMapping(restored);
      setMappingState(restored.mapping_json);
      setFeedbackMessage({
        type: 'success',
        text: `Successfully rolled back! Activated new version v${restored.version} matching historical configuration.`,
      });
      const vers = await api.getMappingVersions(sourceId);
      setVersions(vers);
    } catch (err: any) {
      setFeedbackMessage({ type: 'error', text: err.message || 'Rollback failed' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleProcessStagedUpload = async () => {
    if (!uploadId) return;
    setIsProcessingUpload(true);
    setFeedbackMessage(null);
    try {
      const res = await api.processPendingUpload(uploadId);
      setFeedbackMessage({
        type: 'success',
        text: `Upload ${res.upload.file_name} processed successfully (${res.summary.processed_rows} rows ingested)!`,
      });
    } catch (err: any) {
      setFeedbackMessage({ type: 'error', text: err.message || 'Processing staged upload failed' });
    } finally {
      setIsProcessingUpload(false);
    }
  };

  const renderBadge = (fieldKey: string) => {
    const conf = confidenceState[fieldKey];
    if (!conf || !mappingState[fieldKey]) {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-500 border border-slate-200">
          Unmapped
        </span>
      );
    }

    if (conf.match_type === 'EXACT') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
          <Sparkles className="w-3 h-3 text-emerald-600" /> Exact Match (100%)
        </span>
      );
    }
    if (conf.match_type === 'FUZZY') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-100 text-blue-800 border border-blue-300">
          <Sparkles className="w-3 h-3 text-blue-600" /> Fuzzy ({Math.round(conf.confidence * 100)}%)
        </span>
      );
    }
    if (conf.match_type === 'MANUAL') {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-100 text-purple-800 border border-purple-300">
          Manual Override
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
        Approved v{activeMapping?.version}
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-3">
        <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
        <p className="text-slate-600 font-medium">Loading mapping configuration...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Top Navigation & Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-200 gap-4">
        <div>
          <button
            onClick={onBackToUploads}
            className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-semibold mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Upload Center
          </button>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-7 h-7 text-indigo-600" />
            Column Mapping Review: {source?.name || 'Feed'}
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Map partner-specific column headers to LeakCheck canonical fields with exact & fuzzy auto-matching.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {uploadId && (
            <button
              onClick={handleProcessStagedUpload}
              disabled={isProcessingUpload || missingRequired.length > 0}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 disabled:opacity-50 transition-all shadow-sm"
            >
              <Play className="w-3.5 h-3.5" />
              {isProcessingUpload ? 'Ingesting...' : 'Ingest Staged File'}
            </button>
          )}

          <button
            onClick={handleApproveMapping}
            disabled={isSaving || missingRequired.length > 0}
            className="inline-flex items-center gap-1.5 px-5 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-sm"
          >
            <CheckCircle2 className="w-4 h-4" />
            {isSaving ? 'Activating...' : `Approve & Activate (v${(activeMapping?.version || 0) + 1})`}
          </button>
        </div>
      </div>

      {/* Feedback Alert */}
      {feedbackMessage && (
        <div
          className={`p-4 rounded-lg text-sm border flex items-start gap-2 ${
            feedbackMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
              : 'bg-rose-50 border-rose-300 text-rose-800'
          }`}
        >
          {feedbackMessage.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          )}
          <div>{feedbackMessage.text}</div>
        </div>
      )}

      {/* Missing Required Fields Alert */}
      {missingRequired.length > 0 && (
        <div className="p-4 bg-amber-50 border border-amber-300 rounded-lg text-sm text-amber-800 flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <div>
            <p className="font-semibold">Mandatory Fields Incomplete for {source?.source_type.toUpperCase()}:</p>
            <p className="mt-0.5">
              Please map: <span className="font-mono font-bold">{missingRequired.join(', ')}</span> before approval.
            </p>
          </div>
        </div>
      )}

      {/* Main Grid: Mapping Editor & Version History */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Mapping Controls (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
            <div>
              <h2 className="font-bold text-slate-900">Canonical Field Configuration</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Active Mapping:{' '}
                {activeMapping ? (
                  <span className="font-semibold text-indigo-600">Version {activeMapping.version}</span>
                ) : (
                  <span className="text-amber-600 font-semibold">None (Draft)</span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Immutable upon approval
            </div>
          </div>

          <div className="divide-y divide-slate-100">
            {canonicalFields.map((field) => {
              const isRequired = field.required_for?.includes(source?.source_type);
              const selectedCol = mappingState[field.key] || '';

              return (
                <div key={field.key} className="p-4 hover:bg-slate-50/50 flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-900">{field.display_name}</span>
                      {isRequired ? (
                        <span className="text-[10px] uppercase font-extrabold px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">
                          Required
                        </span>
                      ) : (
                        <span className="text-[10px] uppercase font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                          Optional
                        </span>
                      )}
                      {renderBadge(field.key)}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{field.description}</p>
                    <span className="text-[11px] font-mono text-slate-400">key: {field.key}</span>
                  </div>

                  <div className="w-full md:w-64">
                    <select
                      value={selectedCol}
                      onChange={(e) => handleColumnSelect(field.key, e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                    >
                      <option value="">-- Unmapped --</option>
                      {sourceColumns.map((col) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Version History & Rollback (1 Col) */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 flex flex-col">
          <div className="flex items-center gap-2 pb-4 border-b border-slate-200">
            <History className="w-5 h-5 text-indigo-600" />
            <h2 className="font-bold text-slate-900">Version History & Rollback</h2>
          </div>

          <p className="text-xs text-slate-600 mt-3 mb-4">
            All mapping approvals are immutable audit records. Both Finance Executives and Co-founders can restore prior versions.
          </p>

          <div className="space-y-3 flex-1 overflow-y-auto max-h-[500px]">
            {versions.length === 0 ? (
              <p className="text-xs text-slate-400 py-6 text-center">No prior approved versions.</p>
            ) : (
              versions.map((ver) => {
                const isActive = activeMapping?.id === ver.id;
                return (
                  <div
                    key={ver.id}
                    className={`p-3.5 rounded-lg border text-xs transition-all ${
                      isActive
                        ? 'border-indigo-300 bg-indigo-50/50'
                        : 'border-slate-200 bg-slate-50 hover:bg-slate-100/60'
                    }`}
                  >
                    <div className="flex items-center justify-between font-bold mb-1">
                      <span className="text-slate-900">Version {ver.version}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold ${
                          isActive
                            ? 'bg-emerald-100 text-emerald-800'
                            : ver.status === 'rolled_back'
                            ? 'bg-purple-100 text-purple-800'
                            : 'bg-slate-200 text-slate-700'
                        }`}
                      >
                        {isActive ? 'Active' : ver.status}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-500 mb-2">
                      Approved: {ver.approved_at ? new Date(ver.approved_at).toLocaleString() : 'Draft'}
                    </div>

                    <details className="text-[11px] bg-white p-2 rounded border border-slate-200 mb-2.5">
                      <summary className="cursor-pointer text-slate-600 font-medium">View Field Mapping</summary>
                      <pre className="mt-1 font-mono text-[10px] text-slate-700 overflow-x-auto">
                        {JSON.stringify(ver.mapping_json, null, 2)}
                      </pre>
                    </details>

                    {!isActive && (
                      <button
                        onClick={() => handleRollback(ver.id)}
                        disabled={isSaving}
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-purple-700 hover:text-purple-900 bg-purple-50 px-2.5 py-1 rounded border border-purple-200 transition-colors"
                      >
                        <RotateCcw className="w-3 h-3" />
                        Rollback to v{ver.version}
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
