import React, { useState, useEffect, useCallback } from 'react';
import { 
  Play, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  ShieldAlert, 
  RefreshCw, 
  Search, 
  Filter, 
  TrendingDown, 
  Calendar, 
  Layers,
  ArrowRight,
  Info,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  X,
  Truck,
  PackageCheck,
  RotateCcw,
  Building2,
  Receipt,
  CreditCard
} from 'lucide-react';
import { api, OrderRecon, ReconSummary, User, OrderTimelineResponse } from '../api/client';

interface ReconciliationHubProps {
  currentUser: User;
}

export const ReconciliationHub: React.FC<ReconciliationHubProps> = ({ currentUser }) => {
  // Data States
  const [orders, setOrders] = useState<OrderRecon[]>([]);
  const [summary, setSummary] = useState<ReconSummary | null>(null);
  const [totalOrdersCount, setTotalOrdersCount] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  
  // Filter & Search States
  const [asOfDate, setAsOfDate] = useState<string>('2026-11-01');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedPartner, setSelectedPartner] = useState<string>('ALL');
  const [activeStatusFilter, setActiveStatusFilter] = useState<string>('ALL');
  const [selectedReasonCode, setSelectedReasonCode] = useState<string>('ALL');
  const [selectedAgeBucket, setSelectedAgeBucket] = useState<string>('ALL');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  // Sorting & Pagination States
  const [sortBy, setSortBy] = useState<string>('money_at_risk');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);

  // Status & Detail States
  const [isReconciling, setIsReconciling] = useState<boolean>(false);
  const [isLoadingData, setIsLoadingData] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [alertMessage, setAlertMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Order Audit & Evidence Timeline Modal
  const [selectedOrderForAudit, setSelectedOrderForAudit] = useState<OrderRecon | null>(null);
  const [activeAuditTab, setActiveAuditTab] = useState<'breakdown' | 'timeline'>('breakdown');
  const [timelineData, setTimelineData] = useState<OrderTimelineResponse | null>(null);
  const [isLoadingTimeline, setIsLoadingTimeline] = useState<boolean>(false);

  const isCoFounder = currentUser.role === 'cofounder';

  const loadData = useCallback(async () => {
    setIsLoadingData(true);
    setFetchError(null);
    try {
      // 1. Fetch Global Summary KPIs
      const summaryData = await api.getReconSummary();
      setSummary(summaryData);

      // 2. Fetch Paginated & Filtered Orders from Backend API
      const params: any = {
        page: currentPage,
        page_size: pageSize,
        sort_by: sortBy,
        sort_dir: sortDir,
        envelope: true,
      };

      if (searchQuery.trim()) {
        params.search = searchQuery.trim();
      }
      if (selectedPartner !== 'ALL') {
        params.partner_id = selectedPartner.toLowerCase();
      }
      if (activeStatusFilter === 'RISK_ONLY') {
        params.has_risk = true;
      } else if (activeStatusFilter !== 'ALL') {
        params.status = activeStatusFilter.toLowerCase();
      }
      if (selectedReasonCode !== 'ALL') {
        params.reason_code = selectedReasonCode.toLowerCase();
      }
      if (selectedAgeBucket !== 'ALL') {
        params.age_bucket = selectedAgeBucket;
      }
      if (startDate) {
        params.start_date = startDate;
      }
      if (endDate) {
        params.end_date = endDate;
      }

      const res = await api.listReconOrders(params);
      if (res && res.items) {
        setOrders(res.items);
        setTotalOrdersCount(res.total);
        setTotalPages(res.pages);
      } else if (Array.isArray(res)) {
        setOrders(res);
        setTotalOrdersCount(res.length);
        setTotalPages(1);
      }
    } catch (err: any) {
      console.error('Failed to load reconciliation orders:', err);
      setFetchError(err.message || 'Failed to fetch reconciliation records from backend.');
    } finally {
      setIsLoadingData(false);
    }
  }, [
    currentPage,
    pageSize,
    sortBy,
    sortDir,
    searchQuery,
    selectedPartner,
    activeStatusFilter,
    selectedReasonCode,
    selectedAgeBucket,
    startDate,
    endDate
  ]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Order Detail & Timeline Loading
  const openOrderAudit = async (order: OrderRecon) => {
    setSelectedOrderForAudit(order);
    setActiveAuditTab('breakdown');
    setTimelineData(null);
    setIsLoadingTimeline(true);
    try {
      const data = await api.getOrderTimeline(order.order_id || order.external_order_id, order.partner_id);
      setTimelineData(data);
    } catch (err) {
      console.error('Failed to fetch evidence timeline for order', order.order_id, err);
    } finally {
      setIsLoadingTimeline(false);
    }
  };

  const handleRunRecon = async () => {
    if (isCoFounder) {
      setAlertMessage({
        type: 'error',
        text: 'Co-founders have read-only audit permissions. Running reconciliation requires Finance Executive access.'
      });
      return;
    }

    setIsReconciling(true);
    setAlertMessage(null);
    try {
      const result = await api.triggerRecon(asOfDate);
      setAlertMessage({
        type: 'success',
        text: `Reconciliation executed successfully! Reconciled ${result.total_orders_reconciled} orders. Total Money at Risk: ₹${result.total_money_at_risk}. Generated ${result.draft_claims_generated} draft claims.`
      });
      loadData();
    } catch (err: any) {
      setAlertMessage({
        type: 'error',
        text: err.message || 'Failed to execute reconciliation.'
      });
    } finally {
      setIsReconciling(false);
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

  const resetAllFilters = () => {
    setSearchQuery('');
    setSelectedPartner('ALL');
    setActiveStatusFilter('ALL');
    setSelectedReasonCode('ALL');
    setSelectedAgeBucket('ALL');
    setStartDate('');
    setEndDate('');
    setSortBy('money_at_risk');
    setSortDir('desc');
    setCurrentPage(1);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'settled':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Settled
          </span>
        );
      case 'short_paid':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> Short Paid
          </span>
        );
      case 'unpaid_past_due':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" /> Unpaid Past Due
          </span>
        );
      case 'freight_overcharged':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-300">
            <TrendingDown className="w-3.5 h-3.5 text-purple-600" /> Freight Overcharge
          </span>
        );
      case 'return_not_received':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-900 border border-red-400">
            <ShieldAlert className="w-3.5 h-3.5 text-red-700" /> Return Not Received
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            <Clock className="w-3.5 h-3.5 text-slate-500" /> Pending
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

  const getTimelineIcon = (feedType: string) => {
    switch (feedType) {
      case 'orders':
        return <PackageCheck className="w-4 h-4 text-emerald-600" />;
      case 'settlement':
        return <Receipt className="w-4 h-4 text-indigo-600" />;
      case 'cod':
        return <CreditCard className="w-4 h-4 text-amber-600" />;
      case 'freight':
        return <Truck className="w-4 h-4 text-purple-600" />;
      case 'tracking':
        return <Truck className="w-4 h-4 text-sky-600" />;
      case 'warehouse':
        return <Building2 className="w-4 h-4 text-blue-600" />;
      case 'reversal':
        return <RotateCcw className="w-4 h-4 text-rose-600" />;
      default:
        return <Clock className="w-4 h-4 text-slate-500" />;
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-200 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-7 h-7 text-indigo-600" />
            Orders &amp; Reconciliation Hub
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Deterministic pre-TCS/TDS reconciliation, rate-card tariff calculations, and non-overlapping Money at Risk.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-slate-300 text-xs shadow-sm">
            <Calendar className="w-4 h-4 text-slate-500" />
            <span className="font-semibold text-slate-700">As Of Date:</span>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              disabled={isReconciling}
              className="bg-transparent focus:outline-none font-mono text-slate-900 font-semibold"
            />
          </div>

          <button
            onClick={handleRunRecon}
            disabled={isReconciling || isCoFounder}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold shadow-sm transition-all ${
              isCoFounder
                ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer hover:shadow'
            }`}
          >
            {isReconciling ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Calculating...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                Run Reconciliation
              </>
            )}
          </button>
        </div>
      </div>

      {/* Co-founder Audit Mode Notice */}
      {isCoFounder && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-700 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-amber-800">
            <p className="font-semibold">Co-founder Audit Mode</p>
            <p className="mt-0.5 text-amber-700">
              You are viewing verified financial calculations and non-overlapping risk in read-only audit mode.
              Re-executing reconciliation requires Finance Executive credentials.
            </p>
          </div>
        </div>
      )}

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
          <button
            onClick={() => setAlertMessage(null)}
            className="text-slate-400 hover:text-slate-600 ml-2 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Top 5 KPI Summary Cards (Interactive quick-filters) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Money at Risk */}
        <div 
          onClick={() => { setActiveStatusFilter('RISK_ONLY'); setCurrentPage(1); }}
          className={`bg-white p-5 rounded-xl border transition-all cursor-pointer shadow-sm ${
            activeStatusFilter === 'RISK_ONLY' ? 'ring-2 ring-rose-500 border-rose-300' : 'border-rose-200 hover:border-rose-300'
          } bg-gradient-to-br from-white to-rose-50/40`}
        >
          <div className="flex items-center justify-between text-xs text-rose-600 font-semibold mb-1">
            <span>Money at Risk</span>
            <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 text-[10px] font-extrabold uppercase">
              Non-Overlapping
            </span>
          </div>
          <div className="text-2xl font-black text-rose-700 font-mono tracking-tight mt-1">
            ₹{summary ? Number(summary.total_money_at_risk).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <p className="text-[11px] text-slate-500 mt-2">
            Settlement gap + freight excess + return loss (de-duplicated)
          </p>
        </div>

        {/* Short Paid */}
        <div 
          onClick={() => { setActiveStatusFilter('SHORT_PAID'); setCurrentPage(1); }}
          className={`bg-white p-5 rounded-xl border transition-all cursor-pointer shadow-sm ${
            activeStatusFilter === 'SHORT_PAID' ? 'ring-2 ring-amber-500 border-amber-300' : 'border-slate-200 hover:border-amber-300'
          }`}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Short Paid Orders</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-2">
            {summary?.short_paid_count ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Settlement &lt; Expected (Variance &gt; ₹10)</p>
        </div>

        {/* Unpaid Past Due */}
        <div 
          onClick={() => { setActiveStatusFilter('UNPAID_PAID_DUE'); setCurrentPage(1); }}
          className={`bg-white p-5 rounded-xl border transition-all cursor-pointer shadow-sm ${
            activeStatusFilter === 'UNPAID_PAID_DUE' ? 'ring-2 ring-rose-500 border-rose-300' : 'border-slate-200 hover:border-rose-300'
          }`}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Unpaid Past Due</span>
            <Clock className="w-4 h-4 text-rose-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-2">
            {summary?.unpaid_past_due_count ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Past SLA due date with ₹0 received</p>
        </div>

        {/* Freight Overcharge */}
        <div 
          onClick={() => { setActiveStatusFilter('FREIGHT_OVERCHARGED'); setCurrentPage(1); }}
          className={`bg-white p-5 rounded-xl border transition-all cursor-pointer shadow-sm ${
            activeStatusFilter === 'FREIGHT_OVERCHARGED' ? 'ring-2 ring-purple-500 border-purple-300' : 'border-slate-200 hover:border-purple-300'
          }`}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Freight Overcharge</span>
            <TrendingDown className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-2">
            {summary?.freight_overcharged_count ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Actual courier fee &gt; rate card tariff</p>
        </div>

        {/* Return Not Received */}
        <div 
          onClick={() => { setActiveStatusFilter('RETURN_NOT_RECEIVED'); setCurrentPage(1); }}
          className={`bg-white p-5 rounded-xl border transition-all cursor-pointer shadow-sm ${
            activeStatusFilter === 'RETURN_NOT_RECEIVED' ? 'ring-2 ring-red-500 border-red-400' : 'border-slate-200 hover:border-red-300'
          }`}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Return Not Received</span>
            <ShieldAlert className="w-4 h-4 text-red-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-2">
            {summary?.return_not_received_count ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Refunded but missing verified dock receipt</p>
        </div>
      </div>

      {/* Comprehensive Filter and Search Bar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-4">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by Order ID, External Ref, or Channel..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
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

          {/* Quick Date Presets */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const now = new Date();
                const past7 = new Date();
                past7.setDate(now.getDate() - 7);
                setStartDate(past7.toISOString().split('T')[0]);
                setEndDate(now.toISOString().split('T')[0]);
                setCurrentPage(1);
              }}
              className="px-2.5 py-1.5 text-[11px] font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors border border-slate-200"
            >
              Last 7 Days
            </button>
            <button
              onClick={() => {
                const now = new Date();
                const past30 = new Date();
                past30.setDate(now.getDate() - 30);
                setStartDate(past30.toISOString().split('T')[0]);
                setEndDate(now.toISOString().split('T')[0]);
                setCurrentPage(1);
              }}
              className="px-2.5 py-1.5 text-[11px] font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors border border-slate-200"
            >
              Last 30 Days
            </button>
            <button
              onClick={resetAllFilters}
              className="px-2.5 py-1.5 text-[11px] font-semibold text-rose-600 hover:bg-rose-50 rounded-lg transition-colors border border-rose-200"
            >
              Reset Filters
            </button>
          </div>
        </div>

        {/* Dropdown Filters Row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-3 border-t border-slate-100 text-xs">
          {/* Partner Filter */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Partner Channel
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

          {/* Status Filter */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Recon Status
            </label>
            <select
              value={activeStatusFilter}
              onChange={(e) => { setActiveStatusFilter(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            >
              <option value="ALL">All Statuses</option>
              <option value="RISK_ONLY">Has Money at Risk (&gt;₹0)</option>
              <option value="SETTLED">Settled</option>
              <option value="SHORT_PAID">Short Paid</option>
              <option value="UNPAID_PAID_DUE">Unpaid Past Due</option>
              <option value="FREIGHT_OVERCHARGED">Freight Overcharged</option>
              <option value="RETURN_NOT_RECEIVED">Return Not Received</option>
              <option value="PENDING">Pending</option>
            </select>
          </div>

          {/* Discrepancy Reason Code */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Discrepancy Reason
            </label>
            <select
              value={selectedReasonCode}
              onChange={(e) => { setSelectedReasonCode(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            >
              <option value="ALL">All Discrepancies</option>
              <option value="cod_remittance_missing">COD Remittance Missing</option>
              <option value="freight_overcharge">Freight Overcharge</option>
              <option value="excess_commission">Excess Commission</option>
              <option value="settlement_shortfall">Settlement Shortfall</option>
              <option value="excess_return_deduction">Excess Return Deduction</option>
              <option value="return_receipt_missing">Return Receipt Missing</option>
              <option value="missing_rate_card">Missing Rate Card</option>
              <option value="overpaid_review">Overpaid (Review)</option>
            </select>
          </div>

          {/* Age Bucket */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Aging Bucket
            </label>
            <select
              value={selectedAgeBucket}
              onChange={(e) => { setSelectedAgeBucket(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            >
              <option value="ALL">All Ages</option>
              <option value="0-7">0–7 Days</option>
              <option value="8-15">8–15 Days</option>
              <option value="16-30">16–30 Days</option>
              <option value="31+">31+ Days</option>
            </select>
          </div>

          {/* Start Date */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => { setStartDate(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => { setEndDate(e.target.value); setCurrentPage(1); }}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            />
          </div>
        </div>
      </div>

      {/* Orders Table Container */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {/* Table Header Summary */}
        <div className="px-6 py-3 bg-slate-50 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between text-xs text-slate-600 gap-2">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-800">
              {totalOrdersCount} Reconciled Orders Found
            </span>
            {searchQuery && (
              <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 text-[10px]">
                Matching &quot;{searchQuery}&quot;
              </span>
            )}
          </div>
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

        {/* Error State */}
        {fetchError && (
          <div className="p-8 text-center bg-rose-50 border-b border-rose-200">
            <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto mb-2" />
            <h3 className="text-sm font-bold text-rose-800">Failed to Load Orders</h3>
            <p className="text-xs text-rose-600 mt-1 max-w-md mx-auto">{fetchError}</p>
            <button
              onClick={() => loadData()}
              className="mt-3 px-4 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-semibold hover:bg-rose-700"
            >
              Retry
            </button>
          </div>
        )}

        {/* Orders Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-100 text-slate-600 uppercase text-[11px] font-semibold border-b border-slate-200">
              <tr>
                <th 
                  onClick={() => handleSort('order_date')}
                  className="px-4 py-3 cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center gap-1">
                    <span>Order ID &amp; Date</span>
                    {sortBy === 'order_date' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th className="px-4 py-3">Partner • Mode</th>
                <th 
                  onClick={() => handleSort('order_value')}
                  className="px-4 py-3 text-right cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Order Value</span>
                    {sortBy === 'order_value' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th 
                  onClick={() => handleSort('expected_amount')}
                  className="px-4 py-3 text-right cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Expected Net</span>
                    {sortBy === 'expected_amount' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th 
                  onClick={() => handleSort('received_amount')}
                  className="px-4 py-3 text-right cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Received Net</span>
                    {sortBy === 'received_amount' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th 
                  onClick={() => handleSort('difference')}
                  className="px-4 py-3 text-right cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Variance</span>
                    {sortBy === 'difference' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th 
                  onClick={() => handleSort('status')}
                  className="px-4 py-3 cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center gap-1">
                    <span>Status</span>
                    {sortBy === 'status' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th 
                  onClick={() => handleSort('money_at_risk')}
                  className="px-4 py-3 text-right text-rose-700 font-bold cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Money at Risk</span>
                    {sortBy === 'money_at_risk' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th 
                  onClick={() => handleSort('age_days')}
                  className="px-4 py-3 cursor-pointer hover:bg-slate-200/60 select-none"
                >
                  <div className="flex items-center gap-1">
                    <span>Aging</span>
                    {sortBy === 'age_days' && (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                </th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {isLoadingData ? (
                // Loading Skeleton Rows
                Array.from({ length: 5 }).map((_, idx) => (
                  <tr key={`skeleton-${idx}`} className="animate-pulse">
                    <td className="px-4 py-3.5">
                      <div className="h-3.5 bg-slate-200 rounded w-28 mb-1" />
                      <div className="h-2.5 bg-slate-100 rounded w-16" />
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="h-3.5 bg-slate-200 rounded w-20 mb-1" />
                      <div className="h-2.5 bg-slate-100 rounded w-12" />
                    </td>
                    <td className="px-4 py-3.5 text-right"><div className="h-3.5 bg-slate-200 rounded w-16 ml-auto" /></td>
                    <td className="px-4 py-3.5 text-right"><div className="h-3.5 bg-slate-200 rounded w-16 ml-auto" /></td>
                    <td className="px-4 py-3.5 text-right"><div className="h-3.5 bg-slate-200 rounded w-16 ml-auto" /></td>
                    <td className="px-4 py-3.5 text-right"><div className="h-3.5 bg-slate-200 rounded w-14 ml-auto" /></td>
                    <td className="px-4 py-3.5"><div className="h-5 bg-slate-200 rounded-full w-20" /></td>
                    <td className="px-4 py-3.5 text-right"><div className="h-3.5 bg-slate-200 rounded w-16 ml-auto" /></td>
                    <td className="px-4 py-3.5"><div className="h-4 bg-slate-200 rounded w-12" /></td>
                    <td className="px-4 py-3.5 text-right"><div className="h-6 bg-slate-200 rounded w-24 ml-auto" /></td>
                  </tr>
                ))
              ) : orders.length === 0 ? (
                // Empty State
                <tr>
                  <td colSpan={10} className="px-4 py-16 text-center text-slate-500 font-sans">
                    <div className="flex flex-col items-center justify-center">
                      <Filter className="w-10 h-10 text-slate-300 mb-3" />
                      <p className="font-bold text-slate-700 text-sm">No Reconciliation Records Found</p>
                      <p className="text-xs text-slate-400 mt-1 max-w-sm">
                        No orders matched your current search and filter combination.
                      </p>
                      <button
                        onClick={resetAllFilters}
                        className="mt-4 px-3.5 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 rounded-lg text-xs font-semibold transition-colors"
                      >
                        Reset All Filters
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                // Rendered Orders
                orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50/80 transition-colors">
                    {/* Order ID & Date */}
                    <td className="px-4 py-3">
                      <div className="font-bold text-slate-900">{o.external_order_id || o.order_id}</div>
                      <div className="text-[10px] text-slate-400 font-sans">
                        {new Date(o.order_date).toLocaleDateString()}
                      </div>
                    </td>

                    {/* Partner & Payment Mode */}
                    <td className="px-4 py-3 uppercase font-sans">
                      <div className="font-semibold text-slate-800">{o.partner_id}</div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono">
                        {o.payment_mode}
                      </span>
                    </td>

                    {/* Order Value */}
                    <td className="px-4 py-3 text-right text-slate-800">
                      ₹{Number(o.order_value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>

                    {/* Expected Net */}
                    <td className="px-4 py-3 text-right text-indigo-700 font-semibold">
                      {o.expected_amount !== null
                        ? `₹${Number(o.expected_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                        : <span className="text-amber-600 font-sans text-[11px]">No Rate Card</span>}
                    </td>

                    {/* Received Net */}
                    <td className="px-4 py-3 text-right text-slate-800 font-semibold">
                      ₹{Number(o.received_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>

                    {/* Variance */}
                    <td className="px-4 py-3 text-right">
                      {o.difference !== null ? (
                        <span className={`font-bold ${
                          Number(o.difference) < -10
                            ? 'text-rose-600'
                            : Number(o.difference) > 10
                            ? 'text-emerald-600'
                            : 'text-slate-500'
                        }`}>
                          {Number(o.difference) > 0 ? '+' : ''}
                          ₹{Number(o.difference).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      ) : (
                        <span className="text-slate-400 font-sans">-</span>
                      )}
                    </td>

                    {/* Status Pill */}
                    <td className="px-4 py-3 font-sans">
                      {getStatusBadge(o.status)}
                    </td>

                    {/* Money at Risk */}
                    <td className="px-4 py-3 text-right font-bold text-rose-700 font-mono">
                      {Number(o.money_at_risk) > 0 ? (
                        `₹${Number(o.money_at_risk).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                      ) : (
                        <span className="text-slate-300 font-normal">₹0.00</span>
                      )}
                    </td>

                    {/* Age & Bucket */}
                    <td className="px-4 py-3 font-sans">
                      {o.age_days > 0 ? (
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          o.age_days > 30 ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-700'
                        }`}>
                          {o.age_days}d ({o.age_bucket})
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[10px]">0d</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3 text-right font-sans">
                      <button
                        onClick={() => openOrderAudit(o)}
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-2.5 py-1 rounded border border-indigo-200 hover:bg-indigo-100 transition-colors"
                      >
                        Audit &amp; Timeline
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Server-Side Pagination Footer */}
        {!isLoadingData && totalOrdersCount > 0 && (
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-600 gap-3">
            <div>
              Showing <span className="font-semibold text-slate-900">{(currentPage - 1) * pageSize + 1}</span> to{' '}
              <span className="font-semibold text-slate-900">
                {Math.min(currentPage * pageSize, totalOrdersCount)}
              </span>{' '}
              of <span className="font-semibold text-slate-900">{totalOrdersCount}</span> orders
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

      {/* Interactive Order Detail & Evidence Timeline Modal */}
      {selectedOrderForAudit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold">
                  <Info className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base font-mono">
                    {selectedOrderForAudit.external_order_id || selectedOrderForAudit.order_id}
                  </h3>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500 font-sans mt-0.5">
                    <span className="uppercase font-semibold text-slate-700">{selectedOrderForAudit.partner_id}</span>
                    <span>•</span>
                    <span>{selectedOrderForAudit.payment_mode}</span>
                    <span>•</span>
                    <span>{new Date(selectedOrderForAudit.order_date).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setSelectedOrderForAudit(null)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold p-1 rounded-lg hover:bg-slate-100 transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Modal Navigation Tabs */}
            <div className="flex border-b border-slate-200 bg-slate-50/50 px-6">
              <button
                onClick={() => setActiveAuditTab('breakdown')}
                className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors ${
                  activeAuditTab === 'breakdown'
                    ? 'border-indigo-600 text-indigo-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                Financial Breakdown &amp; Tariff Audit
              </button>
              <button
                onClick={() => setActiveAuditTab('timeline')}
                className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeAuditTab === 'timeline'
                    ? 'border-indigo-600 text-indigo-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                Cross-Feed Evidence Timeline
                {timelineData && (
                  <span className="px-1.5 py-0.2 rounded-full bg-indigo-100 text-indigo-800 text-[10px]">
                    {timelineData.total_events}
                  </span>
                )}
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-700 font-sans">
              {activeAuditTab === 'breakdown' ? (
                <>
                  {/* Status & Risk Summary */}
                  <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-200">
                    <div>
                      <span className="text-[11px] text-slate-500 font-semibold uppercase">Reconciliation Outcome</span>
                      <div className="mt-1">{getStatusBadge(selectedOrderForAudit.status)}</div>
                      {selectedOrderForAudit.reason_codes.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {selectedOrderForAudit.reason_codes.map((rc) => (
                            <span key={rc} className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                              {getReasonLabel(rc)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <span className="text-[11px] text-slate-500 font-semibold uppercase">Non-Overlapping Money at Risk</span>
                      <div className="text-2xl font-black text-rose-700 font-mono mt-0.5">
                        ₹{Number(selectedOrderForAudit.money_at_risk).toFixed(2)}
                      </div>
                    </div>
                  </div>

                  {/* Deduction Breakdown Grid */}
                  <div>
                    <h4 className="font-bold text-slate-900 mb-2 uppercase tracking-wider text-[11px]">
                      Rate Card Expected Deductions
                    </h4>
                    <div className="grid grid-cols-2 gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200 font-mono">
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">Gross Order Value:</span>
                        <div className="font-bold text-slate-900">₹{selectedOrderForAudit.order_value}</div>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">Expected Commission:</span>
                        <div className="font-bold text-slate-900">-₹{selectedOrderForAudit.expected_commission}</div>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">Expected Fixed Fee:</span>
                        <div className="font-bold text-slate-900">-₹{selectedOrderForAudit.expected_fixed_fee}</div>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">Expected Freight Charges:</span>
                        <div className="font-bold text-slate-900">-₹{selectedOrderForAudit.expected_freight}</div>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">Expected COD Fee:</span>
                        <div className="font-bold text-slate-900">-₹{selectedOrderForAudit.expected_cod_fee}</div>
                      </div>
                      <div className="border-t border-slate-200 pt-2 col-span-2 flex justify-between font-bold text-indigo-700 text-sm">
                        <span>Expected Net Settlement:</span>
                        <span>₹{selectedOrderForAudit.expected_amount || 'N/A'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Received Financials */}
                  <div>
                    <h4 className="font-bold text-slate-900 mb-2 uppercase tracking-wider text-[11px]">
                      Actual Received Telemetry (Pre-Tax Comparable)
                    </h4>
                    <div className="grid grid-cols-2 gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200 font-mono">
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">Settlement Credit:</span>
                        <div className="font-bold text-slate-900">₹{selectedOrderForAudit.settlement_credit}</div>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">COD Remittance:</span>
                        <div className="font-bold text-slate-900">₹{selectedOrderForAudit.cod_remittance}</div>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">Actual Freight Billed:</span>
                        <div className="font-bold text-slate-900">₹{selectedOrderForAudit.actual_freight}</div>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[11px] font-sans">Actual Commission Billed:</span>
                        <div className="font-bold text-slate-900">₹{selectedOrderForAudit.actual_commission}</div>
                      </div>
                      <div className="col-span-2 border-t border-slate-200 pt-2 flex justify-between font-bold text-slate-900 text-sm">
                        <span>Total Comparable Received:</span>
                        <span>₹{selectedOrderForAudit.received_amount}</span>
                      </div>
                    </div>
                  </div>

                  {/* Statutory Tax Separation */}
                  <div className="p-3.5 bg-blue-50 border border-blue-200 rounded-xl text-blue-900">
                    <span className="font-bold text-xs">Statutory Tax Isolation (Mandatory Safeguard):</span>
                    <p className="mt-1 text-[11px] text-blue-800">
                      GST TCS (Sec 52 CGST Act): ₹{selectedOrderForAudit.tcs_amount} • Income Tax TDS (Sec 194-O): ₹{selectedOrderForAudit.tds_amount}
                      <br />
                      <span className="italic mt-1 block">
                        Statutory withholdings are isolated 100% from financial leakage calculations in accordance with Company A&apos;s tax compliance policy.
                      </span>
                    </p>
                  </div>

                  {/* Non-Overlapping Money at Risk Formula */}
                  {Number(selectedOrderForAudit.money_at_risk) > 0 && (
                    <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 font-mono">
                      <span className="font-bold text-xs uppercase tracking-wide">
                        Non-Overlapping Leakage Breakdown:
                      </span>
                      <div className="grid grid-cols-3 gap-3 mt-2 text-center text-xs">
                        <div className="p-3 bg-white rounded-lg border border-rose-200 shadow-sm">
                          <span className="text-slate-500 block text-[10px] uppercase font-sans">Settlement Gap</span>
                          <span className="font-bold text-slate-900 text-sm">₹{selectedOrderForAudit.settlement_gap_component}</span>
                        </div>
                        <div className="p-3 bg-white rounded-lg border border-rose-200 shadow-sm">
                          <span className="text-slate-500 block text-[10px] uppercase font-sans">Freight Excess</span>
                          <span className="font-bold text-slate-900 text-sm">₹{selectedOrderForAudit.freight_excess_component}</span>
                        </div>
                        <div className="p-3 bg-white rounded-lg border border-rose-200 shadow-sm">
                          <span className="text-slate-500 block text-[10px] uppercase font-sans">Return Loss</span>
                          <span className="font-bold text-slate-900 text-sm">₹{selectedOrderForAudit.return_loss_component}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                /* Cross-Feed Evidence Timeline */
                <div className="space-y-4">
                  {isLoadingTimeline ? (
                    <div className="py-12 text-center text-slate-500">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-600 mb-2" />
                      Loading chronological evidence trail...
                    </div>
                  ) : !timelineData || timelineData.timeline.length === 0 ? (
                    <div className="py-12 text-center text-slate-400">
                      No telemetry or statement events found for this order.
                    </div>
                  ) : (
                    <div className="relative border-l-2 border-indigo-200 ml-4 pl-6 space-y-6">
                      {timelineData.timeline.map((ev, index) => (
                        <div key={ev.id || index} className="relative group">
                          {/* Dot indicator */}
                          <div className="absolute -left-[31px] top-1.5 w-4 h-4 rounded-full bg-white border-2 border-indigo-600 flex items-center justify-center">
                            <div className="w-1.5 h-1.5 rounded-full bg-indigo-600" />
                          </div>

                          {/* Event Card */}
                          <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200 shadow-sm group-hover:border-indigo-300 transition-colors">
                            <div className="flex items-center justify-between text-xs">
                              <div className="flex items-center gap-2">
                                {getTimelineIcon(ev.feed_type)}
                                <span className="font-bold text-slate-900 uppercase tracking-wide">
                                  {ev.event_type.replace(/_/g, ' ')}
                                </span>
                                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-50 text-indigo-700 border border-indigo-200">
                                  {ev.feed_type}
                                </span>
                              </div>
                              <span className="text-slate-400 text-[11px] font-mono">
                                {new Date(ev.event_timestamp).toLocaleString()}
                              </span>
                            </div>

                            <div className="mt-2 text-xs text-slate-600 grid grid-cols-2 gap-2">
                              <div>
                                <span className="text-slate-400 text-[10px]">Source Partner:</span>
                                <span className="font-semibold text-slate-800 ml-1 uppercase">{ev.source_partner_id}</span>
                              </div>
                              {ev.amount !== null && (
                                <div className="text-right">
                                  <span className="text-slate-400 text-[10px]">Amount:</span>
                                  <span className="font-bold text-slate-900 ml-1 font-mono">₹{ev.amount}</span>
                                </div>
                              )}
                              {ev.transaction_reference && (
                                <div className="col-span-2">
                                  <span className="text-slate-400 text-[10px]">Reference:</span>
                                  <span className="font-mono text-slate-700 ml-1">{ev.transaction_reference}</span>
                                </div>
                              )}
                              {ev.status && (
                                <div>
                                  <span className="text-slate-400 text-[10px]">Status:</span>
                                  <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-200 text-slate-800">
                                    {ev.status}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setSelectedOrderForAudit(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-900 transition-colors shadow-sm"
              >
                Close Audit Detail
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
