import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, 
  LogOut, 
  User as UserIcon, 
  Upload as UploadIcon, 
  Layers, 
  Database,
  Scale,
  TrendingDown,
  FileCheck2
} from 'lucide-react';
import { api, User, RateCard, Source } from './api/client';
import { SignIn } from './pages/SignIn';
import { UploadCenter } from './pages/UploadCenter';
import { ColumnMappingReview } from './pages/ColumnMappingReview';
import { ReconciliationHub } from './pages/ReconciliationHub';
import { MoneyAtRiskDashboard } from './pages/MoneyAtRiskDashboard';
import { ClaimsManagement } from './pages/ClaimsManagement';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'recon' | 'claims' | 'uploads' | 'mappings' | 'rate_cards'>('dashboard');
  const [rateCards, setRateCards] = useState<RateCard[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedMappingSourceId, setSelectedMappingSourceId] = useState<string>('');
  const [selectedUploadId, setSelectedUploadId] = useState<string | undefined>(undefined);
  const [claimStatusFilter, setClaimStatusFilter] = useState<string | undefined>(undefined);
  const [claimPartnerFilter, setClaimPartnerFilter] = useState<string | undefined>(undefined);

  useEffect(() => {
    checkSession();
    // Restore uploadId or activeTab from URL search parameters on refresh
    try {
      const params = new URLSearchParams(window.location.search);
      const urlUploadId = params.get('uploadId');
      const urlSourceId = params.get('sourceId');
      const urlTab = params.get('tab') as any;
      if (urlUploadId) {
        setSelectedUploadId(urlUploadId);
        if (urlSourceId) setSelectedMappingSourceId(urlSourceId);
        setActiveTab('mappings');
      } else if (urlTab && ['dashboard', 'recon', 'claims', 'uploads', 'mappings', 'rate_cards'].includes(urlTab)) {
        setActiveTab(urlTab);
      }
    } catch {}
  }, []);

  const checkSession = async () => {
    try {
      const user = await api.getMe();
      setCurrentUser(user);
      loadInitialData();
    } catch {
      setCurrentUser(null);
    } finally {
      setLoading(false);
    }
  };

  const loadInitialData = async () => {
    try {
      const [cards, srcList] = await Promise.all([
        api.listRateCards(),
        api.listSources()
      ]);
      setRateCards(cards);
      setSources(srcList);
      if (srcList.length > 0 && !selectedMappingSourceId) {
        setSelectedMappingSourceId(srcList[0].id);
      }
    } catch (err) {
      console.error('Failed to load initial metadata', err);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      setCurrentUser(null);
    }
  };

  const handleNavigateToMapping = (sourceId: string, uploadId?: string) => {
    setSelectedMappingSourceId(sourceId);
    setSelectedUploadId(uploadId);
    setActiveTab('mappings');
    try {
      const url = new URL(window.location.href);
      if (uploadId) {
        url.searchParams.set('uploadId', uploadId);
        url.searchParams.set('sourceId', sourceId);
      } else {
        url.searchParams.delete('uploadId');
      }
      window.history.replaceState({}, '', url.toString());
    } catch {}
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400 tracking-wider">INITIALIZING LEAKCHECK...</span>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <SignIn
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          loadInitialData();
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-800 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-sm">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div className="flex items-center">
                <span className="text-lg font-bold tracking-tight text-slate-900 font-mono">
                  Leak<span className="text-indigo-600">Check</span>
                </span>
                <span className="ml-2 inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold whitespace-nowrap">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  v1.0.0 Ready
                </span>
              </div>
            </div>

            {/* Main Tabs */}
            <nav className="flex space-x-1">
              <button
                onClick={() => setActiveTab('dashboard')}
                className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
                  activeTab === 'dashboard'
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <TrendingDown className="w-4 h-4" />
                Executive Dashboard
              </button>

              <button
                onClick={() => setActiveTab('recon')}
                className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
                  activeTab === 'recon'
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <Scale className="w-4 h-4" />
                Orders &amp; Recon
              </button>

              <button
                onClick={() => setActiveTab('claims')}
                className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
                  activeTab === 'claims'
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <FileCheck2 className="w-4 h-4" />
                Claims Management
              </button>

              <button
                onClick={() => setActiveTab('uploads')}
                className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
                  activeTab === 'uploads'
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <UploadIcon className="w-4 h-4" />
                Upload Center
              </button>

              <button
                onClick={() => {
                  setSelectedUploadId(undefined);
                  setActiveTab('mappings');
                  try {
                    const url = new URL(window.location.href);
                    url.searchParams.delete('uploadId');
                    window.history.replaceState({}, '', url.toString());
                  } catch {}
                }}
                className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
                  activeTab === 'mappings'
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <Layers className="w-4 h-4" />
                Column Mapping
              </button>

              <button
                onClick={() => setActiveTab('rate_cards')}
                className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
                  activeTab === 'rate_cards'
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <Database className="w-4 h-4" />
                Rate Cards
              </button>
            </nav>
          </div>

          {/* User info and Logout */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
              <UserIcon className="w-3.5 h-3.5 text-slate-500" />
              <span className="text-slate-700 font-mono">{currentUser.email}</span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider font-bold ${
                  currentUser.role === 'finance_exec'
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                    : 'bg-indigo-100 text-indigo-800 border border-indigo-300'
                }`}
              >
                {currentUser.role === 'finance_exec' ? 'Finance Exec' : 'Co-founder'}
              </span>
            </div>

            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900 text-xs border border-slate-200 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">
        {activeTab === 'dashboard' && (
          <MoneyAtRiskDashboard
            currentUser={currentUser}
            onNavigateToOrders={() => setActiveTab('recon')}
            onNavigateToClaims={(status, partner) => {
              setClaimStatusFilter(status);
              setClaimPartnerFilter(partner);
              setActiveTab('claims');
            }}
          />
        )}

        {activeTab === 'recon' && (
          <ReconciliationHub currentUser={currentUser} />
        )}

        {activeTab === 'claims' && (
          <ClaimsManagement
            currentUser={currentUser}
            initialStatusFilter={claimStatusFilter}
            initialPartnerFilter={claimPartnerFilter}
          />
        )}

        {activeTab === 'uploads' && (
          <UploadCenter
            currentUser={currentUser}
            onNavigateToMapping={handleNavigateToMapping}
          />
        )}

        {activeTab === 'mappings' && (
          <ColumnMappingReview
            currentUser={currentUser}
            sourceId={selectedMappingSourceId || (sources[0]?.id || '')}
            uploadId={selectedUploadId}
            sources={sources}
            onSelectSource={(newSourceId) => {
              setSelectedMappingSourceId(newSourceId);
              setSelectedUploadId(undefined);
              try {
                const url = new URL(window.location.href);
                url.searchParams.delete('uploadId');
                url.searchParams.set('sourceId', newSourceId);
                window.history.replaceState({}, '', url.toString());
              } catch {}
            }}
            onBackToUploads={() => {
              setSelectedUploadId(undefined);
              setActiveTab('uploads');
              try {
                const url = new URL(window.location.href);
                url.searchParams.delete('uploadId');
                window.history.replaceState({}, '', url.toString());
              } catch {}
            }}
          />
        )}

        {activeTab === 'rate_cards' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200">
              <div>
                <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                  <Database className="w-7 h-7 text-indigo-600" />
                  Calibrated Rate Cards
                </h1>
                <p className="text-sm text-slate-600 mt-1">
                  Half-open non-overlapping rate cards calibrated for sample orders.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {rateCards.map((rc) => (
                <div key={rc.id} className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-sm uppercase text-slate-900 font-mono">
                      {rc.partner_id} • {rc.channel}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                      Active
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 font-mono mb-3">
                    Valid: {rc.valid_from} to {rc.valid_until || 'ongoing'}
                  </div>
                  <pre className="text-[11px] bg-slate-50 p-2.5 rounded border border-slate-200 overflow-x-auto font-mono text-slate-800">
                    {JSON.stringify(rc.params_json, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
