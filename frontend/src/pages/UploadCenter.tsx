import React, { useState, useEffect } from 'react';
import { 
  Upload as UploadIcon, 
  FileText, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  RefreshCw, 
  ShieldAlert, 
  Layers,
  ArrowRight,
  XCircle,
  FileSpreadsheet
} from 'lucide-react';
import { api, Source, Upload, UploadRowError, User } from '../api/client';

interface UploadCenterProps {
  currentUser: User;
  onNavigateToMapping: (sourceId: string, uploadId?: string) => void;
}

export const UploadCenter: React.FC<UploadCenterProps> = ({ currentUser, onNavigateToMapping }) => {
  const [sources, setSources] = useState<Source[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingSample, setIsLoadingSample] = useState(false);

  // Errors modal state
  const [selectedUploadForErrors, setSelectedUploadForErrors] = useState<Upload | null>(null);
  const [rowErrors, setRowErrors] = useState<UploadRowError[]>([]);
  const [isLoadingErrors, setIsLoadingErrors] = useState(false);

  const isCoFounder = currentUser.role === 'cofounder';

  const selectedSource = sources.find((s) => s.id === selectedSourceId);

  const getSampleFileNameForSource = (src?: Source | null): string => {
    if (!src) return '01_shopify_orders.csv';
    if (src.partner_id === 'shopify' && src.source_type === 'orders') return '01_shopify_orders.csv';
    if (src.partner_id === 'amazon' && src.source_type === 'settlement') return '02_amazon_settlement.csv';
    if (src.partner_id === 'delhivery' && src.source_type === 'cod') return '03_delhivery_cod_remittance.csv';
    if (src.partner_id === 'bluedart' && src.source_type === 'freight') return '04_bluedart_freight_invoice.csv';
    if (src.partner_id === 'blr_warehouse' && src.source_type === 'receipts') return '05_blr_warehouse_receipts.csv';
    if (src.source_type === 'orders') return '01_shopify_orders.csv';
    if (src.source_type === 'settlement') return '02_amazon_settlement.csv';
    if (src.source_type === 'cod') return '03_delhivery_cod_remittance.csv';
    if (src.source_type === 'freight') return '04_bluedart_freight_invoice.csv';
    return '05_blr_warehouse_receipts.csv';
  };

  const handleAutoLoadSample = async () => {
    const sampleName = getSampleFileNameForSource(selectedSource);
    setIsLoadingSample(true);
    setUploadError(null);
    try {
      const file = await api.fetchSampleFile(sampleName);
      setSelectedFile(file);
      setUploadSuccess(`Loaded sample file '${sampleName}' (${(file.size / 1024).toFixed(1)} KB). Click 'Upload Statement' below to proceed.`);
    } catch (err: any) {
      setUploadError(`Failed to load sample: ${err.message}`);
    } finally {
      setIsLoadingSample(false);
    }
  };

  useEffect(() => {
    loadSources();
    loadUploads();
  }, []);

  const loadSources = async () => {
    try {
      const data = await api.listSources();
      setSources(data);
      if (data.length > 0 && !selectedSourceId) {
        setSelectedSourceId(data[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load sources:', err);
    }
  };

  const loadUploads = async () => {
    setIsLoadingHistory(true);
    try {
      const data = await api.listUploads();
      setUploads(data);
    } catch (err: any) {
      console.error('Failed to load uploads:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setUploadError(null);
      setUploadSuccess(null);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isCoFounder) {
      setUploadError('Co-founders have read-only access. Uploads require Finance Executive credentials.');
      return;
    }
    if (!selectedFile || !selectedSourceId) {
      setUploadError('Please select a data source and a file to upload.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('source_id', selectedSourceId);

    try {
      const res = await api.uploadFile(formData);
      if (res.type === 'preview') {
        setUploadSuccess(`File '${res.file_name}' staged successfully (${res.total_rows.toLocaleString()} rows). Pending column mapping approval.`);
        // Immediately navigate or allow user to review mapping
        onNavigateToMapping(selectedSourceId, res.upload_id);
      } else {
        setUploadSuccess(`File ingested successfully (${res.upload.row_count.toLocaleString()} rows processed).`);
      }
      setSelectedFile(null);
      loadUploads();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload and parse file');
    } finally {
      setIsUploading(false);
    }
  };

  const openErrorModal = async (upload: Upload) => {
    setSelectedUploadForErrors(upload);
    setIsLoadingErrors(true);
    try {
      const errors = await api.getUploadErrors(upload.id);
      setRowErrors(errors);
    } catch (err: any) {
      console.error('Failed to load errors:', err);
    } finally {
      setIsLoadingErrors(false);
    }
  };

  const closeErrorModal = () => {
    setSelectedUploadForErrors(null);
    setRowErrors([]);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5" /> Ingested
          </span>
        );
      case 'uploaded':
      case 'staged':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800 border border-sky-300">
            <Clock className="w-3.5 h-3.5" /> Staged
          </span>
        );
      case 'mapping_pending':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <Clock className="w-3.5 h-3.5" /> Mapping Pending
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Processing
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <XCircle className="w-3.5 h-3.5" /> Failed
          </span>
        );
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Banner / Description */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <UploadIcon className="w-7 h-7 text-indigo-600" />
            Upload Center
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Ingest orders, marketplace settlements, carrier COD, freight invoices, and warehouse receipts.
          </p>
        </div>
        <div className="mt-3 md:mt-0 flex items-center gap-2">
          <span className="text-xs px-3 py-1.5 rounded-md font-medium bg-slate-100 text-slate-700 border border-slate-300">
            DPDP Compliant (PII Auto-Stripped)
          </span>
          <span className={`text-xs px-3 py-1.5 rounded-md font-medium ${
            isCoFounder ? 'bg-amber-100 text-amber-800 border border-amber-300' : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
          }`}>
            {isCoFounder ? 'Role: Co-Founder (Read-Only)' : 'Role: Finance Executive'}
          </span>
        </div>
      </div>

      {/* Role Alert for Co-Founder */}
      {isCoFounder && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-700 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-amber-800">
            <p className="font-semibold">Co-founder Read-Only Access Active</p>
            <p className="mt-0.5 text-amber-700">
              You have full audit permissions to inspect uploads, review quarantined rows, and approve/rollback column mappings.
              File ingestion requires a Finance Executive session.
            </p>
          </div>
        </div>
      )}

      {/* Upload Box */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-indigo-600" />
          Upload New Statement or Telemetry File
        </h2>

        {uploadError && (
          <div className="mb-4 bg-rose-50 border border-rose-300 rounded-lg p-4 text-sm text-rose-800 flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <div>
              <p className="font-medium">Upload Failed</p>
              <p className="mt-0.5">{uploadError}</p>
            </div>
          </div>
        )}

        {uploadSuccess && (
          <div className="mb-4 bg-emerald-50 border border-emerald-300 rounded-lg p-4 text-sm text-emerald-800 flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <div>
              <p className="font-medium">Success</p>
              <p className="mt-0.5">{uploadSuccess}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleUploadSubmit} className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Source Selector */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-sm font-semibold text-slate-700">
                  Data Source & Type <span className="text-rose-500">*</span>
                </label>
                {selectedSourceId && (
                  <button
                    type="button"
                    onClick={() => onNavigateToMapping(selectedSourceId)}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1 hover:underline"
                  >
                    Configure / Review Mapping →
                  </button>
                )}
              </div>
              <select
                value={selectedSourceId}
                onChange={(e) => {
                  setSelectedSourceId(e.target.value);
                  setSelectedFile(null);
                  setUploadSuccess(null);
                  setUploadError(null);
                }}
                disabled={isCoFounder || isUploading}
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100 disabled:text-slate-500"
              >
                {sources.map((src) => (
                  <option key={src.id} value={src.id}>
                    {src.name} ({src.partner_id.toUpperCase()} • {src.source_type.toUpperCase()})
                  </option>
                ))}
              </select>
              <p className="text-xs text-slate-500 mt-1">
                Select the marketplace, carrier, or warehouse corresponding to this report.
              </p>
            </div>

            {/* File Dropzone */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-sm font-semibold text-slate-700">
                  Statement File (.csv, .xlsx) <span className="text-rose-500">*</span>
                </label>
                <button
                  type="button"
                  onClick={handleAutoLoadSample}
                  disabled={isCoFounder || isUploading || isLoadingSample}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1 bg-indigo-50 px-2.5 py-1 rounded border border-indigo-200 hover:bg-indigo-100 transition-colors"
                >
                  {isLoadingSample ? (
                    <RefreshCw className="w-3 h-3 animate-spin" />
                  ) : (
                    <span>⚡ Auto-fill Sample ({getSampleFileNameForSource(selectedSource)})</span>
                  )}
                </button>
              </div>

              <div className={`relative border-2 border-dashed rounded-lg p-5 text-center transition-colors ${
                selectedFile 
                  ? 'border-emerald-400 bg-emerald-50/60' 
                  : 'border-slate-300 bg-slate-50 hover:border-indigo-400'
              }`}>
                <input
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={handleFileChange}
                  disabled={isCoFounder || isUploading}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed z-10"
                />
                <div className="flex flex-col items-center justify-center space-y-1.5 pointer-events-none">
                  {selectedFile ? (
                    <>
                      <CheckCircle2 className="w-7 h-7 text-emerald-600" />
                      <p className="text-sm font-bold text-emerald-900">
                        {selectedFile.name}
                      </p>
                      <p className="text-xs text-emerald-700 font-mono">
                        {(selectedFile.size / 1024).toFixed(1)} KB • Attached & Ready to Ingest
                      </p>
                    </>
                  ) : (
                    <>
                      <UploadIcon className="w-7 h-7 text-slate-400" />
                      <p className="text-sm font-semibold text-slate-700">
                        Click to browse file or drag & drop here
                      </p>
                      <p className="text-xs text-slate-500">
                        Max 25 MB • CSV or XLSX • PII auto-stripped
                      </p>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <div className="text-xs text-slate-500">
              {!selectedFile ? (
                <span className="text-amber-700 font-medium flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Please select or auto-fill a file to enable upload.
                </span>
              ) : (
                <span className="text-emerald-700 font-medium flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  File ready for ingestion.
                </span>
              )}
            </div>

            <button
              type="submit"
              disabled={isCoFounder || isUploading || !selectedFile}
              className={`inline-flex items-center gap-2 px-6 py-2.5 rounded-lg font-semibold text-sm shadow-sm transition-all ${
                !selectedFile || isCoFounder || isUploading
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-md cursor-pointer'
              }`}
            >
              {isUploading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Validating & Parsing...
                </>
              ) : (
                <>
                  <UploadIcon className="w-4 h-4" />
                  Upload Statement
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Ingestion History Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-slate-600" />
            <h3 className="font-semibold text-slate-900">Ingestion Audit History</h3>
            <span className="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full font-mono">
              {uploads.length} files
            </span>
          </div>
          <button
            onClick={loadUploads}
            disabled={isLoadingHistory}
            className="inline-flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingHistory ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 text-slate-600 uppercase text-xs border-b border-slate-200 font-semibold">
              <tr>
                <th className="px-5 py-3.5">File Name & Hash</th>
                <th className="px-5 py-3.5">Partner</th>
                <th className="px-5 py-3.5">Source Type</th>
                <th className="px-5 py-3.5">Rows</th>
                <th className="px-5 py-3.5">Status</th>
                <th className="px-5 py-3.5">Quarantined</th>
                <th className="px-5 py-3.5">Uploaded At</th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {uploads.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-8 text-center text-slate-500">
                    No uploads recorded yet. Upload your first statement above.
                  </td>
                </tr>
              ) : (
                uploads.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-5 py-3.5 font-medium text-slate-900">
                      <div>{u.file_name}</div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        SHA: {u.file_hash.substring(0, 12)}...
                      </div>
                    </td>
                    <td className="px-5 py-3.5 uppercase font-semibold text-slate-700">
                      {u.partner_id}
                    </td>
                    <td className="px-5 py-3.5 capitalize">
                      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-800">
                        {u.source_type}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-700">
                      {u.row_count.toLocaleString()}
                    </td>
                    <td className="px-5 py-3.5">
                      {getStatusBadge(u.processing_status)}
                    </td>
                    <td className="px-5 py-3.5">
                      {u.error_count > 0 ? (
                        <button
                          onClick={() => openErrorModal(u)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-800 underline decoration-rose-300"
                        >
                          <AlertTriangle className="w-3.5 h-3.5" />
                          {u.error_count} quarantined
                        </button>
                      ) : (
                        <span className="text-slate-400 text-xs">0 errors</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-500">
                      {new Date(u.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-3.5 text-right space-x-2">
                      {u.processing_status === 'mapping_pending' && (
                        <button
                          onClick={() => onNavigateToMapping(u.source_id, u.id)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2.5 py-1.5 rounded border border-indigo-200"
                        >
                          <Layers className="w-3.5 h-3.5" />
                          Review Mapping
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      )}
                      {u.error_count > 0 && (
                        <button
                          onClick={() => openErrorModal(u)}
                          className="text-xs text-slate-600 hover:text-slate-900 underline"
                        >
                          Audit Logs
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quarantined Errors Modal */}
      {selectedUploadForErrors && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col overflow-hidden border border-slate-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-rose-600" />
                <h3 className="font-bold text-slate-900">
                  Quarantined Rows Audit: {selectedUploadForErrors.file_name}
                </h3>
              </div>
              <button
                onClick={closeErrorModal}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1">
              <div className="mb-4 bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs text-slate-700 grid grid-cols-3 gap-2">
                <div>
                  <span className="font-semibold text-slate-900">Total Rows:</span> {selectedUploadForErrors.row_count}
                </div>
                <div>
                  <span className="font-semibold text-slate-900">Quarantined Count:</span> {selectedUploadForErrors.error_count}
                </div>
                <div>
                  <span className="font-semibold text-slate-900">Upload ID:</span> {selectedUploadForErrors.id.substring(0, 8)}...
                </div>
              </div>

              {isLoadingErrors ? (
                <div className="text-center py-8 text-slate-500 flex justify-center items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-indigo-600" />
                  Loading quarantined row telemetry...
                </div>
              ) : rowErrors.length === 0 ? (
                <p className="text-sm text-slate-500 py-4 text-center">No quarantined rows recorded.</p>
              ) : (
                <div className="space-y-3">
                  {rowErrors.map((err) => (
                    <div key={err.id} className="border border-rose-200 rounded-lg p-3.5 bg-rose-50/50">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-bold text-rose-900">
                          Row #{err.source_row_number}
                        </span>
                        <span className="font-mono px-2 py-0.5 rounded bg-rose-200 text-rose-900 font-semibold">
                          {err.error_code}
                        </span>
                      </div>
                      <p className="text-xs text-rose-800 mb-2 font-medium">
                        {err.error_message}
                      </p>
                      <details className="text-[11px] bg-white p-2 rounded border border-rose-200">
                        <summary className="cursor-pointer text-slate-600 font-mono hover:text-slate-900">
                          View Quarantined Row Payload
                        </summary>
                        <pre className="mt-1 overflow-x-auto text-slate-800">
                          {JSON.stringify(err.raw_record, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={closeErrorModal}
                className="px-4 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-900 transition-colors"
              >
                Close Audit Log
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
