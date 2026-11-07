import React, { useState, useEffect } from 'react';
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
  Info
} from 'lucide-react';
import { api, OrderRecon, ReconSummary, User } from '../api/client';

interface ReconciliationHubProps {
  currentUser: User;
}

export const ReconciliationHub: React.FC<ReconciliationHubProps> = ({ currentUser }) => {
  const [orders, setOrders] = useState<OrderRecon[]>([]);
  const [summary, setSummary] = useState<ReconSummary | null>(null);
  const [asOfDate, setAsOfDate] = useState<string>('2026-11-01');
  const [activeStatusFilter, setActiveStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedPartner, setSelectedPartner] = useState<string>('ALL');
  const [selectedAgeBucket, setSelectedAgeBucket] = useState<string>('ALL');
  const [isReconciling, setIsReconciling] = useState<boolean>(false);
  const [isLoadingData, setIsLoadingData] = useState<boolean>(true);
  const [selectedOrderForAudit, setSelectedOrderForAudit] = useState<OrderRecon | null>(null);
  const [alertMessage, setAlertMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const isCoFounder = currentUser.role === 'cofounder';

  useEffect(() => {
    loadData();
  }, [activeStatusFilter, selectedPartner]);

  const loadData = async () => {
    setIsLoadingData(true);
    try {
      const summaryData = await api.getReconSummary();
      setSummary(summaryData);

      const params: any = {};
      if (activeStatusFilter === 'RISK_ONLY') {
        params.has_risk = true;
      } else if (activeStatusFilter !== 'ALL') {
        params.status = activeStatusFilter.toLowerCase();
      }
      if (selectedPartner !== 'ALL') {
        params.partner_id = selectedPartner.toLowerCase();
      }

      const ordersData = await api.listReconOrders(params);
      setOrders(ordersData);
    } catch (err: any) {
      console.error('Failed to load reconciliation data:', err);
    } finally {
      setIsLoadingData(false);
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
        text: `Reconciliation executed successfully! Reconciled ${result.total_orders_reconciled} orders. Total Money at Risk: ₹${result.total_money_at_risk}.`
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

  const filteredOrders = orders.filter((o) => {
    if (selectedAgeBucket !== 'ALL' && o.age_bucket !== selectedAgeBucket) {
      return false;
    }
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      (o.external_order_id || o.order_id).toLowerCase().includes(query) ||
      o.partner_id.toLowerCase().includes(query) ||
      o.reason_codes.some((rc) => rc.toLowerCase().includes(query))
    );
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-200 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-7 h-7 text-indigo-600" />
            Reconciliation Hub
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Deterministic pre-TCS/TDS reconciliation, rate-card tariff calculations, and non-overlapping Money at Risk.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-slate-300 text-xs">
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

      {/* Co-founder Notice */}
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
          <div className="font-medium">{alertMessage.text}</div>
        </div>
      )}

      {/* Top 5 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Money at Risk */}
        <div className="bg-white p-5 rounded-xl border border-rose-200 shadow-sm bg-gradient-to-br from-white to-rose-50/30">
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
        <div className="bg-white p-5 rounded-xl border border-amber-200 shadow-sm">
          <div className="text-xs text-amber-700 font-semibold mb-1">Short Paid Orders</div>
          <div className="text-2xl font-bold text-amber-900 font-mono tracking-tight mt-1">
            {summary?.short_paid_count || 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-2">Underpaid beyond ₹10 threshold</p>
        </div>

        {/* Unpaid Past Due */}
        <div className="bg-white p-5 rounded-xl border border-rose-200 shadow-sm">
          <div className="text-xs text-rose-700 font-semibold mb-1">Unpaid Past Due</div>
          <div className="text-2xl font-bold text-rose-900 font-mono tracking-tight mt-1">
            {summary?.unpaid_past_due_count || 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-2">COD or prepaid with ₹0 remittance past deadline</p>
        </div>

        {/* Clean Settled */}
        <div className="bg-white p-5 rounded-xl border border-emerald-200 shadow-sm">
          <div className="text-xs text-emerald-700 font-semibold mb-1">Cleanly Settled</div>
          <div className="text-2xl font-bold text-emerald-900 font-mono tracking-tight mt-1">
            {summary?.settled_count || 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-2">Variance within ±₹10 tolerance</p>
        </div>

        {/* Pending Orders */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-600 font-semibold mb-1">
            <span>Pending Window</span>
            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px]">₹0 Risk</span>
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono tracking-tight mt-1">
            {summary?.pending_count || 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-2">Awaiting due date or return transit</p>
        </div>
      </div>

      {/* Age Buckets Overview */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-500" />
          <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">Age Buckets (Orders at Risk):</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {[
            { label: '0–7 days', count: summary?.age_bucket_counts?.['0-7'] || 0, badge: 'bg-emerald-100 text-emerald-800' },
            { label: '8–15 days', count: summary?.age_bucket_counts?.['8-15'] || 0, badge: 'bg-blue-100 text-blue-800' },
            { label: '16–30 days', count: summary?.age_bucket_counts?.['16-30'] || 0, badge: 'bg-amber-100 text-amber-800' },
            { label: '31+ days', count: summary?.age_bucket_counts?.['31+'] || 0, badge: 'bg-rose-100 text-rose-800' }
          ].map((b, idx) => (
            <div key={idx} className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 shadow-2xs">
              <span>{b.label}:</span>
              <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${b.badge}`}>{b.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          {/* Status Pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { key: 'ALL', label: 'All Orders' },
              { key: 'RISK_ONLY', label: 'Money at Risk Only' },
              { key: 'SHORT_PAID', label: 'Short Paid' },
              { key: 'UNPAID_PAST_DUE', label: 'Unpaid Past Due' },
              { key: 'FREIGHT_OVERCHARGED', label: 'Freight Overcharged' },
              { key: 'RETURN_NOT_RECEIVED', label: 'Return Not Received' },
              { key: 'PENDING', label: 'Pending' },
              { key: 'SETTLED', label: 'Settled' }
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveStatusFilter(tab.key)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  activeStatusFilter === tab.key
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search & Partner Filter */}
          <div className="flex items-center gap-3 w-full md:w-auto">
            <select
              value={selectedPartner}
              onChange={(e) => setSelectedPartner(e.target.value)}
              className="text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Partners</option>
              <option value="shopify">Shopify</option>
              <option value="amazon">Amazon</option>
              <option value="flipkart">Flipkart</option>
              <option value="delhivery">Delhivery</option>
              <option value="bluedart">BlueDart</option>
            </select>

            <select
              value={selectedAgeBucket}
              onChange={(e) => setSelectedAgeBucket(e.target.value)}
              className="text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Ages</option>
              <option value="0-7">0–7 days</option>
              <option value="8-15">8–15 days</option>
              <option value="16-30">16–30 days</option>
              <option value="31+">31+ days</option>
            </select>

            <div className="relative flex-1 md:w-64">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search Order ID or reason..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Orders Master Reconciliation Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-500" />
            <h3 className="font-semibold text-slate-900 text-sm">
              Reconciled Transactions ({filteredOrders.length})
            </h3>
          </div>
          <button
            onClick={loadData}
            disabled={isLoadingData}
            className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingData ? 'animate-spin' : ''}`} />
            Refresh Table
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] font-semibold border-b border-slate-200">
              <tr>
                <th className="px-4 py-3">Order ID & Date</th>
                <th className="px-4 py-3">Partner • Mode</th>
                <th className="px-4 py-3 text-right">Order Value</th>
                <th className="px-4 py-3 text-right">Expected Net</th>
                <th className="px-4 py-3 text-right">Received Net</th>
                <th className="px-4 py-3 text-right">Variance</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right text-rose-700 font-bold">Money at Risk</th>
                <th className="px-4 py-3">Age / Bucket</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {filteredOrders.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-12 text-center text-slate-400 font-sans">
                    {isLoadingData ? 'Loading reconciliation records...' : 'No orders matched the selected filter.'}
                  </td>
                </tr>
              ) : (
                filteredOrders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-bold text-slate-900">{o.external_order_id || o.order_id}</div>
                      <div className="text-[10px] text-slate-400 font-sans">
                        {new Date(o.order_date).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="px-4 py-3 uppercase font-sans">
                      <div className="font-semibold text-slate-800">{o.partner_id}</div>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 font-mono">
                        {o.payment_mode}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-800">
                      ₹{Number(o.order_value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-right text-indigo-700 font-semibold">
                      {o.expected_amount !== null
                        ? `₹${Number(o.expected_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                        : <span className="text-amber-600 font-sans text-[11px]">No Rate Card</span>}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-800 font-semibold">
                      ₹{Number(o.received_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
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
                    <td className="px-4 py-3 font-sans">
                      {getStatusBadge(o.status)}
                    </td>
                    <td className="px-4 py-3 text-right font-bold text-rose-700 font-mono">
                      {Number(o.money_at_risk) > 0 ? (
                        `₹${Number(o.money_at_risk).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                      ) : (
                        <span className="text-slate-300 font-normal">₹0.00</span>
                      )}
                    </td>
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
                    <td className="px-4 py-3 text-right font-sans">
                      <button
                        onClick={() => setSelectedOrderForAudit(o)}
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-2.5 py-1 rounded border border-indigo-200 hover:bg-indigo-100 transition-colors"
                      >
                        Audit Breakdown
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit Breakdown Modal */}
      {selectedOrderForAudit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <Info className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-base">
                  Reconciliation Audit: {selectedOrderForAudit.order_id}
                </h3>
              </div>
              <button
                onClick={() => setSelectedOrderForAudit(null)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-700 font-sans">
              {/* Status Header */}
              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-lg border border-slate-200">
                <div>
                  <span className="text-[11px] text-slate-500 font-semibold uppercase">Classification</span>
                  <div className="mt-1">{getStatusBadge(selectedOrderForAudit.status)}</div>
                </div>
                <div className="text-right">
                  <span className="text-[11px] text-slate-500 font-semibold uppercase">Money at Risk</span>
                  <div className="text-lg font-extrabold text-rose-700 font-mono mt-0.5">
                    ₹{Number(selectedOrderForAudit.money_at_risk).toFixed(2)}
                  </div>
                </div>
              </div>

              {/* Deduction Breakdown Grid */}
              <div>
                <h4 className="font-bold text-slate-900 mb-2 uppercase tracking-wider text-[11px]">
                  Rate Card Expected Breakdown
                </h4>
                <div className="grid grid-cols-2 gap-3 p-3.5 bg-slate-50 rounded-lg border border-slate-200 font-mono">
                  <div>
                    <span className="text-slate-500 text-[11px]">Gross Order Value:</span>
                    <div className="font-bold text-slate-900">₹{selectedOrderForAudit.order_value}</div>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px]">Expected Commission:</span>
                    <div className="font-bold text-slate-900">-₹{selectedOrderForAudit.expected_commission}</div>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px]">Expected Fixed Fee:</span>
                    <div className="font-bold text-slate-900">-₹{selectedOrderForAudit.expected_fixed_fee}</div>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px]">Expected Freight Charges:</span>
                    <div className="font-bold text-slate-900">-₹{selectedOrderForAudit.expected_freight}</div>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px]">Expected COD Fee:</span>
                    <div className="font-bold text-slate-900">-₹{selectedOrderForAudit.expected_cod_fee}</div>
                  </div>
                  <div className="border-t border-slate-200 pt-1 col-span-2 flex justify-between font-bold text-indigo-700">
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
                <div className="grid grid-cols-2 gap-3 p-3.5 bg-slate-50 rounded-lg border border-slate-200 font-mono">
                  <div>
                    <span className="text-slate-500 text-[11px]">Settlement Credit:</span>
                    <div className="font-bold text-slate-900">₹{selectedOrderForAudit.settlement_credit}</div>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px]">COD Remittance:</span>
                    <div className="font-bold text-slate-900">₹{selectedOrderForAudit.cod_remittance}</div>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px]">Actual Freight Billed:</span>
                    <div className="font-bold text-slate-900">₹{selectedOrderForAudit.actual_freight}</div>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px]">Actual Commission Billed:</span>
                    <div className="font-bold text-slate-900">₹{selectedOrderForAudit.actual_commission}</div>
                  </div>
                  <div className="col-span-2 border-t border-slate-200 pt-1 flex justify-between font-bold text-slate-900">
                    <span>Total Comparable Received:</span>
                    <span>₹{selectedOrderForAudit.received_amount}</span>
                  </div>
                </div>
              </div>

              {/* Statutory Tax Separation */}
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-blue-900">
                <span className="font-bold">Statutory Taxes Isolated from Leakage:</span>
                <p className="mt-0.5 text-[11px] text-blue-800">
                  GST TCS (Sec 52): ₹{selectedOrderForAudit.tcs_amount} • Income Tax TDS (Sec 194-O): ₹{selectedOrderForAudit.tds_amount}
                  <br />
                  <span className="italic">Per compliance mandates, statutory withholdings are isolated and never classified as financial leakage.</span>
                </p>
              </div>

              {/* Non-Overlapping Money at Risk Formula */}
              {Number(selectedOrderForAudit.money_at_risk) > 0 && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-900 font-mono">
                  <span className="font-bold">Non-Overlapping Money at Risk Components:</span>
                  <div className="grid grid-cols-3 gap-2 mt-2 text-center text-[11px]">
                    <div className="p-2 bg-white rounded border border-rose-200">
                      <span className="text-slate-500 block">Settlement Gap</span>
                      <span className="font-bold">₹{selectedOrderForAudit.settlement_gap_component}</span>
                    </div>
                    <div className="p-2 bg-white rounded border border-rose-200">
                      <span className="text-slate-500 block">Freight Excess</span>
                      <span className="font-bold">₹{selectedOrderForAudit.freight_excess_component}</span>
                    </div>
                    <div className="p-2 bg-white rounded border border-rose-200">
                      <span className="text-slate-500 block">Return Loss</span>
                      <span className="font-bold">₹{selectedOrderForAudit.return_loss_component}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setSelectedOrderForAudit(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-900"
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
