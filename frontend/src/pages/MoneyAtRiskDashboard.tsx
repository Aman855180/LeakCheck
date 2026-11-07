import React, { useState, useEffect, useCallback } from 'react';
import { 
  TrendingDown, 
  AlertTriangle, 
  ShieldAlert, 
  RefreshCw, 
  ArrowUpRight, 
  FileText, 
  Calendar,
  DollarSign,
  Percent
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell, 
  Legend 
} from 'recharts';
import { api, DashboardMetrics, User } from '../api/client';

interface MoneyAtRiskDashboardProps {
  currentUser: User;
  onNavigateToOrders: (statusFilter?: string, partnerId?: string) => void;
  onNavigateToClaims: (statusFilter?: string, partnerId?: string) => void;
}

const LEAKAGE_COLORS = ['#ef4444', '#8b5cf6', '#f59e0b'];

export const MoneyAtRiskDashboard: React.FC<MoneyAtRiskDashboardProps> = ({
  onNavigateToOrders,
  onNavigateToClaims,
}) => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadMetrics = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getDashboardMetrics();
      setMetrics(data);
    } catch (err: any) {
      console.error('Failed to load dashboard metrics', err);
      setError(err.message || 'Failed to load executive dashboard metrics.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  if (isLoading && !metrics) {
    return (
      <div className="py-20 flex flex-col items-center justify-center space-y-3">
        <RefreshCw className="w-8 h-8 animate-spin text-indigo-600" />
        <p className="text-xs font-mono text-slate-500 tracking-wider uppercase">
          Calculating Money-at-Risk Telemetry...
        </p>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="p-8 text-center bg-rose-50 border border-rose-200 rounded-xl">
        <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto mb-2" />
        <h3 className="text-sm font-bold text-rose-800">Error Loading Dashboard</h3>
        <p className="text-xs text-rose-600 mt-1 max-w-md mx-auto">{error}</p>
        <button
          onClick={loadMetrics}
          className="mt-4 px-4 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-semibold hover:bg-rose-700"
        >
          Retry
        </button>
      </div>
    );
  }

  // Transform Data for Visualizations
  const leakageComponentData = metrics ? [
    { name: 'Settlement Shortfall', value: Number(metrics.total_settlement_gap), fill: '#ef4444' },
    { name: 'Freight Excess', value: Number(metrics.total_freight_excess), fill: '#8b5cf6' },
    { name: 'Return Loss', value: Number(metrics.total_return_loss), fill: '#f59e0b' },
  ].filter(d => d.value > 0) : [];

  const agingData = metrics ? [
    { bucket: '0–7 Days', risk: Number(metrics.age_bucket_risk['0-7'] || 0), count: metrics.age_bucket_counts['0-7'] || 0 },
    { bucket: '8–15 Days', risk: Number(metrics.age_bucket_risk['8-15'] || 0), count: metrics.age_bucket_counts['8-15'] || 0 },
    { bucket: '16–30 Days', risk: Number(metrics.age_bucket_risk['16-30'] || 0), count: metrics.age_bucket_counts['16-30'] || 0 },
    { bucket: '31+ Days', risk: Number(metrics.age_bucket_risk['31+'] || 0), count: metrics.age_bucket_counts['31+'] || 0 },
  ] : [];

  const partnerRiskData = metrics ? Object.entries(metrics.partner_risk_breakdown).map(([partner, risk]) => ({
    partner: partner.toUpperCase(),
    risk: Number(risk),
    orders: metrics.partner_order_counts[partner] || 0
  })).sort((a, b) => b.risk - a.risk) : [];

  const claimsSummary = metrics?.claims_summary;

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-200 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <TrendingDown className="w-7 h-7 text-indigo-600" />
              Money-at-Risk Executive Dashboard
            </h1>
            <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold font-mono">
              LIVE PERSISTED METRICS
            </span>
          </div>
          <p className="text-sm text-slate-600 mt-1">
            Real-time financial leakage breakdown, aging buckets, partner exposure, and claim recovery telemetry.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-slate-300 text-xs shadow-sm font-sans">
            <Calendar className="w-4 h-4 text-slate-500" />
            <span className="font-semibold text-slate-700">Recon As-Of:</span>
            <span className="font-mono font-bold text-slate-900">{metrics?.as_of || '2026-11-01'}</span>
          </div>

          <button
            onClick={loadMetrics}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Primary KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Money at Risk */}
        <div className="bg-white p-5 rounded-xl border border-rose-200 shadow-sm bg-gradient-to-br from-white to-rose-50/50">
          <div className="flex items-center justify-between text-xs text-rose-600 font-semibold mb-1">
            <span>Total Money at Risk</span>
            <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 text-[10px] font-extrabold uppercase">
              Strict Non-Overlap
            </span>
          </div>
          <div className="text-3xl font-black text-rose-700 font-mono tracking-tight mt-1">
            ₹{metrics ? Number(metrics.total_money_at_risk).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2 pt-2 border-t border-rose-100">
            <span>Active Exposure</span>
            <button
              onClick={() => onNavigateToOrders('RISK_ONLY')}
              className="text-rose-700 hover:text-rose-900 font-bold flex items-center gap-0.5"
            >
              View Orders <ArrowUpRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* Settlement Shortfall */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Settlement Shortfall</span>
            <DollarSign className="w-4 h-4 text-rose-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-2">
            ₹{metrics ? Number(metrics.total_settlement_gap).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Prepaid net gaps + overdue COD cash</p>
        </div>

        {/* Freight Overcharge */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Freight Overcharge</span>
            <TrendingDown className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-2">
            ₹{metrics ? Number(metrics.total_freight_excess).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Actual courier invoice &gt; contracted tariff</p>
        </div>

        {/* Return-Related Loss */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Return-Related Loss</span>
            <ShieldAlert className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-2">
            ₹{metrics ? Number(metrics.total_return_loss).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Missing dock deliveries &amp; excess deductions</p>
        </div>

        {/* Claims Recovery Telemetry */}
        <div className="bg-white p-5 rounded-xl border border-emerald-200 shadow-sm bg-gradient-to-br from-white to-emerald-50/40">
          <div className="flex items-center justify-between text-xs text-emerald-700 font-semibold mb-1">
            <span>Claims Recovered</span>
            <Percent className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-emerald-800 font-mono mt-1">
            ₹{claimsSummary ? Number(claimsSummary.total_recovered_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
          </div>
          <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2 pt-2 border-t border-emerald-100">
            <span>Recovery Rate: <strong className="text-emerald-700">{claimsSummary?.recovery_rate_pct ?? '0.00'}%</strong></span>
            <button
              onClick={() => onNavigateToClaims()}
              className="text-emerald-700 hover:text-emerald-900 font-bold flex items-center gap-0.5"
            >
              Claims <ArrowUpRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Visual Analytics Grid: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Financial Leakage Component Composition */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Non-Overlapping Leakage Composition</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Mutually exclusive breakdown isolating settlement shortfall, freight, and return losses.
              </p>
            </div>
          </div>

          {leakageComponentData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-slate-400 text-xs">
              No financial leakage identified across reconciled orders.
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={leakageComponentData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={85}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {leakageComponentData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill || LEAKAGE_COLORS[index % LEAKAGE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(val: number) => [`₹${val.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, 'Amount']}
                    contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', fontSize: '12px' }}
                  />
                  <Legend 
                    verticalAlign="bottom" 
                    height={36} 
                    iconType="circle"
                    formatter={(val: string) => <span className="text-xs text-slate-700">{val}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Chart 2: Aging Risk Distribution */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Aging Buckets: Money at Risk (INR)</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Standardized intervals: 0–7d, 8–15d, 16–30d, and 31+ days.
              </p>
            </div>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={agingData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${v}`} />
                <Tooltip
                  formatter={(val: number, name: string) => [
                    name === 'risk' ? `₹${val.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : val,
                    name === 'risk' ? 'Money at Risk' : 'Order Count'
                  ]}
                  contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', fontSize: '12px' }}
                />
                <Bar dataKey="risk" name="risk" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Partner Breakdown & Claims Portfolio Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Partner Exposure Leaderboard */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Partner Financial Leakage Leaderboard</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Total money at risk ranked across marketplaces, quick-commerce, and logistics aggregators.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-2.5">Partner</th>
                  <th className="px-4 py-2.5 text-right">Orders Tracked</th>
                  <th className="px-4 py-2.5 text-right text-rose-700 font-bold">Money at Risk</th>
                  <th className="px-4 py-2.5 text-right">Claims Filed</th>
                  <th className="px-4 py-2.5 text-right text-emerald-700 font-semibold">Recovered</th>
                  <th className="px-4 py-2.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {partnerRiskData.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-400 font-sans">
                      No partner exposure data available.
                    </td>
                  </tr>
                ) : (
                  partnerRiskData.map((p) => {
                    const pClaims = claimsSummary?.partner_claims_summary[p.partner.toLowerCase()] || {
                      total_claims: 0,
                      claimed_amount: '0.00',
                      recovered_amount: '0.00',
                      outstanding_amount: '0.00'
                    };
                    return (
                      <tr key={p.partner} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3 font-bold text-slate-900 font-sans">
                          {p.partner}
                        </td>
                        <td className="px-4 py-3 text-right text-slate-700">
                          {p.orders}
                        </td>
                        <td className="px-4 py-3 text-right font-bold text-rose-700">
                          ₹{p.risk.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-3 text-right text-slate-700">
                          ₹{Number(pClaims.claimed_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })} ({pClaims.total_claims})
                        </td>
                        <td className="px-4 py-3 text-right text-emerald-700 font-bold">
                          ₹{Number(pClaims.recovered_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-3 text-right font-sans">
                          <button
                            onClick={() => onNavigateToOrders(undefined, p.partner.toLowerCase())}
                            className="text-indigo-600 hover:text-indigo-900 font-semibold text-[11px]"
                          >
                            Filter Orders →
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Claims Recovery Portfolio Card */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-900 text-sm">Claims Lifecycle Summary</h3>
              <FileText className="w-4 h-4 text-indigo-600" />
            </div>
            <p className="text-xs text-slate-500 mb-4">
              Total claims generated from verified discrepancies and recovery turnaround.
            </p>

            <div className="space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-slate-600 font-sans">Total Claims Drafted/Filed:</span>
                <span className="font-bold text-slate-900">{claimsSummary?.total_claims ?? 0}</span>
              </div>
              <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-slate-600 font-sans">Total Claimed Value:</span>
                <span className="font-bold text-slate-900">₹{claimsSummary?.total_claim_amount ?? '0.00'}</span>
              </div>
              <div className="flex items-center justify-between p-2.5 bg-emerald-50 rounded-lg border border-emerald-200 text-emerald-900">
                <span className="font-sans font-semibold">Total Amount Recovered:</span>
                <span className="font-black text-emerald-700">₹{claimsSummary?.total_recovered_amount ?? '0.00'}</span>
              </div>
              <div className="flex items-center justify-between p-2.5 bg-rose-50 rounded-lg border border-rose-200 text-rose-900">
                <span className="font-sans font-semibold">Outstanding to Recover:</span>
                <span className="font-black text-rose-700">₹{claimsSummary?.total_outstanding_amount ?? '0.00'}</span>
              </div>
            </div>

            {/* Status Breakdown Chips */}
            <div className="mt-5 pt-4 border-t border-slate-100">
              <span className="text-[10px] uppercase font-bold text-slate-400 block mb-2 font-sans">
                Status Distribution
              </span>
              <div className="grid grid-cols-2 gap-2 text-[11px] font-sans">
                <div className="flex items-center justify-between px-2.5 py-1 bg-slate-100 rounded text-slate-700">
                  <span>Drafts:</span>
                  <span className="font-mono font-bold">{claimsSummary?.status_counts.draft ?? 0}</span>
                </div>
                <div className="flex items-center justify-between px-2.5 py-1 bg-amber-50 rounded text-amber-800 border border-amber-200">
                  <span>Submitted:</span>
                  <span className="font-mono font-bold">{claimsSummary?.status_counts.submitted ?? 0}</span>
                </div>
                <div className="flex items-center justify-between px-2.5 py-1 bg-blue-50 rounded text-blue-800 border border-blue-200">
                  <span>In Review:</span>
                  <span className="font-mono font-bold">{claimsSummary?.status_counts.in_review ?? 0}</span>
                </div>
                <div className="flex items-center justify-between px-2.5 py-1 bg-emerald-50 rounded text-emerald-800 border border-emerald-200">
                  <span>Recovered:</span>
                  <span className="font-mono font-bold">{claimsSummary?.status_counts.recovered ?? 0}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-100">
            <button
              onClick={() => onNavigateToClaims()}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors flex items-center justify-center gap-1.5"
            >
              Manage &amp; Track All Claims
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
