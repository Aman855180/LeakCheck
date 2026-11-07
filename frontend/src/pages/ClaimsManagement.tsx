import React, { useState, useEffect, useCallback } from 'react';
import { 
  FileCheck2, 
  Download, 
  Search, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  RefreshCw, 
  ChevronLeft, 
  ChevronRight, 
  ChevronUp, 
  ChevronDown, 
  X, 
  ArrowRight, 
  DollarSign,
  Edit3,
  FileSpreadsheet
} from 'lucide-react';
import { api, Claim, ClaimDetail, ClaimsSummary, User } from '../api/client';

interface ClaimsManagementProps {
  currentUser: User;
  initialStatusFilter?: string;
  initialPartnerFilter?: string;
}

export const ClaimsManagement: React.FC<ClaimsManagementProps> = ({
  currentUser,
  initialStatusFilter,
  initialPartnerFilter,
}) => {
  // Data States
  const [claims, setClaims] = useState<Claim[]>([]);
  const [summary, setSummary] = useState<ClaimsSummary | null>(null);
  const [totalClaimsCount, setTotalClaimsCount] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);

  // Filter States
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedPartner, setSelectedPartner] = useState<string>(initialPartnerFilter || 'ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>(initialStatusFilter || 'ALL');
  const [selectedReason, setSelectedReason] = useState<string>('ALL');
  const [minAmount, setMinAmount] = useState<string>('');
  const [maxAmount, setMaxAmount] = useState<string>('');

  // Sorting & Pagination
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);

  // Status & Progress States
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [alertMessage, setAlertMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Detail / Edit Modal States
  const [selectedClaimDetail, setSelectedClaimDetail] = useState<ClaimDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [isUpdatingClaim, setIsUpdatingClaim] = useState<boolean>(false);
  const [editStatus, setEditStatus] = useState<string>('draft');
  const [editNotes, setEditNotes] = useState<string>('');
  const [editRecoveredAmount, setEditRecoveredAmount] = useState<string>('0.00');
  const [editRecoveredDate, setEditRecoveredDate] = useState<string>('');

  const isCoFounder = currentUser.role === 'cofounder';

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      // 1. Fetch Claims Summary
      const summaryData = await api.getClaimsSummary();
      setSummary(summaryData);

      // 2. Fetch Paginated Claims
      const params: any = {
        page: currentPage,
        page_size: pageSize,
        sort_by: sortBy,
        sort_dir: sortDir,
        envelope: true,
      };

      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (selectedPartner !== 'ALL') params.partner_id = selectedPartner.toLowerCase();
      if (selectedStatus !== 'ALL') params.claim_status = selectedStatus.toLowerCase();
      if (selectedReason !== 'ALL') params.claim_reason = selectedReason.toLowerCase();
      if (minAmount) params.min_amount = Number(minAmount);
      if (maxAmount) params.max_amount = Number(maxAmount);

      const res = await api.listClaims(params);
      if (res && res.items) {
        setClaims(res.items);
        setTotalClaimsCount(res.total);
        setTotalPages(res.pages);
      } else if (Array.isArray(res)) {
        setClaims(res);
        setTotalClaimsCount(res.length);
        setTotalPages(1);
      }
    } catch (err: any) {
      console.error('Failed to load claims', err);
    } finally {
      setIsLoading(false);
    }
  }, [
    currentPage,
    pageSize,
    sortBy,
    sortDir,
    searchQuery,
    selectedPartner,
    selectedStatus,
    selectedReason,
    minAmount,
    maxAmount
  ]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Generate Draft Claims
  const handleGenerateClaims = async () => {
    if (isCoFounder) {
      setAlertMessage({
        type: 'error',
        text: 'Co-founders have read-only audit permissions. Generating claims requires Finance Executive credentials.'
      });
      return;
    }

    setIsGenerating(true);
    setAlertMessage(null);
    try {
      const res = await api.generateDraftClaims();
      setAlertMessage({
        type: 'success',
        text: `Claims generation completed. Processed ${res.claims_generated_or_updated} draft claims.`
      });
      loadData();
    } catch (err: any) {
      setAlertMessage({
        type: 'error',
        text: err.message || 'Failed to generate claims from reconciliation records.'
      });
    } finally {
      setIsGenerating(false);
    }
  };

  // Open Claim Detail & Edit Modal
  const openClaimModal = async (claimId: string) => {
    setIsLoadingDetail(true);
    try {
      const detail = await api.getClaimDetail(claimId);
      setSelectedClaimDetail(detail);
      setEditStatus(detail.claim_status);
      setEditNotes(detail.notes || '');
      setEditRecoveredAmount(detail.recovered_amount || '0.00');
      setEditRecoveredDate(detail.recovered_at ? detail.recovered_at.split('T')[0] : '');
    } catch (err: any) {
      console.error('Failed to load claim detail', err);
    } finally {
      setIsLoadingDetail(false);
    }
  };

  // Handle Save Claim Updates
  const handleSaveClaim = async () => {
    if (isCoFounder || !selectedClaimDetail) return;

    setIsUpdatingClaim(true);
    try {
      const recAmt = Number(editRecoveredAmount);
      if (isNaN(recAmt) || recAmt < 0) {
        alert('Please enter a valid recovered amount (>= 0)');
        setIsUpdatingClaim(false);
        return;
      }
      if (recAmt > Number(selectedClaimDetail.claim_amount)) {
        alert(`Recovered amount cannot exceed the total claim amount (₹${selectedClaimDetail.claim_amount})`);
        setIsUpdatingClaim(false);
        return;
      }

      const payload: any = {
        claim_status: editStatus,
        notes: editNotes,
        recovered_amount: recAmt,
      };
      if (editRecoveredDate) {
        payload.recovered_at = new Date(editRecoveredDate).toISOString();
      }

      const updated = await api.updateClaim(selectedClaimDetail.id, payload);
      setSelectedClaimDetail({ ...selectedClaimDetail, ...updated });
      setAlertMessage({
        type: 'success',
        text: `Claim for order ${updated.external_order_id} successfully updated.`
      });
      loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to update claim');
    } finally {
      setIsUpdatingClaim(false);
    }
  };

  const handleSort = (columnKey: string) => {
    if (sortBy === columnKey) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(columnKey);
      setSortDir('desc');
    }
    setCurrentPage(1);
  };

  const resetFilters = () => {
    setSearchQuery('');
    setSelectedPartner('ALL');
    setSelectedStatus('ALL');
    setSelectedReason('ALL');
    setMinAmount('');
    setMaxAmount('');
    setSortBy('created_at');
    setSortDir('desc');
    setCurrentPage(1);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'draft':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            <Clock className="w-3.5 h-3.5 text-slate-500" /> Draft
          </span>
        );
      case 'submitted':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> Submitted
          </span>
        );
      case 'in_review':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">
            <Clock className="w-3.5 h-3.5 text-blue-600" /> In Review
          </span>
        );
      case 'approved':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-indigo-600" /> Approved
          </span>
        );
      case 'recovered':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Recovered
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <X className="w-3.5 h-3.5 text-rose-600" /> Rejected
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            {status}
          </span>
        );
    }
  };

  const getReasonLabel = (reason: string) => {
    const map: Record<string, string> = {
      cod_remittance_missing: 'COD Remittance Missing',
      freight_overcharge: 'Freight Overcharged',
      excess_commission: 'Excess Commission',
      settlement_shortfall: 'Settlement Shortfall',
      excess_return_deduction: 'Excess Return Deduction',
      return_receipt_missing: 'Return Receipt Missing',
      missing_rate_card: 'Missing Rate Card',
      overpaid_review: 'Overpaid (Review)'
    };
    return map[reason] || reason;
  };

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-200 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <FileCheck2 className="w-7 h-7 text-indigo-600" />
            Claims Management &amp; Recovery Hub
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Track dispute dockets, manual marketplace submissions, recovery settlements, and evidence packages.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* CSV Export Button */}
          <a
            href="/api/v1/claims/export/csv"
            download
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold border border-slate-300 transition-colors shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-slate-500" />
            Export Evidence CSV
          </a>

          {/* Generate Claims Button */}
          <button
            onClick={handleGenerateClaims}
            disabled={isGenerating || isCoFounder}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold shadow-sm transition-all ${
              isCoFounder
                ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer hover:shadow'
            }`}
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <FileCheck2 className="w-3.5 h-3.5" />
                Sync Draft Claims
              </>
            )}
          </button>
        </div>
      </div>

      {/* Alert Banner */}
      {alertMessage && (
        <div
          className={`p-4 rounded-lg text-sm border flex items-start gap-2 ${
            alertMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
              : 'bg-rose-50 border-rose-300 text-rose-800'
          }`}
        >
          {alertMessage.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          )}
          <div className="font-medium flex-1">{alertMessage.text}</div>
          <button onClick={() => setAlertMessage(null)} className="text-slate-400 hover:text-slate-600 font-bold">
            ✕
          </button>
        </div>
      )}

      {/* Claims KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Total Claims</span>
            <FileSpreadsheet className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-2">
            {summary?.total_claims ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Discrepancy dockets created</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-indigo-200 shadow-sm bg-gradient-to-br from-white to-indigo-50/30">
          <div className="flex items-center justify-between text-xs text-indigo-700 font-medium">
            <span>Total Claim Amount</span>
            <DollarSign className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-black text-indigo-900 font-mono mt-2">
            ₹{summary ? Number(summary.total_claim_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Gross disputed leakage exposure</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-emerald-200 shadow-sm bg-gradient-to-br from-white to-emerald-50/40">
          <div className="flex items-center justify-between text-xs text-emerald-700 font-medium">
            <span>Recovered Amount</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-emerald-800 font-mono mt-2">
            ₹{summary ? Number(summary.total_recovered_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <p className="text-[11px] text-emerald-600 font-semibold mt-1">
            Recovery Rate: {summary?.recovery_rate_pct ?? '0.00'}%
          </p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-rose-200 shadow-sm bg-gradient-to-br from-white to-rose-50/40">
          <div className="flex items-center justify-between text-xs text-rose-700 font-medium">
            <span>Outstanding Balance</span>
            <AlertTriangle className="w-4 h-4 text-rose-500" />
          </div>
          <div className="text-2xl font-black text-rose-800 font-mono mt-2">
            ₹{summary ? Number(summary.total_outstanding_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Pending marketplace settlement</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="text-xs text-slate-500 font-medium">Claim Status Pipeline</div>
          <div className="grid grid-cols-3 gap-1 text-[10px] font-mono mt-2">
            <span className="p-1 bg-slate-100 rounded text-center">Draft: <strong>{summary?.status_counts.draft ?? 0}</strong></span>
            <span className="p-1 bg-amber-50 rounded text-center text-amber-800">Sub: <strong>{summary?.status_counts.submitted ?? 0}</strong></span>
            <span className="p-1 bg-blue-50 rounded text-center text-blue-800">Rev: <strong>{summary?.status_counts.in_review ?? 0}</strong></span>
          </div>
          <div className="grid grid-cols-2 gap-1 text-[10px] font-mono mt-1">
            <span className="p-1 bg-emerald-50 rounded text-center text-emerald-800">Rec: <strong>{summary?.status_counts.recovered ?? 0}</strong></span>
            <span className="p-1 bg-rose-50 rounded text-center text-rose-800">Rej: <strong>{summary?.status_counts.rejected ?? 0}</strong></span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-4">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by Order ID, Notes, or Claim Reason..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
              className="w-full pl-9 pr-9 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
            />
            {searchQuery && (
              <button
                onClick={() => { setSearchQuery(''); setCurrentPage(1); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <button
            onClick={resetFilters}
            className="px-3 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 rounded-lg transition-colors border border-rose-200"
          >
            Reset Filters
          </button>
        </div>

        {/* Dropdown Filters */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3 pt-3 border-t border-slate-100 text-xs">
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Partner
            </label>
            <select
              value={selectedPartner}
              onChange={(e) => { setSelectedPartner(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            >
              <option value="ALL">All Partners</option>
              <option value="shopify">Shopify D2C</option>
              <option value="amazon">Amazon India</option>
              <option value="flipkart">Flipkart</option>
              <option value="myntra">Myntra</option>
              <option value="blinkit">Blinkit</option>
              <option value="zepto">Zepto</option>
              <option value="delhivery">Delhivery</option>
              <option value="bluedart">Blue Dart</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Claim Status
            </label>
            <select
              value={selectedStatus}
              onChange={(e) => { setSelectedStatus(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            >
              <option value="ALL">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="submitted">Submitted</option>
              <option value="in_review">In Review</option>
              <option value="approved">Approved</option>
              <option value="recovered">Recovered</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Claim Reason
            </label>
            <select
              value={selectedReason}
              onChange={(e) => { setSelectedReason(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            >
              <option value="ALL">All Reasons</option>
              <option value="cod_remittance_missing">COD Remittance Missing</option>
              <option value="freight_overcharge">Freight Overcharge</option>
              <option value="excess_commission">Excess Commission</option>
              <option value="settlement_shortfall">Settlement Shortfall</option>
              <option value="excess_return_deduction">Excess Return Deduction</option>
              <option value="return_receipt_missing">Return Receipt Missing</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Min Claim (₹)
            </label>
            <input
              type="number"
              placeholder="0.00"
              value={minAmount}
              onChange={(e) => { setMinAmount(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs font-mono"
            />
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Max Claim (₹)
            </label>
            <input
              type="number"
              placeholder="50000.00"
              value={maxAmount}
              onChange={(e) => { setMaxAmount(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs font-mono"
            />
          </div>
        </div>
      </div>

      {/* Claims Table Container */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-3 bg-slate-50 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between text-xs text-slate-600 gap-2">
          <span className="font-semibold text-slate-800">
            {totalClaimsCount} Claims Listed
          </span>
          <div className="flex items-center gap-3">
            <span>Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setCurrentPage(1); }}
              className="px-2 py-1 bg-white border border-slate-300 rounded font-semibold text-xs"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-100 text-slate-600 uppercase text-[11px] font-semibold border-b border-slate-200">
              <tr>
                <th className="px-4 py-3">Order ID &amp; Partner</th>
                <th className="px-4 py-3">Claim Reason</th>
                <th 
                  onClick={() => handleSort('claim_amount')}
                  className="px-4 py-3 text-right cursor-pointer hover:bg-slate-200/60 select-none text-rose-700 font-bold"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Claim Amount</span>
                    {sortBy === 'claim_amount' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th 
                  onClick={() => handleSort('recovered_amount')}
                  className="px-4 py-3 text-right cursor-pointer hover:bg-slate-200/60 select-none text-emerald-700 font-bold"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Recovered</span>
                    {sortBy === 'recovered_amount' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th className="px-4 py-3 text-right">Outstanding</th>
                <th 
                  onClick={() => handleSort('claim_status')}
                  className="px-4 py-3 cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center gap-1">
                    <span>Status</span>
                    {sortBy === 'claim_status' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th 
                  onClick={() => handleSort('created_at')}
                  className="px-4 py-3 cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center gap-1">
                    <span>Created Date</span>
                    {sortBy === 'created_at' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th className="px-4 py-3">Notes</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, idx) => (
                  <tr key={`skel-${idx}`} className="animate-pulse">
                    <td className="px-4 py-3"><div className="h-4 bg-slate-200 rounded w-28" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-slate-200 rounded w-24" /></td>
                    <td className="px-4 py-3 text-right"><div className="h-4 bg-slate-200 rounded w-16 ml-auto" /></td>
                    <td className="px-4 py-3 text-right"><div className="h-4 bg-slate-200 rounded w-16 ml-auto" /></td>
                    <td className="px-4 py-3 text-right"><div className="h-4 bg-slate-200 rounded w-16 ml-auto" /></td>
                    <td className="px-4 py-3"><div className="h-5 bg-slate-200 rounded-full w-20" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-slate-200 rounded w-20" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-slate-200 rounded w-32" /></td>
                    <td className="px-4 py-3 text-right"><div className="h-6 bg-slate-200 rounded w-20 ml-auto" /></td>
                  </tr>
                ))
              ) : claims.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center text-slate-500 font-sans">
                    <FileCheck2 className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                    <p className="font-bold text-slate-700 text-sm">No Claims Found</p>
                    <p className="text-xs text-slate-400 mt-1">
                      No claims match your filter criteria or no draft claims have been generated yet.
                    </p>
                  </td>
                </tr>
              ) : (
                claims.map((c) => {
                  const outstanding = Math.max(0, Number(c.claim_amount) - Number(c.recovered_amount));
                  return (
                    <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-bold text-slate-900">{c.external_order_id}</div>
                        <div className="text-[10px] text-slate-500 uppercase font-sans">{c.partner_id}</div>
                      </td>
                      <td className="px-4 py-3 font-sans">
                        <span className="font-medium text-slate-800">{getReasonLabel(c.claim_reason)}</span>
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-rose-700">
                        ₹{Number(c.claim_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-emerald-700">
                        ₹{Number(c.recovered_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-slate-800">
                        ₹{outstanding.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 font-sans">
                        {getStatusBadge(c.claim_status)}
                      </td>
                      <td className="px-4 py-3 text-slate-500 text-[11px] font-sans">
                        {new Date(c.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 font-sans text-slate-600 truncate max-w-xs text-[11px]">
                        {c.notes || <span className="text-slate-300 italic">No notes</span>}
                      </td>
                      <td className="px-4 py-3 text-right font-sans">
                        <button
                          onClick={() => openClaimModal(c.id)}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-2.5 py-1 rounded border border-indigo-200 hover:bg-indigo-100 transition-colors"
                        >
                          Review &amp; Edit
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        {!isLoading && totalClaimsCount > 0 && (
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-600 gap-3">
            <div>
              Showing <span className="font-semibold text-slate-900">{(currentPage - 1) * pageSize + 1}</span> to{' '}
              <span className="font-semibold text-slate-900">{Math.min(currentPage * pageSize, totalClaimsCount)}</span>{' '}
              of <span className="font-semibold text-slate-900">{totalClaimsCount}</span> claims
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
                disabled={currentPage <= 1}
                className="px-2.5 py-1.5 rounded border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1 font-semibold"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Prev
              </button>
              <span className="px-3 py-1 font-mono text-slate-700">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
                disabled={currentPage >= totalPages}
                className="px-2.5 py-1.5 rounded border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1 font-semibold"
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Loading Detail Spinner */}
      {isLoadingDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-xs">
          <div className="bg-white p-4 rounded-xl shadow-lg flex items-center gap-2 text-xs font-semibold text-slate-700">
            <RefreshCw className="w-4 h-4 animate-spin text-indigo-600" />
            Loading Claim Dossier...
          </div>
        </div>
      )}

      {/* Claim Detail & Edit Modal */}
      {selectedClaimDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold">
                  <FileCheck2 className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base font-mono">
                    Dispute Claim: {selectedClaimDetail.external_order_id}
                  </h3>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500 font-sans mt-0.5">
                    <span className="uppercase font-semibold text-slate-700">{selectedClaimDetail.partner_id}</span>
                    <span>•</span>
                    <span>Reason: {getReasonLabel(selectedClaimDetail.claim_reason)}</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setSelectedClaimDetail(null)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold p-1 rounded-lg hover:bg-slate-100"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-700 font-sans">
              {/* Financial Snapshot */}
              <div className="grid grid-cols-3 gap-3 p-3.5 bg-slate-50 rounded-xl border border-slate-200 font-mono text-center">
                <div className="p-2 bg-white rounded-lg border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase font-sans">Claimed Amount</span>
                  <span className="font-bold text-rose-700 text-sm">₹{selectedClaimDetail.claim_amount}</span>
                </div>
                <div className="p-2 bg-white rounded-lg border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase font-sans">Recovered So Far</span>
                  <span className="font-bold text-emerald-700 text-sm">₹{selectedClaimDetail.recovered_amount}</span>
                </div>
                <div className="p-2 bg-white rounded-lg border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase font-sans">Outstanding</span>
                  <span className="font-bold text-slate-900 text-sm">
                    ₹{Math.max(0, Number(selectedClaimDetail.claim_amount) - Number(selectedClaimDetail.recovered_amount)).toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Status Update Form (Finance Exec only) */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <Edit3 className="w-3.5 h-3.5 text-indigo-600" />
                    Claim Status &amp; Recovery Management
                  </h4>
                  {isCoFounder && (
                    <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-semibold">
                      Read-Only Audit Mode
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Status Dropdown */}
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Lifecycle Status
                    </label>
                    <select
                      value={editStatus}
                      onChange={(e) => setEditStatus(e.target.value)}
                      disabled={isCoFounder || isUpdatingClaim}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white font-medium focus:ring-2 focus:ring-indigo-500 text-xs disabled:opacity-50"
                    >
                      <option value="draft">Draft (Internal)</option>
                      <option value="submitted">Submitted to Partner</option>
                      <option value="in_review">In Review / Under Investigation</option>
                      <option value="approved">Approved by Partner</option>
                      <option value="recovered">Recovered (Settled)</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </div>

                  {/* Recovered Amount */}
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Recovered Amount (₹)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={editRecoveredAmount}
                      onChange={(e) => setEditRecoveredAmount(e.target.value)}
                      disabled={isCoFounder || isUpdatingClaim}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white font-mono focus:ring-2 focus:ring-indigo-500 text-xs disabled:opacity-50 font-bold text-emerald-800"
                    />
                  </div>

                  {/* Recovery Date */}
                  <div className="sm:col-span-2">
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Recovery Settlement Date
                    </label>
                    <input
                      type="date"
                      value={editRecoveredDate}
                      onChange={(e) => setEditRecoveredDate(e.target.value)}
                      disabled={isCoFounder || isUpdatingClaim}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 text-xs disabled:opacity-50 font-mono"
                    />
                  </div>

                  {/* Notes */}
                  <div className="sm:col-span-2">
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Executive Notes &amp; Partner Docket References
                    </label>
                    <textarea
                      rows={3}
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      disabled={isCoFounder || isUpdatingClaim}
                      placeholder="Enter dispute ticket number, partner correspondence, or recovery batch details..."
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 text-xs disabled:opacity-50"
                    />
                  </div>
                </div>

                {!isCoFounder && (
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleSaveClaim}
                      disabled={isUpdatingClaim}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-colors shadow-sm disabled:opacity-50"
                    >
                      {isUpdatingClaim ? 'Saving...' : 'Save Claim Updates'}
                    </button>
                  </div>
                )}
              </div>

              {/* Supporting Financial Evidence */}
              <div>
                <h4 className="font-bold text-slate-900 mb-2 uppercase tracking-wider text-[11px]">
                  Supporting Financial Evidence (Immutable Ledger)
                </h4>
                <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 font-mono text-xs space-y-2">
                  <div className="flex justify-between">
                    <span className="text-slate-500 font-sans">Order Gross Value:</span>
                    <span className="font-bold text-slate-900">₹{selectedClaimDetail.evidence_json?.order_value || '0.00'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 font-sans">Expected Net Settlement:</span>
                    <span className="font-bold text-indigo-700">₹{selectedClaimDetail.evidence_json?.expected_amount || '0.00'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 font-sans">Actual Received Net:</span>
                    <span className="font-bold text-slate-900">₹{selectedClaimDetail.evidence_json?.received_amount || '0.00'}</span>
                  </div>
                  <div className="flex justify-between border-t border-slate-200 pt-1 text-rose-700 font-bold">
                    <span className="font-sans">Calculated Net Shortfall / Gap:</span>
                    <span>₹{selectedClaimDetail.evidence_json?.settlement_gap || '0.00'}</span>
                  </div>
                  {Number(selectedClaimDetail.evidence_json?.freight_excess) > 0 && (
                    <div className="flex justify-between text-purple-700 font-bold">
                      <span className="font-sans">Freight Tariff Overcharge:</span>
                      <span>₹{selectedClaimDetail.evidence_json?.freight_excess}</span>
                    </div>
                  )}
                  {Number(selectedClaimDetail.evidence_json?.return_loss) > 0 && (
                    <div className="flex justify-between text-amber-700 font-bold">
                      <span className="font-sans">Return Missing / Excess Loss:</span>
                      <span>₹{selectedClaimDetail.evidence_json?.return_loss}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setSelectedClaimDetail(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-900"
              >
                Close Claim
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
